# mqtt_widget.py
import json
import sys
from typing import Any

from PyQt5.QtWidgets import *
from PyQt5.QtCore import *
from PyQt5.QtGui import *

from config import ConfigManager
from mqtt_manager import MQTTManager
from sqlite3Manager import SQLiteTableManager


class MQTTControlWidget(QWidget):
    """MQTT控制Widget - 可嵌入其他界面"""
    # 自定义信号
    mqtt_connected = pyqtSignal()
    mqtt_disconnected = pyqtSignal()
    new_message_received = pyqtSignal(str, str)  # topic, message



    # 添加新信号
    ais_ships_updated = pyqtSignal(dict)  # 船舶列表更新信号


    def __init__(self, api_service,parent=None):
        super().__init__(parent)

        self.mqtt_manager = MQTTManager()
        self.db_manager = None
        # 初始化配置管理器
        self.config_mgr = ConfigManager()

        # 添加船舶管理器
        from ship_manager import ShipManager
        self.ship_manager = ShipManager(api_service)

        self.init_db()
        self.init_ui()
        self.connect_signals()
        self.mqtt_manager.connect()




        # 添加定时器，定期清理离线船舶
        self.cleanup_timer = QTimer()
        self.cleanup_timer.timeout.connect(self.cleanup_offline_ships)
        self.cleanup_timer.start(60000*5)  # 每5分钟检查一次


    def init_db(self):
        """连接本地数据库读取MQTT配置"""
        # MQTT连接的配置信息,读取数据库的信息
        # 创建管理器实例
        self.db_manager = SQLiteTableManager("test.db")
        # 连接到数据库
        if self.db_manager.connect():
            results = self.db_manager.search_records("Internet", {"netChoice": self.config_mgr.get("InternetType")})
            if results:
                self.mqtt_manager.config.broker_ip = results[0]["address"]
                self.mqtt_manager.config.port =int(results[0]["Port"])
                self.mqtt_manager.config.username = results[0]["Account"]
                self.mqtt_manager.config.password = results[0]["Psw"]

    def init_ui(self):
        """初始化界面"""
        # 主布局
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(5, 5, 5, 5)
        main_layout.setSpacing(5)

        # 1. 连接配置组
        config_group = QGroupBox("MQTT连接配置")
        config_group.setMaximumHeight(180)
        config_layout = QGridLayout()

        # IP地址
        config_layout.addWidget(QLabel("IP地址:"), 0, 0)
        self.ip_input = QLineEdit()
        self.ip_input.setText(self.mqtt_manager.config.broker_ip)
        config_layout.addWidget(self.ip_input, 0, 1)

        # 端口
        config_layout.addWidget(QLabel("端口:"), 0, 2)
        self.port_input = QSpinBox()
        self.port_input.setRange(1, 65535)
        self.port_input.setValue(self.mqtt_manager.config.port)
        config_layout.addWidget(self.port_input, 0, 3)

        # 用户名
        config_layout.addWidget(QLabel("用户名:"), 1, 0)
        self.username_input = QLineEdit()
        self.username_input.setPlaceholderText("可选")
        self.username_input.setText(self.mqtt_manager.config.username)
        config_layout.addWidget(self.username_input, 1, 1)

        # 密码
        config_layout.addWidget(QLabel("密码:"), 1, 2)
        self.password_input = QLineEdit()
        self.password_input.setEchoMode(QLineEdit.Password)
        self.password_input.setText(self.mqtt_manager.config.password)
        config_layout.addWidget(self.password_input, 1, 3)

        # 连接/断开按钮
        self.connect_btn = QPushButton("连接")
        self.connect_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")

        self.reconnect_btn = QPushButton("重连")
        self.reconnect_btn.setEnabled(False)

        button_layout = QHBoxLayout()
        button_layout.addWidget(self.connect_btn)
        button_layout.addWidget(self.reconnect_btn)
        button_layout.addStretch()

        config_layout.addLayout(button_layout, 2, 0, 1, 4)

        # 连接状态指示器
        self.status_label = QLabel("状态: 未连接")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")
        config_layout.addWidget(self.status_label, 3, 0, 1, 4)

        config_group.setLayout(config_layout)
        main_layout.addWidget(config_group)

        # 2. 订阅管理组
        subscribe_group = QGroupBox("主题订阅管理")
        subscribe_layout = QVBoxLayout()

        # 已订阅主题列表
        sub_top_layout = QHBoxLayout()
        sub_top_layout.addWidget(QLabel("已订阅主题:"))
        self.topic_combo = QComboBox()
        self.topic_combo.setMinimumWidth(200)
        sub_top_layout.addWidget(self.topic_combo, 1)

        # 取消订阅按钮
        self.unsubscribe_btn = QPushButton("取消订阅")
        self.unsubscribe_btn.setEnabled(False)
        sub_top_layout.addWidget(self.unsubscribe_btn)

        subscribe_layout.addLayout(sub_top_layout)

        # 添加新订阅
        sub_bottom_layout = QHBoxLayout()
        sub_bottom_layout.addWidget(QLabel("新主题:"))
        self.new_topic_input = QLineEdit()
        self.new_topic_input.setPlaceholderText("输入要订阅的主题，如: sensor/temperature")
        sub_bottom_layout.addWidget(self.new_topic_input, 1)

        # QoS选择
        sub_bottom_layout.addWidget(QLabel("QoS:"))
        self.qos_combo = QComboBox()
        self.qos_combo.addItems(["0", "1", "2"])
        self.qos_combo.setCurrentIndex(0)
        sub_bottom_layout.addWidget(self.qos_combo)

        # 订阅按钮
        self.subscribe_btn = QPushButton("订阅")
        self.subscribe_btn.setEnabled(False)
        sub_bottom_layout.addWidget(self.subscribe_btn)

        subscribe_layout.addLayout(sub_bottom_layout)
        subscribe_group.setLayout(subscribe_layout)
        main_layout.addWidget(subscribe_group)

        # 3. 消息发布组
        publish_group = QGroupBox("消息发布")
        publish_layout = QVBoxLayout()

        # 发布主题
        pub_topic_layout = QHBoxLayout()
        pub_topic_layout.addWidget(QLabel("发布主题:"))
        self.publish_topic_input = QLineEdit()
        self.publish_topic_input.setPlaceholderText("输入发布主题")
        pub_topic_layout.addWidget(self.publish_topic_input, 1)

        publish_layout.addLayout(pub_topic_layout)

        # 消息内容
        publish_layout.addWidget(QLabel("消息内容:"))
        self.message_input = QTextEdit()
        self.message_input.setMaximumHeight(80)
        self.message_input.setPlaceholderText("输入JSON格式或文本消息")
        publish_layout.addWidget(self.message_input)

        # 发布按钮
        self.publish_btn = QPushButton("发布")
        self.publish_btn.setEnabled(False)
        publish_layout.addWidget(self.publish_btn)

        publish_group.setLayout(publish_layout)
        main_layout.addWidget(publish_group)

        # 4. 日志区域
        log_group = QGroupBox("日志")
        log_layout = QVBoxLayout()

        self.log_text = QTextEdit()
        self.log_text.setReadOnly(True)
        self.log_text.setMaximumHeight(100)
        self.log_text.setFont(QFont("Consolas", 9))
        log_layout.addWidget(self.log_text)

        log_group.setLayout(log_layout)
        main_layout.addWidget(log_group)

        # 设置最小尺寸
        self.setMinimumWidth(500)
        self.setMinimumHeight(700)

    def connect_signals(self):
        """连接信号和槽"""
        # 按钮点击信号
        self.connect_btn.clicked.connect(self.toggle_connection)
        self.reconnect_btn.clicked.connect(self.reconnect_mqtt)
        self.subscribe_btn.clicked.connect(self.add_subscription)
        self.unsubscribe_btn.clicked.connect(self.remove_subscription)
        self.publish_btn.clicked.connect(self.publish_message)

        # 输入框变化信号
        self.new_topic_input.textChanged.connect(self.on_topic_input_changed)
        self.publish_topic_input.textChanged.connect(self.on_publish_topic_changed)
        self.message_input.textChanged.connect(self.on_message_input_changed)
        self.topic_combo.currentIndexChanged.connect(self.on_topic_selected)

        # MQTT管理器信号
        self.mqtt_manager.signals.connected.connect(self.on_mqtt_connected)
        self.mqtt_manager.signals.disconnected.connect(self.on_mqtt_disconnected)
        self.mqtt_manager.signals.connection_failed.connect(self.on_connection_error)

        self.mqtt_manager.signals.message_received.connect(self.on_message_received)
        self.mqtt_manager.signals.message_published.connect(self.on_message_published)

        self.mqtt_manager.signals.subscribed.connect(self.on_subscribed)
        self.mqtt_manager.signals.unsubscribed.connect(self.on_unsubscribed)

        self.mqtt_manager.signals.log_message.connect(self.on_log_message)

        # 连接船舶管理器信号
        self.ship_manager.ship_added.connect( self .on_ship_added)
        self.ship_manager.ship_updated.connect(self.on_ship_updated)
        self.ship_manager.ship_removed.connect(self.on_ship_removed)


    def toggle_connection(self):
        """切换连接状态"""
        if self.mqtt_manager.is_connected:
            self.disconnect_mqtt()
        else:
            self.connect_mqtt()

    def connect_mqtt(self):
        """连接MQTT"""
        # 获取配置
        ip = self.ip_input.text().strip()
        port = self.port_input.value()
        username = self.username_input.text().strip()
        password = self.password_input.text().strip()

        if not ip:
            self.log_text.append("❌ 请输入IP地址")
            return

        # 设置配置
        self.mqtt_manager.set_config(ip, port, username, password)

        # 连接
        self.mqtt_manager.connect()

    def disconnect_mqtt(self):
        """断开MQTT连接"""
        self.mqtt_manager.disconnect()

    def reconnect_mqtt(self):
        """重新连接"""
        self.mqtt_manager.reconnect()

    def add_subscription(self):
        """添加订阅"""
        topic = self.new_topic_input.text().strip()
        if not topic:
            self.log_text.append("❌ 请输入主题")
            return

        qos = int(self.qos_combo.currentText())

        if self.mqtt_manager.subscribe(topic, qos):
            self.new_topic_input.clear()

    def remove_subscription(self):
        """移除订阅"""
        current_topic = self.topic_combo.currentText()
        if current_topic:
            self.mqtt_manager.unsubscribe(current_topic)

    def publish_message(self):
        """发布消息"""
        topic = self.publish_topic_input.text().strip()
        message = self.message_input.toPlainText().strip()

        if not topic:
            self.log_text.append("❌ 请输入发布主题")
            return

        if not message:
            self.log_text.append("❌ 请输入消息内容")
            return

        try:
            # 尝试解析为JSON
            try:
                payload = json.loads(message)
            except:
                payload = message

            if self.mqtt_manager.publish(topic, payload):
                self.message_input.clear()

        except Exception as e:
            self.log_text.append(f"❌ 发布失败: {e}")

    def on_mqtt_connected(self):
        """MQTT连接成功"""
        self.connect_btn.setText("断开")
        self.connect_btn.setStyleSheet("QPushButton { background-color: #f44336; color: white; }")
        self.reconnect_btn.setEnabled(True)
        self.subscribe_btn.setEnabled(True)
        self.publish_btn.setEnabled(True)
        self.status_label.setText("状态: 已连接")
        self.status_label.setStyleSheet("color: green; font-weight: bold;")

        # 发射自定义信号
        self.mqtt_connected.emit()

    def on_mqtt_disconnected(self):
        """MQTT断开连接"""
        self.connect_btn.setText("连接")
        self.connect_btn.setStyleSheet("QPushButton { background-color: #4CAF50; color: white; }")
        self.reconnect_btn.setEnabled(False)
        self.subscribe_btn.setEnabled(False)
        self.publish_btn.setEnabled(False)
        self.status_label.setText("状态: 未连接")
        self.status_label.setStyleSheet("color: gray; font-weight: bold;")

        # 清空主题列表
        self.topic_combo.clear()

        # 发射自定义信号
        self.mqtt_disconnected.emit()

    def on_connection_error(self, error_msg):
        """连接错误"""
        self.log_text.append(f"❌ {error_msg}")

    def on_message_received(self, topic, message):
        """接收到消息"""
        # 在日志中显示
        try:
            # 如果是JSON，格式化显示
            data = json.loads(message)
            formatted_msg = json.dumps(data, indent=2, ensure_ascii=False)[:100]

            # 检查是否是AIS主题
            if 'ais/dynamic' in topic.lower():
                self.process_ais_message(topic, message)


        except json.JSONDecodeError:

            # 不是JSON格式，作为普通文本处理

            formatted_msg = message[:200]

            # 如果是AIS主题，但消息不是JSON，可能是纯文本格式的AIS数据

            # 检查是否是AIS主题
            if 'ais/dynamic' in topic.lower():
                # 假设AIS消息可能是逗号分隔的文本格式

                self.process_ais_message(topic, message)

        self.log_text.append(f"📩 [{topic}] {formatted_msg}")



    def process_ais_message(self, topic: str, message: str):
        """
        处理AIS消息

        Args:
            topic: 主题
            message: 消息内容
        """
        try:

            self.ship_manager.parse_ais_message(message)


        except Exception as e:
            self.log_text.append(f"❌ 处理AIS消息失败: {e}")
            import traceback
            traceback.print_exc()
    def on_message_published(self, topic, message):
        """消息发布成功"""
        self.log_text.append(f"✅ 已发布到 [{topic}]")

    def on_subscribed(self, topic, qos):
        """订阅成功"""
        # 添加到ComboBox
        if self.topic_combo.findText(topic) == -1:
            self.topic_combo.addItem(topic)

    def on_unsubscribed(self, topic):
        """取消订阅成功"""
        # 从ComboBox中移除
        index = self.topic_combo.findText(topic)
        if index >= 0:
            self.topic_combo.removeItem(index)

    def on_log_message(self, message):
        """日志消息"""
        self.log_text.append(message)

    def on_topic_input_changed(self, text):
        """主题输入变化"""
        self.subscribe_btn.setEnabled(bool(text.strip()))

    def on_publish_topic_changed(self, text):
        """发布主题输入变化"""
        self.publish_btn.setEnabled(bool(text.strip()) and bool(self.message_input.toPlainText().strip()))

    def on_message_input_changed(self):
        """消息输入变化"""
        self.publish_btn.setEnabled(bool(self.publish_topic_input.text().strip()) and
                                    bool(self.message_input.toPlainText().strip()))

    def on_topic_selected(self, index):
        """主题被选择"""
        self.unsubscribe_btn.setEnabled(index >= 0)

    def set_connection_params(self, ip: str, port: int, username: str = "", password: str = ""):
        """设置连接参数"""
        self.ip_input.setText(ip)
        self.port_input.setValue(port)
        self.username_input.setText(username)
        self.password_input.setText(password)

    def get_mqtt_manager(self):
        """获取MQTT管理器实例"""
        return self.mqtt_manager

    def get_subscribed_topics(self):
        """获取已订阅的主题列表"""
        return self.mqtt_manager.get_subscribed_topics()

    def clear_logs(self):
        """清除日志"""
        self.log_text.clear()

    def add_subscription_topic(self, topic: str, qos: int = 0):
        """添加订阅主题（编程方式）"""
        self.mqtt_manager.subscribe(topic, qos)

    def remove_subscription_topic(self, topic: str):
        """移除订阅主题（编程方式）"""
        self.mqtt_manager.unsubscribe(topic)

    def publish(self, topic: str, message: Any, qos: int = 0):
        """发布消息（编程方式）"""
        return self.mqtt_manager.publish(topic, message, qos)

    def on_ship_added(self, ship):
        """新船舶添加"""
        pass

    def on_ship_updated(self, ship):
        """船舶信息更新"""
        # 可选：只在重要变化时记录
        pass

    def on_ship_removed(self, mmsi):
        """船舶移除（离线）"""
        self.log_text.append(f"🚫 船舶离线: {mmsi}")


    def on_ship_direction_changed(self, mmsi, new_direction):
        """船舶方向变化"""
        pass

    def cleanup_offline_ships(self):
        """清理离线船舶"""
        self.ship_manager.remove_offline_ships()

    def get_all_ships(self):
        """获取所有船舶信息"""
        return self.ship_manager.get_all_ships()

    def get_ships_by_direction(self, direction):
        """按方向获取船舶"""
        return self.ship_manager.get_ships_by_direction(direction)


class MainApplication(QMainWindow):
    """主应用程序 - 演示如何嵌入MQTT控件"""

    def __init__(self):
        super().__init__()
        self.setWindowTitle("MQTT控件演示")
        self.setGeometry(100, 100, 900, 800)

        # 中央控件
        central_widget = QWidget()
        self.setCentralWidget(central_widget)

        # 主布局
        main_layout = QVBoxLayout(central_widget)

        # 添加MQTT控件
        self.mqtt_widget = MQTTControlWidget()

        main_layout.addWidget(self.mqtt_widget)

if __name__ == '__main__':
    app = QApplication(sys.argv)
    window =  MainApplication()
    window.show()
    sys.exit(app.exec())