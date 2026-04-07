import base64
import json
import sys
import time
from typing import Tuple, List

import folium
import tempfile
import os

from PyQt5.QtWebEngineWidgets import QWebEngineSettings

from APIManager import APIManager,APIService
from mapBridge import MapBridge
from mileage_region_manager import MileageRegionManager
from passage_record_edit_dialog import PassageRecordEditDialog
from passage_record_manager import PassageRecordManager
from queue_manager import QueueManager
from ship_manager import ShipInfo
from sqlite3Manager import SQLiteTableManager

# 或者禁用硬件加速
os.environ["QT_WEBENGINE_DISABLE_GPU"] = "1"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"

from PyQt5.QtWidgets import (QApplication, QMainWindow, QWidget,
                             QVBoxLayout, QHBoxLayout, QPushButton,
                             QLineEdit, QLabel, QMessageBox)
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

        # 创建MQTT控件
        self.mqtt_widget = MQTTControlWidget(api_service)
        # 设置窗口关闭事件（重写closeEvent，让关闭变成隐藏）
        self.mqtt_widget.setAttribute(Qt.WA_DeleteOnClose, False)  # 关闭时不删除对象
        self.mqtt_widget.setWindowFlags(self.mqtt_widget.windowFlags() | Qt.Window)  # 确保是独立窗口

       
        # 连接按钮信号
        self.mqtt_btn.clicked.connect(self.show_mqtt_widget)


        #创建地图船舶绘制器
        self.ship_drawer = None

        # 连接MQTT控件的AIS信号
        self.mqtt_widget.ship_manager.ship_updated.connect(self.on_ais_ships_updated)
        self.mqtt_widget.ship_manager.ship_removed.connect(self.on_ais_ships_remove)
        self.mqtt_widget.ship_manager.update_queue_status.connect(self.update_queue_status)

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

        # 设置定时器自动清理
        self.cleanup_timer_record = QTimer()
        self.cleanup_timer_record.timeout.connect(self.passage_record_manager.auto_cleanup)
        self.cleanup_timer_record.start(3600000)  # 每小时清理一次
        self.record_btn.clicked.connect(self.show_passage_records)

        # 创建队列管理器
        from queue_manager import QueueManager
        self.queue_manager = QueueManager(self.passage_record_manager)

        # 连接队列变化信号到表格更新
        self.queue_manager.pending_queue_changed.connect(self.update_pending_table)
        self.queue_manager.commanded_queue_changed.connect(self.update_commanded_table)
        self.queue_manager.control_area_queue_changed.connect(self.update_control_area_table)

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

        self.loadMap()

        # 设置 WebChannel
        self.setup_web_channel()



        # self.mqtt_widget.show()

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
        记录系统日志消息

        Args:
            message: 日志消息内容
        """
        # 获取当前时间
        current_time = QDateTime.currentDateTime()
        time_str = current_time.toString("yyyy-MM-dd HH:mm:ss")

        # 格式化消息
        log_line = f"[{time_str}] {message}\n"

        # 获取当前文本光标
        cursor = self.plainTextEdit.textCursor()
        cursor.movePosition(cursor.End)

        # 插入文本
        cursor.insertText(log_line)

        # 更新行数计数
        self.current_log_lines += 1

        # 如果超过最大行数，删除最前面的行
        if self.current_log_lines > self.max_log_lines:
            # 获取文档
            doc = self.plainTextEdit.document()
            # 删除第一行
            cursor = self.plainTextEdit.textCursor()
            cursor.movePosition(cursor.Start)
            cursor.select(cursor.BlockUnderCursor)
            cursor.removeSelectedText()
            cursor.deleteChar()  # 删除换行符
            self.current_log_lines -= 1

        # 自动滚动到底部
        self.plainTextEdit.ensureCursorVisible()

    def clear_log(self):
        """清空日志"""
        self.plainTextEdit.clear()
        self.current_log_lines = 0
        self.log_message("日志已清空")

    def show_passage_records(self):
        """显示通行记录管理界面"""
        from passage_record_dialog import PassageRecordDialog
        dialog = PassageRecordDialog(self.passage_record_manager, self)
        dialog.record_saved.connect(self.on_record_saved)
        dialog.exec_()

    def on_record_created(self, mmsi):
        print(f"新通行记录创建: {mmsi}")

    def on_record_completed(self, mmsi):
        print(f"通行记录完成: {mmsi}")


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

        # 当页面加载完成后，设置地图中心点和缩放
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
            river=self.db_manager.search_records("Reaches",{"ReachCode":self.reachCode})
            # 使用 split() 分割字符串
            longitude, latitude = river[0].get("CenterP").split(',')
            self.comboBox.setCurrentText("0")
            self.comboBox.setCurrentText(river[0].get("ReachName"))
            js = f"setMapView({latitude}, {longitude}, {14});"
            self.webView.page().runJavaScript(js)
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

            # 在这里进行你的初始化操作
            self.initialize_with_reach_data(reach_name, self.reachCode)
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

           #根据界限标和鸣笛标区计算获取区域
            reach.__post_init__()


            # 加载航道里程线数据
            self.load_channel_mileage_for_reach(reach)

            # 1. 先清空队列管理器（切换到新河段）
            if hasattr(self, 'queue_manager'):
                cleared_count = self.queue_manager.clear_all_queues()
                print(f"已清空队列，共 {cleared_count} 艘船舶")

            # 创建或更新ShipManager
            if not hasattr(self.mqtt_widget, 'ship_manager'):
                from ship_manager import ShipManager
                self.mqtt_widget.ship_manager = ShipManager(self.api,self.mileage_manager,reach,self.queue_manager)  # 传入依赖

            else:
                self.mqtt_widget.ship_manager.set_mileage_manager(self.mileage_manager,reach,self.queue_manager)  # 更新依赖

            # 在函数末尾添加
            self.current_reach = reach  # 保存当前河段



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
            self.load_mqtt_topic()
            return None


        except Exception as e:
            print(f"加载河段数据失败: {e}")
            import traceback
            traceback.print_exc()
            return None

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

    def update_pending_table(self):
        """更新待指挥队列表格"""
        ships = self.queue_manager.get_pending_list()
        # 在这里更新你的表格显示
        print(f"待指挥队列: {len(ships)} 艘")
        for ship in ships:
            print(f"  - {ship.get('name')} ({ship.get('mmsi')}) {ship.get('calc_range')}")

    def update_commanded_table(self):
        """更新已指挥队列表格"""
        ships = self.queue_manager.get_commanded_list()
        print(f"已指挥队列: {len(ships)} 艘")

    def update_control_area_table(self):
        """更新控制河段区域队列表格"""
        ships = self.queue_manager.get_control_area_list()
        print(f"控制河段区域: {len(ships)} 艘")

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
                    self.queue_manager.pending_queue_changed.emit()

                # 更新已指挥队列中的船舶信息
                if mmsi in self.queue_manager.commanded_queue:
                    self.queue_manager.commanded_queue[mmsi]['name'] = new_name
                    self.queue_manager.commanded_queue[mmsi]['status'] = new_status
                    self.queue_manager.commanded_queue_changed.emit()

                # 更新控制区域队列中的船舶信息
                if mmsi in self.queue_manager.control_area_queue:
                    self.queue_manager.control_area_queue[mmsi]['name'] = new_name
                    self.queue_manager.control_area_queue[mmsi]['status'] = new_status
                    self.queue_manager.control_area_queue_changed.emit()


        except Exception as e:
            print(f"处理船舶信息修改失败: {e}")
            import traceback
            traceback.print_exc()


    def update_queue_status(self,mmsi,ship_info: ShipInfo, channel_position: dict):
        """更新船舶在队列中的状态"""

        #判断船舶是否在计算范围区域内

        # 构建队列用的船舶信息
        queue_ship_info = {
            'mmsi': mmsi,
            'name': ship_info.name,
            'lat': ship_info.latitude,
            'lon': ship_info.longitude,
            'heading': ship_info.heading,
            'speed': ship_info.speed,
            'direction': ship_info.direction,
            'in_up_calc': channel_position.get('in_up_calc_range', False),
            'in_down_calc': channel_position.get('in_down_calc_range', False),
            'in_control_area': channel_position.get('in_control_area', False),
            'in_park': channel_position.get('in_park', False),
            'estimated_km': channel_position.get('estimated_km'),
            'timestamp': time.time()
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
   

