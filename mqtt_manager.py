# mqtt_manager.py
import json
import time
from typing import List, Dict, Any, Optional, Callable
from dataclasses import dataclass
import paho.mqtt.client as mqtt
from PyQt5.QtCore import QObject, pyqtSignal, QThread, pyqtSlot


@dataclass
class MQTTConfig:
    """MQTT连接配置"""
    broker_ip: str = "isc.cqu.edu.cn"
    port: int = 1883
    username: str = "txl"
    password: str = "txl2022"
    client_id: str = ""
    keepalive: int = 60
    clean_session: bool = True
    tls_enabled: bool = False
    ca_certs: Optional[str] = None




class MQTTSignalHandler(QObject):
    """MQTT信号处理器"""
    # 连接状态信号
    connected = pyqtSignal()
    disconnected = pyqtSignal()
    connection_failed = pyqtSignal(str)  # 错误信息

    # 消息信号
    message_received = pyqtSignal(str, str)  # topic, payload
    message_published = pyqtSignal(str, str)  # topic, payload

    # 订阅状态信号
    subscribed = pyqtSignal(str, int)  # topic, qos
    unsubscribed = pyqtSignal(str)  # topic

    # 日志信号
    log_message = pyqtSignal(str)  # 日志消息


class MQTTManager(QObject):
    """MQTT管理器 - 处理MQTT连接和消息"""

    def __init__(self, config: MQTTConfig = None):
        super().__init__()
        self.config = config or MQTTConfig()
        self.signals = MQTTSignalHandler()

        self.client = None
        self.is_connected = False
        self.subscribed_topics = {}  # topic -> qos
        self.ais_topics = []
        self.led_topics = []
        self.plc_topics = []
        self.message_handlers = {}  # topic -> callback function

        # 连接状态
        self.auto_reconnect = True
        self.reconnect_attempts = 0
        self.max_reconnect_attempts = 5

        # 初始化客户端
        self._init_client()

    def _init_client(self):
        """初始化MQTT客户端"""
        client_id = self.config.client_id or f"pyqt_mqtt_{int(time.time())}"

        self.client = mqtt.Client(
            client_id=client_id,
            clean_session=self.config.clean_session
        )

        # 设置认证
        if self.config.username:
            self.client.username_pw_set(
                self.config.username,
                self.config.password
            )


        # 设置回调函数
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_message = self._on_message
        self.client.on_publish = self._on_publish
        self.client.on_subscribe = self._on_subscribe
        self.client.on_unsubscribe = self._on_unsubscribe

    def set_config(self, broker_ip: str, port: int,
                   username: str = "", password: str = ""):
        """设置MQTT配置"""
        self.config.broker_ip = broker_ip
        self.config.port = port
        self.config.username = username
        self.config.password = password


    def _on_connect(self, client, userdata, flags, rc):
        """连接回调"""
        if rc == 0:
            self.is_connected = True
            self.reconnect_attempts = 0
            self.signals.connected.emit()#mqtt连接成功的信号发射
            self.signals.log_message.emit("✅ MQTT连接成功")

            # 重新订阅之前订阅的主题
            for topic, qos in self.subscribed_topics.items():
                self.client.subscribe(topic, qos)
                self.signals.log_message.emit(f"重新订阅主题: {topic}")

        else:
            error_msg = f"连接失败，返回码: {rc}"
            self.signals.connection_failed.emit(error_msg)
            self.signals.log_message.emit(f"❌ {error_msg}")

            # 自动重连
            if self.auto_reconnect and self.reconnect_attempts < self.max_reconnect_attempts:
                self.reconnect_attempts += 1
                self.signals.log_message.emit(f"尝试重连 ({self.reconnect_attempts}/{self.max_reconnect_attempts})...")
                time.sleep(2 ** self.reconnect_attempts)  # 指数退避
                self.connect()

    def _on_disconnect(self, client, userdata, rc):
        """断开连接回调"""
        self.is_connected = False
        self.signals.disconnected.emit()

        if rc != 0:
            self.signals.log_message.emit(f"意外断开连接，返回码: {rc}")

            # 自动重连
            if self.auto_reconnect and self.reconnect_attempts < self.max_reconnect_attempts:
                self.reconnect_attempts += 1
                self.signals.log_message.emit(f"尝试重连 ({self.reconnect_attempts}/{self.max_reconnect_attempts})...")
                time.sleep(2 ** self.reconnect_attempts)
                self.connect()
        else:
            self.signals.log_message.emit("✅ 已断开MQTT连接")

    def _on_message(self, client, userdata, msg):
        """消息接收回调"""
        try:
            topic = msg.topic
            payload = msg.payload.decode('utf-8')
            qos = msg.qos

            # 发射信号
            self.signals.message_received.emit(topic, payload)



        except Exception as e:
            self.signals.log_message.emit(f"处理消息时出错: {e}")

    def _on_publish(self, client, userdata, mid):
        """消息发布回调"""
        self.signals.log_message.emit(f"消息已发布 (ID: {mid})")

    def _on_subscribe(self, client, userdata, mid, granted_qos):
        """订阅成功回调"""
        # 这里需要维护mid到topic的映射，简化处理
        self.signals.log_message.emit(f"订阅成功 (QoS: {granted_qos})")

    def _on_unsubscribe(self, client, userdata, mid):
        """取消订阅回调"""
        self.signals.log_message.emit(f"取消订阅成功")

    def _on_log(self, client, userdata, level, buf):
        """日志回调"""
        level_str = {
            mqtt.MQTT_LOG_INFO: "INFO",
            mqtt.MQTT_LOG_NOTICE: "NOTICE",
            mqtt.MQTT_LOG_WARNING: "WARNING",
            mqtt.MQTT_LOG_ERR: "ERROR",
            mqtt.MQTT_LOG_DEBUG: "DEBUG"
        }.get(level, "UNKNOWN")

        log_msg = f"[MQTT {level_str}] {buf}"
        self.signals.log_message.emit(log_msg)



    def connect(self):
        """连接到MQTT代理"""
        try:
            self.signals.log_message.emit(f"正在连接MQTT服务器 {self.config.broker_ip}:{self.config.port}...")

            if self.config.tls_enabled:
                self.client.tls_set()

                # 设置用户名密码
            if self.config.username:
                self.client.username_pw_set(
                    self.config.username,
                    self.config.password
                )

            self.client.connect(
                self.config.broker_ip,
                self.config.port,
                self.config.keepalive
            )

            # 启动网络循环（在后台线程中）
            self.client.loop_start()

        except Exception as e:
            error_msg = f"连接失败: {e}"
            self.signals.connection_failed.emit(error_msg)
            self.signals.log_message.emit(f"❌ {error_msg}")

    def disconnect(self):
        """断开连接"""
        if self.client and self.is_connected:
            self.client.loop_stop()
            self.client.disconnect()
            self.is_connected = False
            self.signals.disconnected.emit()
            self.signals.log_message.emit("已断开MQTT连接")

    def reconnect(self):
        """重新连接"""
        self.signals.log_message.emit("尝试重新连接...")
        self.disconnect()
        time.sleep(1)
        self.connect()

    def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False):
        """
        发布消息

        Args:
            topic: 主题
            payload: 消息内容（会自动转换为JSON字符串）
            qos: 服务质量等级 (0, 1, 2)
            retain: 是否保留消息
        """
        if not self.is_connected:
            self.signals.log_message.emit("❌ 未连接，无法发布消息")
            return False

        try:
            # 转换payload为字符串
            if isinstance(payload, dict) or isinstance(payload, list):
                payload_str = json.dumps(payload, ensure_ascii=False)
            else:
                payload_str = str(payload)

            result = self.client.publish(topic, payload_str, qos=qos, retain=retain)

            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                self.signals.message_published.emit(topic, payload_str)
                self.signals.log_message.emit(f"✅ 发布消息到 {topic}: {payload_str[:50]}...")
                return True
            else:
                self.signals.log_message.emit(f"❌ 发布失败: {result.rc}")
                return False

        except Exception as e:
            self.signals.log_message.emit(f"❌ 发布消息时出错: {e}")
            return False

    def subscribe(self, topic: str, qos: int = 0, callback: Callable = None):
        """
        订阅主题

        Args:
            topic: 要订阅的主题
            qos: 服务质量等级
            callback: 收到消息时的回调函数
        """
        if not self.is_connected:
            self.signals.log_message.emit("❌ 未连接，无法订阅")
            return False

        try:
            result = self.client.subscribe(topic, qos)

            if result[0] == mqtt.MQTT_ERR_SUCCESS:
                self.subscribed_topics[topic] = qos

                if callback:
                    self.message_handlers[topic] = callback

                self.signals.subscribed.emit(topic, qos)
                self.signals.log_message.emit(f"✅ 已订阅主题: {topic} (QoS: {qos})")
                return True
            else:
                self.signals.log_message.emit(f"❌ 订阅失败: {result[0]}")
                return False

        except Exception as e:
            self.signals.log_message.emit(f"❌ 订阅时出错: {e}")
            return False

    def unsubscribe(self, topic: str):
        """取消订阅"""
        if not self.is_connected:
            self.signals.log_message.emit("❌ 未连接，无法取消订阅")
            return False

        try:
            result = self.client.unsubscribe(topic)

            if result[0] == mqtt.MQTT_ERR_SUCCESS:
                if topic in self.subscribed_topics:
                    del self.subscribed_topics[topic]

                if topic in self.message_handlers:
                    del self.message_handlers[topic]

                self.signals.unsubscribed.emit(topic)
                self.signals.log_message.emit(f"✅ 已取消订阅: {topic}")
                return True
            else:
                self.signals.log_message.emit(f"❌ 取消订阅失败: {result[0]}")
                return False

        except Exception as e:
            self.signals.log_message.emit(f"❌ 取消订阅时出错: {e}")
            return False

    def get_subscribed_topics(self) -> List[str]:
        """获取已订阅的主题列表"""
        return list(self.subscribed_topics.keys())

    def clear_subscriptions(self):
        """清除所有订阅"""
        for topic in list(self.subscribed_topics.keys()):
            self.unsubscribe(topic)

    def add_message_handler(self, topic: str, callback: Callable):
        """为特定主题添加消息处理器"""
        self.message_handlers[topic] = callback

    def remove_message_handler(self, topic: str):
        """移除特定主题的消息处理器"""
        if topic in self.message_handlers:
            del self.message_handlers[topic]

    def __del__(self):
        """析构函数"""
        self.disconnect()

