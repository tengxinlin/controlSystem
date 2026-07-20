import base64
import json
import sys
import time
from datetime import datetime
from typing import Tuple, List

import folium
import tempfile
import os

from PyQt5.QtGui import QBrush, QColor, QTextCursor
from PyQt5.QtWebEngineWidgets import QWebEngineSettings
from sqlalchemy import false

from APIManager import APIManager,APIService
from led_manager import LEDManager
from led_widget import LEDWidget
from mapBridge import MapBridge
from mileage_region_manager import MileageRegionManager
from passage_record_edit_dialog import PassageRecordEditDialog
from passage_record_manager import PassageRecordManager
from queue_manager import QueueManager
from queue_timer_processor import QueueTimerProcessor
from ship_manager import ShipInfo
from signal_confirm_dialog import SignalConfirmDialog
from sqlite3Manager import SQLiteTableManager

# 或者禁用硬件加速
os.environ["QT_WEBENGINE_DISABLE_GPU"] = "1"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget,
                             QVBoxLayout, QHBoxLayout, QPushButton,
                             QLineEdit, QLabel, QMessageBox, QGridLayout, QTableWidgetItem, QHeaderView, QTableWidget,
                             QDialog)
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, pyqtSignal, QObject, Qt, center, QTimer, QDateTime
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtCore import QObject, pyqtSlot
from mainwindow import Ui_MainWindow
from PyQt5.QtWidgets import QMainWindow
from login_dialog import LoginDialog

from reach_data import ControlReach, ReachPoint, ReachLine, ReachPolygon, FenceArea, RevealArea

import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QSizePolicy
from mainwindow import Ui_MainWindow  # 导入转换后的UI类
from FoliumMapWidget import FoliumMapWidget
from config import ConfigManager  # 假设 config_manager.py 在同一目录
from mqtt_ui import MQTTControlWidget

class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self,api_service,username):
        """
               主窗口构造函数
               :param api_service: 已登录的APIService实例
               :param username: 登录用户名
               """
        super().__init__()

        self.bridge = None
        self.channel = None
        self.reaches = None
        self.setupUi(self)  # 加载 UI 界面
        self.username = username

        # 获取屏幕尺寸
        screen = QApplication.primaryScreen()
        screen_size = screen.availableGeometry()  # 或 screen.size()
        width = int(screen_size.width() * 0.95)
        height = int(screen_size.height() *0.95)
        self.resize(width, height)

        # 记录程序启动时间
        self.startup_time = time.time()
        self.is_open = True  # 是否开机超过2分钟
        # 初始化时间显示
        self.init_time_display()

        # 你可以通过 self.map_frame 访问它
        frame = self.frame_map
        # 确保 frame 可见且有大小
        frame.show()

        # 强制布局更新
        QApplication.processEvents()

        print(f"frame 大小: {frame.width()} x {frame.height()}")

        # 检查 frame 是否已有布局，若无则创建一个垂直布局
        if frame.layout() is None:
            layout = QVBoxLayout(frame)
        else:
            layout = frame.layout()

        # 创建新的MQTT控件
        self.mqtt_widget = MQTTControlWidget(api_service)
        # 连接按钮信号
        self.mqtt_btn.clicked.connect(self.show_mqtt_widget)

        #创建地图船舶绘制器
        self.ship_drawer = None



        # 创建WebEngineView
        self.webView = QWebEngineView()
        layout.addWidget(self.webView)

        # 确保 WebView 可见
        self.webView.show()

        # 启用必要的设置
        self.webView.settings().setAttribute(
            self.webView.settings().WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self.webView.settings().setAttribute(
            self.webView.settings().WebAttribute.LocalContentCanAccessFileUrls, True
        )
        self.webView.settings().setAttribute(
            self.webView.settings().WebAttribute.AllowWindowActivationFromJavaScript, True
        )

        # 禁用Web安全限制（仅用于本地开发）
        self.webView.settings().setAttribute(
            self.webView.settings().WebAttribute.LocalContentCanAccessFileUrls, True
        )
        self.webView.settings().setAttribute(
            self.webView.settings().WebAttribute.AllowRunningInsecureContent, True
        )

        # 启用JavaScript
        self.webView.settings().setAttribute(self.webView.settings().WebAttribute.JavascriptEnabled, True)
        self.webView.settings().setAttribute(self.webView.settings().WebAttribute.JavascriptCanOpenWindows, True)

        # 初始化配置管理器
        self.config_mgr = ConfigManager(app_name="MyMapApp")

        #控制河段必要参数定义
        self.network=self.config_mgr.get("InternetType")
        self.controlRivername = self.config_mgr.get("controlRiverName")
        self.reachCode = self.config_mgr.get("reachCode")

        # 创建管理器实例
        self.db_manager = SQLiteTableManager("test.db")
        self.db_manager.connect()

        self.current_reach = None  # 当前选中的控制河段

        # 创建里程区域管理器
        self.mileage_manager = MileageRegionManager()


        # 设置定时器清理过期船舶
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self.cleanup_expired_ships)
        self.cleanup_timer.start(60000*5)  # 每5分钟清理一次


        # 创建通行记录管理器
        self.passage_record_manager = PassageRecordManager(self.db_manager)
        # 连接信号
        self.passage_record_manager.record_created.connect(self.on_record_created)
        self.passage_record_manager.record_completed.connect(self.on_record_completed)

        # 通行记录管理界面（单例）
        self.passage_record_dialog = None

        # 设置定时器自动清理
        self.cleanup_timer_record = QTimer()
        self.cleanup_timer_record.timeout.connect(self.passage_record_manager.auto_cleanup)
        self.cleanup_timer_record.start(3600000)  # 每小时清理一次
        self.record_btn.clicked.connect(self.show_passage_records)

        # 创建队列管理器
        from queue_manager import QueueManager
        self.queue_manager = QueueManager(self.passage_record_manager,self.get_current_signal,self.log_message,self.current_reach)

        # 创建队列处理器
        self.queue_processor = None
        self.current_signal = '关闭'  # 控制河段的信号,关闭，上水，下水，半杆，禁航

        #api接口
        self.api = api_service

        self.initLocalDB()

        #控制河段信息读取
        # 设置日志控件
        self.setup_log_widget()
        # 显示启动日志
        self.log_message(f"系统启动，欢迎用户: {username}")

        # 控制河段选择COMBOX信号连接
        self.comboBox.currentTextChanged.connect(self.on_reach_selected)
        self.load_reach_data(self.controlRivername)

        # 设置 WebChannel
        self.setup_web_channel()

        # 初始化LED管理器
        self.led_manager = LEDManager(self.db_manager, self.mqtt_widget.mqtt_manager,self.log_message)

        # 初始化LED相关变量
        self.led_widgets = []  # 存储LED控件
        self.led_layout = None  # LED布局

        # 假设你的 QWidget 名字是 widget_led_container
        self.init_led_container()

        # # 连接LED状态变化信号
        # self.led_manager.led_status_changed.connect(self.on_led_status_changed)
        # self.led_manager.led_connection_changed.connect(self.on_led_connection_changed)
        # # self.mqtt_widget.show()

        #初始化后选择combox
        river = self.db_manager.search_records("Reaches", {"ReachCode": self.reachCode})
        # 使用 split() 分割字符串
        longitude, latitude = river[0].get("CenterP").split(',')
        self.comboBox.setCurrentText("0")
        self.comboBox.setCurrentText(river[0].get("ReachName"))

        # 当前需要揭示信号的船舶信息
        self.pending_signal_mmsi=None
        self.pending_signal_ship = None
        self.pending_signal_type = None
        self.signal_dialog = None  # 保存对话框引用





    def get_current_signal(self) -> str:
        """
        获取当前控制河段信号

        Returns:
            '上水': 上水信号
            '下水': 下水信号
            '关闭': 关闭信号
            '半杆': 半杆信号
        """
        # 这里根据实际情况返回当前信号
        # 可以从LED灯状态、信号控制界面等获取
        return self.current_signal

    def start_queue_processor(self):
        """启动队列定时器处理器"""
        print("正在启动队列定时器处理器...")

        self.queue_processor = QueueTimerProcessor(
            self.queue_manager,
            self.get_current_signal,
            parent=self
        )

        # 连接信号
        self.queue_processor.pending_updated.connect(self.update_pending_table)
        self.queue_processor.commanded_updated.connect(self.update_commanded_table)
        self.queue_processor.control_area_updated.connect(self.update_control_area_table)
        self.queue_processor.show_signal_dialog.connect(self.show_signal_confirm_dialog)

        # 启动定时器
        self.queue_processor.start()

        print("队列定时器处理器已启动")

    def show_signal_confirm_dialog(self,mmsi:str, ship_name: str, signal_type: str):
        """显示信号确认对话框"""
        # 如果已经有对话框打开，先关闭旧的
        if self.signal_dialog and self.signal_dialog.isVisible():
            print("已有对话框打开，关闭旧对话框")
            self.signal_dialog.close()

        self.pending_signal_mmsi = mmsi
        self.pending_signal_ship = ship_name
        self.pending_signal_type = signal_type

        # 创建对话框
        self.signal_dialog = SignalConfirmDialog(mmsi,ship_name, signal_type, timeout_seconds=10, parent=self)

        # 连接信号
        self.signal_dialog.confirmed.connect(self.on_signal_confirmed)
        self.signal_dialog.cancelled.connect(self.on_signal_cancelled)
        self.signal_dialog.timeout.connect(self.on_signal_timeout)

        # 对话框关闭时通知处理器
        self.signal_dialog.finished.connect(self.on_dialog_finished)

        # 显示对话框
        self.signal_dialog.show()

    def on_signal_confirmed(self,mmsi,signal):
        """用户确认揭示信号"""
        if self.pending_signal_ship and self.pending_signal_type:
            self.log_message(f"✅ 用户确认揭示信号: {self.pending_signal_ship} -> {self.pending_signal_type}")

            if signal == self.current_signal:
                #要揭示的信号等于当前信号，记录补充时间
                self.passage_record_manager.record_signal_channel(mmsi,2)
            elif signal != self.pending_signal_mmsi  and signal != '半杆':
                # 要揭示的信号不等于当前信号，记录起卦时间
                self.passage_record_manager.record_signal_channel(mmsi, 1)
            else:
                #半杆信号
                self.passage_record_manager.record_signal_channel(mmsi, 3)

            # 发送MQTT信号
            self.send_mqtt_signal(self.pending_signal_type, self.pending_signal_ship)

            #发送信号后更新当前信号
            self.current_signal = signal

            self.label_signal.setText(signal)
            self.label_current_signal.setText(signal)

            # 从待指挥队列移到已指挥队列
            self._update_ship_signal_revealed(self.pending_signal_ship, self.pending_signal_type)

            # 记录日志
            self.log_message(f"揭示信号: {self.pending_signal_ship} - {self.pending_signal_type}")

    def on_signal_cancelled(self):
        """用户取消揭示信号"""
        if self.pending_signal_ship:
            print(f"❌ 用户取消揭示信号: {self.pending_signal_ship}")

            # 在队列处理器中阻止该船舶2分钟内再次弹窗
            if self.queue_processor:
                # 需要找到该船舶的MMSI
                mmsi = self._get_ship_mmsi_by_name(self.pending_signal_ship)
                if mmsi:
                    self.queue_processor._block_ship(mmsi)

            self.log_message(f"取消揭示信号: {self.pending_signal_ship}")

    def on_signal_timeout(self):
        """倒计时结束"""
        print(f"⏰ 倒计时结束，自动确认揭示信号: {self.pending_signal_ship}")
        # 自动确认
        self.on_signal_confirmed(self.pending_signal_mmsi)

    def on_dialog_finished(self):
        """对话框关闭时的处理"""
        if self.queue_processor:
            # 通知处理器对话框已关闭
            self.queue_processor.on_dialog_closed()

        self.pending_signal_ship = None
        self.pending_signal_type = None
        self.signal_dialog = None

    def send_mqtt_signal(self, signal_type: str, ship_name: str = None):
        """
        发送控制信号（同时通过 MQTT 和 LoRa 控制所有灯）

        Args:
            signal_type: 信号类型 ('上水', '下水', '半杆', '关闭','禁航')
            ship_name: 船舶名称（可选）
        """
        # 信号类型映射到状态码
        signal_map = {
            '禁航':0, #禁航信号
            '上水': 1,  # 上水信号
            '下水': 2,  # 下水信号
            '半杆': 3,  # 半杆信号
            '关闭': 4  # 关闭信号
        }

        status = signal_map.get(signal_type, 4)

        # 获取当前控制河段的所有 LED
        if not hasattr(self, 'led_manager') or not self.led_manager:
            print("❌ LED 管理器未初始化")
            return

        # 获取当前控制河段的 LED 列表
        current_reach_code = self.reachCode if hasattr(self, 'reachCode') else None
        if not current_reach_code:
            print("❌ 未获取到当前控制河段代码")
            return

        leds = self.led_manager.reach_leds.get(current_reach_code, [])
        if not leds:
            print(f"⚠️ 控制河段 {current_reach_code} 没有 LED 灯")
            return

        # ========== 发送 MQTT 控制指令 ==========
        mqtt_success_count = 0
        lora_success_count = 0

        for led in leds:
            # 1. 通过 MQTT 发送（如果 LED 有 MQTT 发布主题）
            if led.publish_topic:
                try:
                    mqtt_message = str(status)
                    result = self.mqtt_widget.mqtt_manager.publish(led.publish_topic, mqtt_message)
                    if result:
                        mqtt_success_count += 1
                        print(f"📡 MQTT [{led.led_name}]: {led.get_status_text()}")
                except Exception as e:
                    print(f"❌ MQTT 控制 {led.led_name} 失败: {e}")

            # 2. 通过 LoRa 发送（如果 LED 有 LoRa 信息）
            if led.lora_id and led.lora_publish:
                try:
                    # LoRa 命令格式: "command loraid 灯序号 状态码"
                    lora_message = f"command {led.lora_id} {led.lora_index} {status}"
                    result = self.mqtt_widget.mqtt_manager.publish(led.lora_publish, lora_message)
                    if result:
                        lora_success_count += 1
                        print(f"📡 LoRa [{led.led_name}]: {led.get_status_text()}")
                except Exception as e:
                    print(f"❌ LoRa 控制 {led.led_name} 失败: {e}")

        # 记录发送结果
        total_leds = len(leds)
        print(f"\n📤 信号发送完成:")
        print(f"   信号类型: {signal_type} (状态码: {status})")
        print(f"   控制河段: {current_reach_code}")
        print(f"   LED总数: {total_leds}")
        print(f"   MQTT成功: {mqtt_success_count}")
        print(f"   LoRa成功: {lora_success_count}")

        # 如果有船舶名称，记录日志
        if ship_name:
            self.log_message(f"发送 {signal_type} 信号，船舶: {ship_name}")
        else:
            self.log_message(f"发送 {signal_type} 信号")

        return mqtt_success_count + lora_success_count

    def _update_ship_signal_revealed(self, ship_name: str, signal_type: str):
        """更新船舶的揭示状态 - 从待指挥队列移到已指挥队列"""
        # 找到待指挥队列中的对应船舶
        ships = self.queue_manager.get_pending_list()
        target_ship = None
        target_mmsi = None

        for ship in ships:
            if ship.get('name') == ship_name:
                target_ship = ship.copy()
                target_mmsi = ship.get('mmsi')
                break

        if target_ship and target_mmsi:
            # 更新揭示信息
            target_ship['signal_revealed'] = True
            target_ship['reveal_time'] = time.time()
            target_ship['reveal_signal'] = signal_type
            target_ship['command_time'] = time.time()  # 记录指挥时间

            # 从待指挥队列移除
            self.queue_manager.remove_from_pending(target_mmsi)

            # 添加到已指挥队列
            self.queue_manager.add_to_commanded(target_mmsi, target_ship)

            print(f"✅ 船舶 {ship_name} ({target_mmsi}) 已从待指挥队列移到已指挥队列，信号: {signal_type}")

    def _get_ship_mmsi_by_name(self, ship_name: str) -> str:
        """根据船名获取MMSI"""
        ships = self.queue_manager.get_pending_list()
        for ship in ships:
            if ship.get('name') == ship_name:
                return ship.get('mmsi')
        return None

    # 在主窗口初始化时设置
    def setup_web_channel(self):
        # 创建桥接对象
        self.bridge = MapBridge()

        # 连接信号
        self.bridge.shipDataChanged.connect(self.on_ship_data_changed)
        self.bridge.edit_ship_passage_record.connect(self.edit_ship_passage_record)

        # 创建 WebChannel
        self.channel = QWebChannel()
        self.channel.registerObject("pyQtBridge", self.bridge)

        # 设置到 webView
        self.webView.page().setWebChannel(self.channel)

    def init_led_container(self):
        """初始化LED容器"""
        # 获取LED容器
        self.led_container = self.widget_led_container

        # 确保容器可见并设置大小策略
        self.led_container.setVisible(True)
        self.led_container.setMinimumHeight(180)  # 设置最小高度
        self.led_container.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Fixed)

        # 清除现有布局
        old_layout = self.led_container.layout()
        if old_layout:
            while old_layout.count():
                item = old_layout.takeAt(0)
                if item.widget():
                    item.widget().deleteLater()
            # 删除旧布局
            from PyQt5.QtWidgets import QWidget
            QWidget().setLayout(old_layout)

        # 创建水平布局
        self.led_layout = QHBoxLayout(self.led_container)
        self.led_layout.setSpacing(0)
        self.led_layout.setContentsMargins(0, 0, 0, 0)
        self.led_layout.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)

        # 默认隐藏容器
        self.led_container.setVisible(False)

    def load_leds_for_reach(self, reachcode: str):
        """
        加载控制河段的LED灯

        Args:
            reachcode: 控制河段代码
        """
        try:
            # 获取LED列表
            leds = self.led_manager.load_leds_by_reachcode(reachcode)

            print(f"查询到LED数量: {len(leds)}")
            for led in leds:
                print(f"  - LED: {led.led_name}, ID: {led.led_id}")

            # 清空现有LED控件
            for widget in self.led_widgets:
                widget.deleteLater()
            self.led_widgets.clear()

            # 清除布局中的所有控件
            if self.led_layout:
                while self.led_layout.count():
                    item = self.led_layout.takeAt(0)
                    if item.widget():
                        item.widget().deleteLater()

            # 如果没有LED，隐藏容器
            if not leds:
                self.led_container.setVisible(False)
                print("没有LED灯需要显示")
                return

            # 最多显示4个
            display_leds = leds[:4]

            # 显示容器
            self.led_container.setVisible(True)

            # 调试：检查容器状态
            print(f"容器可见性: {self.led_container.isVisible()}")
            print(f"容器大小: {self.led_container.size().width()} x {self.led_container.size().height()}")
            print(f"容器几何: {self.led_container.geometry()}")

            # 创建LED控件并添加到水平布局
            for i, led in enumerate(display_leds):
                # 创建LED控件
                led_widget = LEDWidget(led, self.led_manager, self)
                self.led_widgets.append(led_widget)

                # 添加到水平布局
                self.led_layout.addWidget(led_widget)

                # 调试：检查控件状态
                print(
                    f"LED {i + 1}: {led.led_name}, 可见: {led_widget.isVisible()}, 大小: {led_widget.size().width()}x{led_widget.size().height()}")

            # 如果不足4个，添加弹性空间
            if len(display_leds) < 4:
                self.led_layout.addStretch()

            # 强制更新布局
            self.led_container.update()
            self.led_container.repaint()

            print(f"加载了 {len(display_leds)} 个LED灯（水平布局）")

        except Exception as e:
            print(f"加载LED灯失败: {e}")
            import traceback
            traceback.print_exc()


    def edit_ship_passage_record(self, mmsi: str,name:str):
        """
        编辑/新增船舶通行记录

        Args:
            mmsi: 船舶MMSI
            name: 船名
        """
        dialog = PassageRecordEditDialog(mmsi,name, self.passage_record_manager, self)
        dialog.record_saved.connect(self.on_passage_record_saved)
        dialog.exec_()

    def on_passage_record_saved(self, record_data):
        """通行记录保存后的处理"""
        self.log_message(f"通行记录已保存: {record_data.get('name')} ({record_data.get('mmsi')})")

    def init_time_display(self):
        """初始化时间显示"""
        # 创建定时器，每秒更新一次时间
        self.time_timer = QTimer(self)
        self.time_timer.timeout.connect(self.update_time_display)
        self.time_timer.start(1000)  # 1000毫秒 = 1秒

        # 立即更新一次
        self.update_time_display()

    # 日志控件
    def setup_log_widget(self):
        """设置日志控件"""
        # 设置只读模式
        self.plainTextEdit.setReadOnly(True)

        # 设置字体（等宽字体便于查看）
        font = self.plainTextEdit.font()
        font.setFamily("Consolas")
        font.setPointSize(10)
        self.plainTextEdit.setFont(font)

        # 设置样式（简洁的深色背景）
        self.plainTextEdit.setStyleSheet("""
            QPlainTextEdit {
                border: 1px solid #3c3c3c;
                border-radius: 3px;
                padding: 5px;
            }
        """)

        # 日志最大行数限制
        self.max_log_lines = 1000
        self.current_log_lines = 0

    def log_message(self, message: str):
        """
        记录系统日志消息（最新消息显示在顶部）

        Args:
            message: 日志消息内容
        """
        # 获取当前时间
        current_time = QDateTime.currentDateTime()
        time_str = current_time.toString("yyyy-MM-dd HH:mm:ss")

        # 格式化消息
        log_line = f"[{time_str}] {message}\n"

        # 获取当前文档
        doc = self.plainTextEdit.document()

        # 如果有内容且超过最大行数限制，删除最后一行
        if self.current_log_lines >= self.max_log_lines:
            # 删除最后一行
            cursor = self.plainTextEdit.textCursor()
            cursor.movePosition(cursor.End)
            cursor.select(QTextCursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()  # 删除换行符
            self.current_log_lines -= 1

        # 在开头插入新消息
        cursor = self.plainTextEdit.textCursor()
        cursor.movePosition(cursor.Start)
        cursor.insertText(log_line)

        # 更新行数计数
        self.current_log_lines += 1

        # 滚动到顶部（显示最新消息）
        self.plainTextEdit.ensureCursorVisible()
        self.plainTextEdit.moveCursor(QTextCursor.Start)

    def clear_log(self):
        """清空日志"""
        self.plainTextEdit.clear()
        self.current_log_lines = 0
        self.log_message("日志已清空")

    def show_passage_records(self):
        """显示通行记录管理界面"""
        if self.passage_record_dialog is None:
            from passage_record_dialog import PassageRecordDialog
            self.passage_record_dialog = PassageRecordDialog(self.passage_record_manager, self)
            self.passage_record_dialog.record_saved.connect(self.on_record_saved)

            # 显示并刷新数据
        self.passage_record_dialog.show_and_refresh()

    def on_record_created(self, mmsi):
        print(f"新通行记录创建: {mmsi}")

    def on_record_completed(self, mmsi):
        self.log_message(f"通行记录完成: {mmsi}")


    def on_record_saved(self, record):
        """记录保存后的处理"""
        print(f"记录已保存: {record}")

    # 在更新船舶位置时调用
    def update_ship_position(self, ship_info, position_info):
        """更新船舶位置时更新通行记录"""
        self.passage_record_manager.update_from_ship_manager(
            ship_info,
            in_reveal_area=position_info.get('in_up_reveal_area') or position_info.get('in_down_reveal_area'),
            in_control_area=position_info.get('in_control_area', False)
        )

    def update_time_display(self):
        """更新时间显示"""
        # 获取当前时间
        now = QDateTime.currentDateTime()

        # 格式化时间：年月日 时分秒 星期
        # 格式: 2024-01-15 14:30:25 星期三
        time_str = now.toString("yyyy-MM-dd HH:mm:ss dddd")

        # 更新标签
        self.label_time.setText(time_str)

        # 2. 判断是否开机超过2分钟
        if not self.is_open:
            elapsed = time.time() - self.startup_time
            if elapsed >= 120:  # 2分钟 = 120秒
                self.is_open = True
                print(f"✓ 程序已运行 {elapsed:.0f} 秒 ({elapsed / 60:.1f}分钟)，系统已就绪")

    def show_mqtt_widget(self):
        """显示MQTT界面"""
        if self.mqtt_widget.isVisible():
            # 如果已经显示，则激活并置前
            self.mqtt_widget.raise_()
            self.mqtt_widget.activateWindow()
        else:
            # 如果隐藏，则显示
            self.mqtt_widget.show()
            self.mqtt_widget.raise_()

    def loadMap(self):
        """加载HTML地图文件"""

        # 方法1：添加调试信息，确认路径是否正确
        current_dir = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(current_dir, 'map.html')

        print(f"当前目录: {current_dir}")
        print(f"HTML路径: {html_path}")
        print(f"文件是否存在: {os.path.exists(html_path)}")

        if os.path.exists(html_path):
            with open(html_path, 'r', encoding='utf-8') as f:
                print(f"文件内容（前100字符）: {f.read(100)}")
        else:
            print("文件不存在！")
            # 尝试创建测试文件
            test_html = """<!DOCTYPE html>
        <html>
        <head>
            <title>测试页面</title>
            <style>body { font-size: 20px; color: red; }</style>
        </head>
        <body>
            <h1>如果看到这个，说明HTML加载成功！</h1>
        </body>
        </html>"""
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(test_html)
            print(f"已创建测试文件: {html_path}")

        # 然后加载
        self.webView.load(QUrl.fromLocalFile(html_path))

        from map_ship_drawer import MapShipDrawer
        self.ship_drawer = MapShipDrawer(self.webView)



        # 当页面加载完成后，设置地图
        self.webView.loadFinished.connect(self.on_load_finished)

    def inject_webchannel_js(self):
        """注入 WebChannel 初始化 JavaScript"""
        # 确保 QWebChannel 脚本已加载
        js_code = """
        // 等待 QWebChannel 脚本加载
        (function() {
            if (typeof qt !== 'undefined' && qt.webChannelTransport) {
                console.log('qt.webChannelTransport 已存在');
                new QWebChannel(qt.webChannelTransport, function(channel) {
                    window.pyQtBridge = channel.objects.pyQtBridge;
                    console.log('WebChannel 初始化成功', window.pyQtBridge);

                    // 发送初始化完成信号
                    if (window.pyQtBridge) {
                        window.pyQtBridge.log('WebChannel 初始化完成');
                    }
                });
            } else {
                console.log('等待 qt.webChannelTransport...');
                setTimeout(arguments.callee, 100);
            }
        })();
        """

        self.webView.page().runJavaScript(js_code)

    def on_load_finished(self, ok):
        if ok:
            # 注入 WebChannel 初始化代码
            self.inject_webchannel_js()

            # 可选：发送测试消息
            self.webView.page().runJavaScript("""
                        if (typeof pyQtBridge !== 'undefined') {
                            console.log('WebChannel 初始化成功');
                            pyQtBridge.log('地图已就绪');
                        } else {
                            console.log('WebChannel 未初始化');
                        }
                    """)
            # 在这里进行你的初始化操作
            self.initialize_with_reach_data(self.controlRivername,self.reachCode)



        else:
            print("页面加载失败")


    def initLocalDB(self):
        """初始化数据库数据"""
        try:
            pass
            # #初始化mqtt账号密码
            # users = self.api.getMqttAdr()
            # if users:
            #    self.db_manager.update_by_single_condition('Internet',users[0],'netChoice','内网')
            #    self.db_manager.update_by_single_condition('Internet', users[1], 'netChoice', '外网')
            # network=self.config_mgr.get('InternetType')
            # #初始化河段信息
            # reaches=self.api.getAllReaches()
            # raechCodeList=[]
            # if reaches and reaches[0]:
            #     self.db_manager.delete_all("Reaches")
            #     for reach in reaches:
            #         raechCodeList.append(reach['ReachCode'])
            #         self.db_manager.insert_record("Reaches", reach)

            ##初始化围栏信息
            # FenceInfoAll = self.api.getFencesAll()
            # print(FenceInfoAll)
            # if FenceInfoAll and FenceInfoAll[0]:
            #     self.db_manager.delete_all("Fence")
            #     for FenceInfo in FenceInfoAll:
            #         dict= {'ReachCode': FenceInfo['ReachCode'], "ReachName": FenceInfo['ReachName']}
            #         if FenceInfo['TBQ']:
            #             for tbq in FenceInfo["TBQ"]:
            #                 dict["FenceType"]='停泊区'
            #                 for key, value in tbq.items():
            #                     dict["FenceName"] = key
            #                     dict['PointList'] = value
            #                 self.db_manager.insert_record("Fence", dict)
            #         if FenceInfo['TSQ']:
            #             for tbq in FenceInfo["TSQ"]:
            #                 dict["FenceType"]='特殊区'
            #                 for key, value in tbq.items():
            #                     dict["FenceName"]=key
            #                     dict['PointList']=value
            #                 self.db_manager.insert_record("Fence", dict)
            #         if FenceInfo['DDQ']:
            #             for tbq in FenceInfo["DDQ"]:
            #                 dict["FenceType"] = '等待区'
            #                 for key, value in tbq.items():
            #                     dict["FenceName"] = key
            #                     dict['PointList'] = value
            #                 self.db_manager.insert_record("Fence", dict)

            # ##初始化LED信息
            # for reachCode in raechCodeList:
            #     ledInfoAll=self.api.getLedInfoAll(reachCode)
            #     if ledInfoAll and ledInfoAll[0]:
            #         self.db_manager.delete_by_conditions('LedInfo',{"reachCode":reachCode})
            #         for ledInfo in ledInfoAll:
            #             dict={}
            #             dict['reachCode'] = reachCode
            #             dict['ledID'] = ledInfo['ledID']
            #             dict['ledName'] = ledInfo['ledName']
            #             dict['LEDPublish']=ledInfo['LEDPublish']
            #             dict['LEDReceive']=ledInfo['LEDReceive']
            #             self.db_manager.insert_record("LedInfo", dict)


            # #初始化LORA信息
            # for reachCode in raechCodeList:
            #     loraInfoAll=self.api.getLoraInforList(reachCode)
            #     if loraInfoAll and loraInfoAll[0]:
            #         self.db_manager.delete_by_conditions('LoraInfo', {"reachCode": reachCode})
            #         for loraInfo in loraInfoAll:
            #             dict = {}
            #             dict['reachCode'] = reachCode
            #             dict['LoRaID'] = loraInfo['LoRaID']
            #             dict['LoRaPlace'] = loraInfo['LoRaPlace']
            #             dict['LoRaPublish'] = loraInfo['LoRaPublish']
            #             dict['LoRaReceive'] = loraInfo['LoRaReceive']
            #             dict['InternetType'] = self.config_mgr.get('InternetType')
            #             self.db_manager.insert_record("LoraInfo", dict)

            # #初始化主题信息
            # for reachCode in raechCodeList:
            #     topicInfoAll = self.api.getReachTopics(reachCode)
            #     if topicInfoAll and topicInfoAll[0]:
            #         self.db_manager.delete_by_conditions('topic', {"reachCode": reachCode,"network":network})
            #         for topicInfo in topicInfoAll:
            #             dict = {}
            #             dict['reachCode'] = reachCode
            #             dict['type'] = topicInfo['type']
            #             dict['topic'] = topicInfo['topic']
            #             dict['network'] = network
            #             self.db_manager.insert_record("topic", dict)

        except Exception as e:
            print(f"执行错误: {e}")

    def load_reach_data(self,rivername):
        """
        从Reaches表查询ReachName和TeachCode，形成键值对并填充到comboBox
        """
        try:
            # 查询Reaches表中的ReachName和TeachCode
            query = "SELECT ReachName, ReachCode FROM Reaches"
            results = self.db_manager.fetch_all(query)

            # 创建字典存储ReachName -> TeachCode的映射
            self.reach_dict = {}  # 存储键值对，用于后续查找

            # 【关键】临时阻塞信号，防止添加项时触发选择事件
            self.comboBox.blockSignals(True)

            # 清空comboBox
            self.comboBox.clear()

            # 遍历查询结果
            for row in results:
                reach_name = row.get('ReachName')
                reach_code = row.get('ReachCode')

                if reach_name :
                    # 添加到字典
                    self.reach_dict[reach_name] = reach_code

                    # 添加到comboBox
                    self.comboBox.addItem(reach_name)

            print(f"成功加载 {len(self.reach_dict)} 条河段数据")
            # 【关键】恢复信号
            self.comboBox.blockSignals(False)

            # # 查找是否有匹配的河段
            # index = self.comboBox.findText(rivername)
            #
            # if index >= 0:
            #     # 找到匹配项，选中它
            #     self.comboBox.setCurrentText(rivername)
            #     print(f"已选择河段: {rivername}")
            # else:
            #     # 没有找到，默认选中第一个
            #     if self.comboBox.count() > 0:
            #         self.comboBox.setCurrentIndex(0)
            #         print(f"未找到河段 '{rivername}'，已默认选中: {self.comboBox.currentText()}")

        except Exception as e:
            print(f"加载河段数据失败: {e}")
            import traceback
            traceback.print_exc()



    def on_reach_selected(self, reach_name):
        """
        当comboBox选择变化时的处理函数

        Args:
            reach_name: 选择的河段名称
        """
        if not reach_name:
            return

        print(f"选择了河段: {reach_name}")

        # 根据选中的reach_name获取对应的reachCode
        self.controlRivername=reach_name
        self.reachCode = self.reach_dict.get(reach_name)
        self.config_mgr.set("controlRiverName", value=reach_name)
        self.config_mgr.set("reachCode", value=self.reachCode)
        self.config_mgr.save_config()

        if reach_name:
            print(f"对应的TeachCode: {self.reachCode}")

            # 1. 关闭并删除旧的 MQTT 控件
            if hasattr(self, 'mqtt_widget') and self.mqtt_widget:
                if hasattr(self.mqtt_widget, 'mqtt_manager'):
                    self.mqtt_widget.mqtt_manager.disconnect()
                self.mqtt_widget.deleteLater()


            self.loadMap()


        else:
            print(f"未找到河段 {reach_name} 对应的TeachCode")



    def initialize_with_reach_data(self, reach_name: str, teach_code: str):
        """
        根据选中的河段数据进行初始化操作

        Args:
            reach_name: 河段名称
            teach_code: 对应的TeachCode
        """
        global json
        print(f"开始初始化 - 河段: {reach_name}, TeachCode: {teach_code}")

        try:
            # 查询Reaches表
            query = """
                    SELECT ReachName,\
                        ReachCode,\
                            CenterP,\
                           UpBordLine, \
                           DownBordLine,
                           UpWhistle, \
                           DownWhistle,
                           UpCalculateRange, \
                           DownCalculateRange
                    FROM Reaches
                    WHERE ReachName = ?
                    """
            results = self.db_manager.fetch_all(query, (reach_name,))

            if not results:
                print(f"未找到河段: {reach_name}")
                return None

            row = results[0]

            # 解析地图中心点
            center_coords = row.get('CenterP', '')
            if center_coords:
                try:
                    lon,lat = center_coords.split(',')
                    center_point = ReachPoint(lat=float(lat), lon=float(lon))
                except:
                    # 如果解析失败，使用默认值
                    center_point = ReachPoint(lat=29.58, lon=106.65)
            else:
                center_point = ReachPoint(lat=29.58, lon=106.65)

            # 创建控制河段对象
            reach = ControlReach(
                reach_name=row['ReachName'],
                reach_code=row['ReachCode'],
                center_point=center_point
            )

            # 加载上下界限标
            if row.get('UpBordLine'):
                reach.up_bound_line = ReachLine.from_coords_str(row['UpBordLine'])
            if row.get('DownBordLine'):
                reach.down_bound_line = ReachLine.from_coords_str(row['DownBordLine'])

            # 加载上下鸣笛标
            if row.get('UpWhistle'):
                reach.up_whistle_line = ReachLine.from_coords_str(row['UpWhistle'])

            if row.get('DownWhistle'):
                try:
                    reach.down_whistle_line = ReachLine.from_coords_str(row['DownWhistle'])
                except:
                    pass

            # 加载上下水计算范围（多边形）
            if row.get('UpCalculateRange'):
                reach.up_calc_polygon = ReachPolygon.from_coords_str(row['UpCalculateRange'])
                if reach.up_calc_polygon:
                    print(f"上游计算范围: {len(reach.up_calc_polygon.points)} 个点")

            if row.get('DownCalculateRange'):
                reach.down_calc_polygon = ReachPolygon.from_coords_str(row['DownCalculateRange'])
                if reach.down_calc_polygon:
                    print(f"下游计算范围: {len(reach.down_calc_polygon.points)} 个点")

            # 加载围栏数据
            park_areas, special_areas = self.load_fences_for_reach(reach.reach_code)
            reach.park_areas = park_areas
            reach.special_areas = special_areas

            # 在函数末尾添加
            self.current_reach = reach  # 保存当前河段

           #根据界限标和鸣笛标区计算获取区域
            reach.__post_init__()


            # 加载航道里程线数据
            self.load_channel_mileage_for_reach(reach)

            # 1. 先清空队列管理器（切换到新河段）
            if hasattr(self, 'queue_manager'):
                cleared_count = self.queue_manager.clear_all_queues()
                print(f"已清空队列，共 {cleared_count} 艘船舶")

            # 创建新的MQTT控件
            self.mqtt_widget = MQTTControlWidget(api_service)
            # 设置窗口关闭事件（重写closeEvent，让关闭变成隐藏）
            self.mqtt_widget.setAttribute(Qt.WA_DeleteOnClose, False)  # 关闭时不删除对象
            self.mqtt_widget.setWindowFlags(self.mqtt_widget.windowFlags() | Qt.Window)  # 确保是独立窗口

            # 5. 设置新的 ShipManager
            from ship_manager import ShipManager
            self.mqtt_widget.ship_manager = ShipManager(
                self.api,
                self.mileage_manager,
                self.current_reach,
                self.queue_manager
            )

            # 连接MQTT控件的AIS信号
            self.mqtt_widget.ship_manager.ship_updated.connect(self.on_ais_ships_updated)
            self.mqtt_widget.ship_manager.ship_removed.connect(self.on_ais_ships_remove)
            self.mqtt_widget.ship_manager.update_queue_status.connect(self.update_queue_status)

            # 6. 连接 MQTT
            self.mqtt_widget.mqtt_manager.connect()
            self.load_mqtt_topic()

            print("MQTT 控件已重新创建并连接")


            #设置新的queue_manager
            self.queue_manager = QueueManager(self.passage_record_manager, self.get_current_signal, self.log_message,
                                              self.current_reach)


            # 初始化LED管理器
            self.led_manager = LEDManager(self.db_manager, self.mqtt_widget.mqtt_manager,self.log_message)


            # 加载LED灯
            self.load_leds_for_reach(self.reachCode)

            # LED连接状态监控定时器（每6分钟检查一次）
            self.led_check_timer = QTimer(self)
            self.led_check_timer.timeout.connect(self.check_led_connection_status)
            self.led_check_timer.start(60000)  # 1分钟 = 360000毫秒

            # # 连接LED状态信号
            # if hasattr(self, 'led_manager'):
            #     self.led_manager.led_connection_changed.connect(self.on_led_connected)
            #     self.led_manager.led_status_changed.connect(self.on_led_status_changed)

            self.start_queue_processor()
            self.current_signal = '关闭'  # 控制河段的信号

            js = f"setMapView({reach.center_point.lat}, {reach.center_point.lon}, {14});"
            self.webView.page().runJavaScript(js)
            print(f"设置地图中心: ")

            # 构建要绘制的数据
            reach_data = reach.to_dict()
            data_json = json.dumps(reach_data, ensure_ascii=False)

            js_code=f"""drawReach({data_json})"""
            self.webView.page().runJavaScript(js_code)
            print(f"河段 {reach.reach_name} 绘制完成")

            print(f"成功加载河段: {reach_name}")


            return None
        except Exception as e:
            print(f"加载河段数据失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def check_led_connection_status(self):
        """检查LED连接状态"""
        if hasattr(self, 'led_manager'):
            changed = self.led_manager.check_led_connections()
            if changed > 0:
                print(f"检测到 {changed} 个 LED 连接状态变化")



    def on_led_disconnected(self, led_id: str, led_name: str):
        """LED断开连接"""
        print(f"❌ LED {led_name} ({led_id}) 连接断开")
        self.log_message(f"LED {led_name} 连接断开，已关闭")

        # 更新LED控件显示（红色凸显）
        self._update_led_widget_style(led_id, connected=False)

    def on_led_status_changed(self, led_id: str, status: int):
        """LED状态变化"""
        # 更新LED控件显示
        self._update_led_widget_status(led_id, status)
        # 记录日志
        led = self.led_manager.leds.get(led_id)
        if led:
            status_texts = {0: "禁航", 1: "上水", 2: "下水", 3: "半杆", 4: "关闭"}
            self.log_message(f"LED状态变化: {led.led_name} -> {status_texts.get(status, '未知')}")

    def _update_led_widget_style(self, led_id: str, connected: bool):
        """更新LED控件样式"""
        for widget in self.led_widgets:
            if widget.led_info.led_id == led_id:
                if connected:
                    # 恢复正常样式
                    widget.name_label.setStyleSheet("""
                           font-size: 14px; 
                           font-weight: bold; 
                           color: #2c3e50;
                       """)
                else:
                    # 断开连接：红色凸显
                    widget.name_label.setStyleSheet("""
                           font-size: 14px; 
                           font-weight: bold; 
                           color: #e74c3c;
                           background-color: #ffebee;
                           border-radius: 4px;
                           padding: 2px 5px;
                       """)
                break

    def _update_led_widget_status(self, led_id: str, status: int):
        """更新LED控件状态显示"""
        for widget in self.led_widgets:
            if widget.led_info.led_id == led_id:
                widget.update_status_display(status)
                break
    def load_channel_mileage_for_reach(self, reach: ControlReach,
                                       upstream_count: int = 20,
                                       downstream_count: int = 10):
        """
        加载控制河段附近的航道里程线数据

        Args:
            reach: 控制河段对象
            upstream_count: 上游加载的里程线数量
            downstream_count: 下游加载的里程线数量
        """
        try:
            self.mileage_manager.load_from_db(self.db_manager)

            # 获取控制河段的上下界限标里程
            # 假设可以从Reaches表获取或根据坐标计算
            reach_km = self.get_reach_km(reach)

            # 查询数据库获取附近的航道里程线
            query = """
                    SELECT KM, Points \
                    FROM ChannelMileageLine
                    WHERE km BETWEEN ? AND ?
                    ORDER BY km
                    """

            # 计算里程范围（上游20个，下游10个，每个间隔1km）
            min_km = reach_km - upstream_count
            max_km = reach_km + downstream_count

            results = self.db_manager.fetch_all(query, (min_km, max_km))

            # 清空并重新加载里程线
            self.mileage_manager.mileage_lines.clear()

            for row in results:
                km = float(row['KM'])
                point_str = row['Points']

                # 解析坐标
                coords = self._parse_coordinates(point_str)
                if coords and len(coords) >= 4:
                    from channel_mileage import MileageLine
                    line = MileageLine(
                        km=km,
                        start_point=(coords[0], coords[1]),  # (lat, lon)
                        end_point=(coords[2], coords[3])
                    )
                    self.mileage_manager.mileage_lines[km] = line

            # 构建里程区域
            self.mileage_manager._build_mileage_regions()

            # 细分区域
            self.mileage_manager._subdivide_regions()


            #计算上界限标的中心点坐标
            lat=(reach.up_bound_line.start.lat+reach.up_bound_line.end.lat)/2
            lon=(reach.down_bound_line.start.lon+reach.down_bound_line.end.lon)/2

            self.mileage_manager.calculate_upBoardkm(lat,lon)

            # self.mileage_manager.visualize_subdivision()
            print(f"成功加载航道里程线: {len(self.mileage_manager.mileage_lines)} 条")
            print(f"里程范围: {min_km}km - {max_km}km")

        except Exception as e:
            print(f"加载航道里程线失败: {e}")
            import traceback
            traceback.print_exc()

    def _parse_coordinates(self, point_str: str):
        """解析坐标字符串"""
        try:
            parts = point_str.strip().split(',')
            return [float(p.strip()) for p in parts]
        except:
            return []



    def get_reach_km(self, reach: ControlReach) -> float:
        """
        获取控制河段对应的里程数

        Args:
            reach: 控制河段对象

        Returns:
            里程数（公里）
        """
        try:

            # 方法2：根据中心点坐标计算最近的里程线
            if hasattr(self, 'mileage_manager') and self.mileage_manager.mileage_lines:
                center = reach.center_point
                min_dist = float('inf')
                best_km = 0

                for km, line in self.mileage_manager.mileage_lines.items():
                    # 计算中心点到里程线的距离
                    from channel_mileage import point_to_line_distance
                    dist = point_to_line_distance(
                        (center.lat, center.lon),
                        line.start_point,
                        line.end_point
                    )
                    if dist < min_dist:
                        min_dist = dist
                        best_km = km

                return best_km

            # 默认值
            return 0

        except Exception as e:
            print(f"获取河段里程失败: {e}")
            return 0

    def load_fences_for_reach(self, reach_code: str) -> Tuple[List[FenceArea], List[FenceArea]]:
        """
        根据河段代码加载围栏数据（停泊区和特殊区）

        Args:
            reach_code: 河段代码

        Returns:
            (park_areas, special_areas) 元组
        """
        park_areas = []
        special_areas = []

        try:
            # 查询fence表
            query = """
                    SELECT  FenceName, FenceType, PointList FROM Fence WHERE ReachCode = ? \
                    """
            results = self.db_manager.fetch_all(query, (reach_code,))

            for row in results:
                fence_area = FenceArea.from_db_row(row)
                if fence_area:
                    if fence_area.fence_type == '停泊区':
                        park_areas.append(fence_area)
                    elif fence_area.fence_type == '特殊区':
                        special_areas.append(fence_area)

            print(f"河段 {reach_code}: 加载了 {len(park_areas)} 个停泊区, {len(special_areas)} 个特殊区")

        except Exception as e:
            print(f"加载围栏数据失败: {e}")
            import traceback
            traceback.print_exc()

        return park_areas, special_areas

    def load_mqtt_topic(self):
        """
        将从数据库读取相应的控制河段主题添加到MQTT类中。

        返回:
            解码后的坐标列表，如果字符串无效或为空则返回空列表。
        """

        topics=self.db_manager.search_records("topic",{'type':"AIS","network":self.network,"reachCode":self.reachCode})
        if topics:
            for topic in topics:
                self.mqtt_widget.mqtt_manager.ais_topics.append(topic.get('topic'))
                self.mqtt_widget.mqtt_manager.subscribe(topic.get('topic'))
        topics = self.db_manager.search_records("topic",{'type': "PLC", "network": self.network, "reachCode": self.reachCode})
        if topics:
            for topic in topics:
                self.mqtt_widget.mqtt_manager.plc_topics.append(topic.get('topic'))

    def cleanup_expired_ships(self):
        """清理过期船舶"""
        removed = self.queue_manager.clean_expired_ships()
        if removed > 0:
            print(f"清理了 {removed} 艘过期船舶")


    def update_pending_table(self,ships):
        """更新待指挥队列表格"""

        # 设置表格列数
        columns = 6
        self.tableWidget_pending.setColumnCount(columns)

        # 设置表头
        headers = [ "船名", "航向", "实时时间", "拟揭示信号", "是否到位", "抵达时间"]
        self.tableWidget_pending.setHorizontalHeaderLabels(headers)

        # 设置行数
        self.tableWidget_pending.setRowCount(len(ships))

        # 设置表格属性
        self.tableWidget_pending.setAlternatingRowColors(True)
        self.tableWidget_pending.setSortingEnabled(False)

        # 关键：设置列拉伸模式，让列填满整个表格
        header = self.tableWidget_pending.horizontalHeader()

        # 设置所有列按比例拉伸
        header.setSectionResizeMode(QHeaderView.Stretch)

        # 或者设置特定列拉伸，其他列固定宽度
        # header.setSectionResizeMode(0, QHeaderView.ResizeToContents)  # 排序序号自适应内容
        # header.setSectionResizeMode(1, QHeaderView.Stretch)  # 船名拉伸
        # header.setSectionResizeMode(2, QHeaderView.Stretch)  # 航向拉伸
        # header.setSectionResizeMode(3, QHeaderView.Stretch)  # 实时时间拉伸
        # header.setSectionResizeMode(4, QHeaderView.Stretch)  # 拟揭示信号拉伸
        # header.setSectionResizeMode(5, QHeaderView.ResizeToContents)  # 是否到位自适应
        # header.setSectionResizeMode(6, QHeaderView.Stretch)  # 抵达时间拉伸

        # 填充数据
        for row, ship in enumerate(ships):
            # 排序序号
            seq_item = QTableWidgetItem(str(row + 1))
            seq_item.setTextAlignment(Qt.AlignCenter)
            self.tableWidget_pending.setItem(row, 0, seq_item)

            # 船名
            name_item = QTableWidgetItem(ship.get('name', '未知'))
            name_item.setTextAlignment(Qt.AlignCenter)
            self.tableWidget_pending.setItem(row, 0, name_item)

            # 航向（上下水方向）
            direction = ship.get('status', 'unknown')
            direction_text = "上水" if direction == 'up' else "下水" if direction == 'down' else "未知"
            dir_item = QTableWidgetItem(direction_text)
            dir_item.setTextAlignment(Qt.AlignCenter)
            # 根据方向设置颜色
            if direction == 'up':
                dir_item.setBackground(QBrush(QColor(200, 230, 255)))  # 浅蓝色
            elif direction == 'down':
                dir_item.setBackground(QBrush(QColor(255, 200, 200)))  # 浅红色
            self.tableWidget_pending.setItem(row, 1, dir_item)

            # 实时时间（到达上界限标所需时间）
            time_minutes = ship.get('time_minutes', 0)
            if time_minutes > 0:
                time_text = f"{time_minutes:.1f}"
            else:
                time_text = "--"
            time_item = QTableWidgetItem(time_text)
            time_item.setTextAlignment(Qt.AlignCenter)
            # 时间小于3分钟时高亮显示
            if 0 < time_minutes < 3:
                time_item.setBackground(QBrush(QColor(255, 200, 100)))  # 橙色高亮
            self.tableWidget_pending.setItem(row, 2, time_item)

            # 拟揭示信号
            calc_range = ship.get('calc_range', '')
            signal_text = "上水" if calc_range == 'up' else "下水" if calc_range == 'down' else "-"
            signal_item = QTableWidgetItem(signal_text)
            signal_item.setTextAlignment(Qt.AlignCenter)
            self.tableWidget_pending.setItem(row, 3, signal_item)

            # 是否到位（是否到达揭示区域内）
            is_arrived = ship.get('is_arrived', False)
            arrival_time=ship.get('arrival_time', 0)
            diff_time=0
            if is_arrived:
                diff_time=(time.time()-arrival_time)/60
            arrived_text =f"是（{diff_time:.1f}）" if is_arrived else "否"
            arrived_item = QTableWidgetItem(arrived_text)
            arrived_item.setTextAlignment(Qt.AlignCenter)
            if is_arrived:
                arrived_item.setBackground(QBrush(QColor(200, 255, 200)))  # 浅绿色
            self.tableWidget_pending.setItem(row, 4, arrived_item)

            # 抵达时间（到达上界限标所需时间，与实时时间相同或已到达的分钟数）

            arrived_minutes = ship.get('arrived_minutes', 0)
            arrive_text = f"{arrived_minutes:.1f}"

            arrive_item = QTableWidgetItem(arrive_text)
            arrive_item.setTextAlignment(Qt.AlignCenter)
            self.tableWidget_pending.setItem(row, 5, arrive_item)

        # 调整行高
        for row in range(len(ships)):
            self.tableWidget_pending.setRowHeight(row, 30)

        print(f"待指挥队列表格已更新: {len(ships)} 艘")

    def update_commanded_table(self, ships):
        """更新已指挥队列表格"""
        # 设置列数
        columns = 4
        self.tableWidget_command.setColumnCount(columns)

        # 设置表头
        headers = ["船名", "航向", "时间(分)",'信号']
        self.tableWidget_command.setHorizontalHeaderLabels(headers)

        # 设置行数
        self.tableWidget_command.setRowCount(len(ships))

        # 关键：设置列拉伸模式，让列填满整个表格
        header = self.tableWidget_command.horizontalHeader()

        # 设置所有列按比例拉伸
        header.setSectionResizeMode(QHeaderView.Stretch)

        # 设置表格属性
        self.tableWidget_command.setAlternatingRowColors(True)
        self.tableWidget_command.setSortingEnabled(False)
        self.tableWidget_command.setSelectionBehavior(QTableWidget.SelectRows)


        # 填充数据
        for row, ship in enumerate(ships):
            from PyQt5.QtGui import QBrush, QColor


            # 1. 船名
            name = ship.get('name', '未知')
            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignCenter)
            name_item.setToolTip(f"MMSI: {ship.get('mmsi', '')}")
            self.tableWidget_command.setItem(row, 0, name_item)

            # 2. 航向
            direction = ship.get('status', 'unknown')
            direction_text = "上水" if direction == 'up' else "下水" if direction == 'down' else "未知"
            dir_item = QTableWidgetItem(direction_text)
            dir_item.setTextAlignment(Qt.AlignCenter)
            if direction == 'up':
                dir_item.setBackground(QBrush(QColor(200, 230, 255)))
            elif direction == 'down':
                dir_item.setBackground(QBrush(QColor(255, 200, 200)))
            self.tableWidget_command.setItem(row, 1, dir_item)



            # 3. 揭示时间（已过去分钟数）
            elapsed_minutes = ship.get('elapsed_minutes', 0)
            elapsed_text = f"{elapsed_minutes:.1f}" if elapsed_minutes > 0 else "-"
            elapsed_item = QTableWidgetItem(elapsed_text)
            elapsed_item.setTextAlignment(Qt.AlignCenter)
            # 超过20分钟警告
            if elapsed_minutes > 20:
                elapsed_item.setBackground(QBrush(QColor(255, 200, 200)))
            self.tableWidget_command.setItem(row, 2, elapsed_item)

            # 6. 揭示信号
            calc_range = ship.get('calc_range', '')
            signal_text = "上水" if calc_range == 'up' else "下水" if calc_range == 'down' else "-"
            signal_item = QTableWidgetItem(signal_text)
            signal_item.setTextAlignment(Qt.AlignCenter)
            self.tableWidget_command.setItem(row, 3, signal_item)


        # 调整行高
        for row in range(len(ships)):
            self.tableWidget_command.setRowHeight(row, 35)

        print(f"已指挥队列表格已更新: {len(ships)} 艘")

    def update_control_area_table(self, ships):
        """更新控制河段队列表格"""
        # 设置列数
        columns = 4
        self.tableWidget_control.setColumnCount(columns)

        # 设置表头
        headers = [ "船名", "航向", "进入时间", "已停留(分)"]
        self.tableWidget_control.setHorizontalHeaderLabels(headers)

        # 设置行数
        self.tableWidget_control.setRowCount(len(ships))

        # 设置表格属性
        self.tableWidget_control.setAlternatingRowColors(True)
        self.tableWidget_control.setSortingEnabled(False)
        self.tableWidget_control.setSelectionBehavior(QTableWidget.SelectRows)

        # 关键：设置列拉伸模式，让列填满整个表格
        header = self.tableWidget_control.horizontalHeader()

        # 设置所有列按比例拉伸
        header.setSectionResizeMode(QHeaderView.Stretch)

        # 填充数据
        current_time = time.time()
        for row, ship in enumerate(ships):
            from PyQt5.QtGui import QBrush, QColor



            # 2. 船名
            name = ship.get('name', '未知')
            name_item = QTableWidgetItem(name)
            name_item.setTextAlignment(Qt.AlignCenter)
            name_item.setToolTip(f"MMSI: {ship.get('mmsi', '')}")
            self.tableWidget_control.setItem(row, 0, name_item)

            # 3. 航向
            direction = ship.get('status', 'unknown')
            direction_text = "上水" if direction == 'up' else "下水" if direction == 'down' else "未知"
            dir_item = QTableWidgetItem(direction_text)
            dir_item.setTextAlignment(Qt.AlignCenter)
            if direction == 'up':
                dir_item.setBackground(QBrush(QColor(200, 230, 255)))
            elif direction == 'down':
                dir_item.setBackground(QBrush(QColor(255, 200, 200)))
            self.tableWidget_control.setItem(row, 1, dir_item)

            # 4. 进入时间
            enter_time = ship.get('enter_channel_time', 0)
            if enter_time > 0:
                time_str = datetime.fromtimestamp(enter_time).strftime('%H:%M:%S')
                enter_time_item = QTableWidgetItem(time_str)
            else:
                enter_time_item = QTableWidgetItem("-")
            enter_time_item.setTextAlignment(Qt.AlignCenter)
            self.tableWidget_control.setItem(row, 2, enter_time_item)

            # 5. 已停留时间（分钟）
            if enter_time > 0:
                elapsed_minutes = (current_time - enter_time) / 60
                elapsed_text = f"{elapsed_minutes:.1f}"
                elapsed_item = QTableWidgetItem(elapsed_text)
                # 停留时间过长警告
                if elapsed_minutes > 30:
                    elapsed_item.setBackground(QBrush(QColor(255, 200, 200)))
                elif elapsed_minutes > 15:
                    elapsed_item.setBackground(QBrush(QColor(255, 235, 180)))
            else:
                elapsed_item = QTableWidgetItem("-")
            elapsed_item.setTextAlignment(Qt.AlignCenter)
            self.tableWidget_control.setItem(row, 3, elapsed_item)

        # 调整行高
        for row in range(len(ships)):
            self.tableWidget_control.setRowHeight(row, 35)

        print(f"控制河段队列表格已更新: {len(ships)} 艘")

    def on_ais_ships_updated(self, ships):
        """AIS船舶数据更新时的处理"""
        if self.ship_drawer:
            # 批量绘制船舶
            self.ship_drawer.draw_ship(ships)

    def on_ais_ships_remove(self,mmsi):
        """船舶过期删除船舶图标"""
        if self.ship_drawer:
            # 批量绘制船舶
            self.ship_drawer.remove_ship(mmsi)

    def on_ship_data_changed(self, data_str: str):
        """
        处理船舶信息修改

        Args:
            data_str: JSON格式的船舶更新数据
        """
        try:
            import json
            data = json.loads(data_str)

            mmsi = data.get('MMSI')
            new_name = data.get('name')
            new_status = data.get('status')

            print(f"收到船舶信息修改: MMSI={mmsi}, 名称={new_name}, 状态={new_status}")

            # 更新本地数据库中的船舶名称
            if hasattr(self, 'db_manager'):
                # 更新 ShipName 表
                self.db_manager.update_single_field(
                    "ShipName",
                    "ShipName",
                    new_name,
                    {"MMSI": mmsi}
                )
                #接口更新船名

                print(f"已更新数据库中的船舶名称: {mmsi} -> {new_name}")


            # 更新船舶管理器中的船舶信息
            if hasattr(self, 'mqtt_widget') :
                ship = self.mqtt_widget.ship_manager.ships.get(mmsi)
                if ship:
                    ship.name = new_name
                    ship.status = new_status

                    # 根据状态更新方向
                    if new_status == 'up':
                        ship.shipType = 'up'
                    elif new_status == 'down':
                        ship.shipType = 'down'
                    elif new_status == 'docked':
                        ship.shipType = 'docked'
                    elif new_status == 'special':
                        ship.shipType = 'special'

                    self.mqtt_widget.ship_manager.ships[mmsi] = ship
                    print(f"已更新船舶管理器中的信息: {mmsi}")

            # 更新队列管理器中的船舶信息
            if hasattr(self, 'queue_manager') and self.queue_manager:
                # 更新待指挥队列中的船舶信息
                if mmsi in self.queue_manager.pending_queue:
                    self.queue_manager.pending_queue[mmsi]['name'] = new_name
                    self.queue_manager.pending_queue[mmsi]['status'] = new_status


                # 更新已指挥队列中的船舶信息
                if mmsi in self.queue_manager.commanded_queue:
                    self.queue_manager.commanded_queue[mmsi]['name'] = new_name
                    self.queue_manager.commanded_queue[mmsi]['status'] = new_status


                # 更新控制区域队列中的船舶信息
                if mmsi in self.queue_manager.control_area_queue:
                    self.queue_manager.control_area_queue[mmsi]['name'] = new_name
                    self.queue_manager.control_area_queue[mmsi]['status'] = new_status



        except Exception as e:
            print(f"处理船舶信息修改失败: {e}")
            import traceback
            traceback.print_exc()


    def update_queue_status(self,mmsi,ship_info: ShipInfo, channel_position: dict, crossing_result: dict):
        """更新船舶在队列中的状态"""

        #位置字典的关键字
        # estimated_km 估计的里程数
        # in_special 是否在特殊区
        # in_up_calc_range 是否在上水区域
        # in_down_calc_range 是否在下水区域
        # in_control_area 是否在控制河段区域
        # in_up_reveal_area 是否在上水揭示区域
        # in_down_reveal_area 是否在下水揭示区域
        #time_minutes 到达上界限标所需时间

        #开机时间没超过两分钟，不对船舶队列进行更新和指挥判断
        if not self.is_open:
            return


        #判断船舶是否在计算范围区域内
        if ship_info.calc_range or channel_position.get('in_control_area',False) or channel_position.get('in_up_reveal_area',False) or channel_position.get('in_down_reveal_area',False):
            #如果船舶在上下水计算范围区域内，需要将船舶信息转化为队列信息
            # 构建队列用的船舶信息
            queue_ship_info = {
                'mmsi': mmsi,
                'name': ship_info.name,
                'lat': ship_info.latitude,
                'lon': ship_info.longitude,
                'heading': ship_info.heading,
                'speed': ship_info.speed,
                'status': ship_info.status,
                'in_up_calc': channel_position.get('in_up_calc_range', False),
                'in_down_calc': channel_position.get('in_down_calc_range', False),
                'in_control_area': channel_position.get('in_control_area', False),
                'in_park': channel_position.get('in_park', False),
                'estimated_km': channel_position.get('estimated_km'),
                'time_minutes': channel_position.get('time_minutes'),#到达上界限标所需的时间
                'is_arrived': ship_info.is_arrived,#是否到达揭示区域
                'arrival_time': ship_info.arrival_time,#船舶到达揭示区域的时间
                'timestamp': time.time(),
                # 添加跨线检测结果
                'cross_up_whistle': crossing_result.get('cross_up_whistle', False) if crossing_result else False,
                'cross_down_whistle': crossing_result.get('cross_down_whistle', False) if crossing_result else False,
                'cross_up_bound': crossing_result.get('cross_up_bound', False) if crossing_result else False,
                'cross_down_bound': crossing_result.get('cross_down_bound', False) if crossing_result else False
            }

            # 调用队列管理器更新状态
            self.queue_manager.update_ship_queue_status(
                mmsi=mmsi,
                ship_info=queue_ship_info,
                in_up_calc=queue_ship_info['in_up_calc'],
                in_down_calc=queue_ship_info['in_down_calc'],
                in_control_area=queue_ship_info['in_control_area'],
                in_park=queue_ship_info['in_park']
            )








if __name__ == "__main__":
    app = QApplication(sys.argv)
    app.setStyle('Fusion')
    app.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    app.setAttribute(Qt.AA_UseHighDpiPixmaps, True)
    # 在程序入口（创建 QApplication 后）添加：
    os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = '9222'
    # # 创建登录对话框（不创建主窗口）
    # login_dialog = LoginDialog()
    # # 定义登录成功后的回调函数
    # def on_login_success(api_service, username):
    #     """登录成功后创建并显示主窗口"""
    #
    #     main_window = MainWindow(api_service, username)
    #     main_window.show()
    #     login_dialog.close()
    #
    #     # 连接登录成功信号
    #
    # # 先信号与槽连接，在展示对话框
    # login_dialog.login_success.connect(on_login_success)
    #
    # # 显示登录对话框
    # login_dialog.show()

    api_service = APIService("http://isc.cqu.edu.cn:23456")
    api_service.login("梁山","Cqhdj@2024")
    main_window = MainWindow(api_service, "username")
    main_window.show()



    # 进入事件循环
    sys.exit(app.exec_())
   

