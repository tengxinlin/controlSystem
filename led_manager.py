# led_manager.py
from dataclasses import dataclass
from enum import Enum
import time
from typing import Dict, List

from PyQt5.QtCore import QObject, pyqtSignal


class LEDControlMode(Enum):
    """LED控制模式"""
    MQTT = "mqtt"
    LORA = "lora"
    BOTH = "both"
    NONE = "none"


@dataclass
class LEDInfo:
    """LED灯信息"""
    led_id: str  # LED ID（来自 LedInfo 表）
    led_name: str = ""  # LED 名称
    publish_topic: str = ""  # MQTT 发布主题（控制）
    receive_topic: str = ""  # MQTT 接收主题（状态反馈）

    # LoRa 相关（来自 LoraInfo 表）
    lora_id: str = ""  # LoRa ID
    lora_publish: str = ""  # LoRa 发布主题（控制）
    lora_receive: str = ""  # LoRa 接收主题（状态反馈）
    lora_index: int = 0  # LoRa 灯序号（1-4）

    # 状态
    status: int = 4  # 默认关闭状态 (5)
    mqtt_status: int = 4  # MQTT 反馈的状态
    lora_status: int = 4  # LoRa 反馈的状态

    # 接收时间
    mqtt_last_receive: float = 0  # MQTT 最后接收时间
    lora_last_receive: float = 0  # LoRa 最后接收时间

    # 连接状态
    mqtt_connected: bool = False  # MQTT 是否连接
    lora_connected: bool = False  # LoRa 是否连接

    # 状态映射 (MQTT发送的01,02,03...)
    STATUS_MAP = {
        0: "禁航",
        1: "上水",
        2: "下水",
        3: "半杆",
        4: "关闭"
    }

    def get_status_text(self) -> str:
        """获取状态文本"""
        return self.STATUS_MAP.get(self.status, "未知")

    def set_status(self, status: int):
        """设置状态"""
        if status in self.STATUS_MAP:
            self.status = status

    def update_mqtt_receive(self, status: int):
        """更新 MQTT 接收状态"""
        self.mqtt_status = status
        self.mqtt_last_receive = time.time()
        self.mqtt_connected = True

        # 更新最终状态（使用最新的有效反馈）
        self._update_final_status()

    def update_lora_receive(self, status: int):
        """更新 LoRa 接收状态"""
        self.lora_status = status
        self.lora_last_receive = time.time()
        self.lora_connected = True

        # 更新最终状态
        self._update_final_status()

    def _update_final_status(self):
        """根据 MQTT 和 LoRa 的状态更新最终状态"""
        if self.mqtt_connected and self.lora_connected:
            # 双通道都连接，使用最新收到的状态
            if self.mqtt_last_receive > self.lora_last_receive:
                self.status = self.mqtt_status
            else:
                self.status = self.lora_status
        elif self.mqtt_connected:
            self.status = self.mqtt_status
        elif self.lora_connected:
            self.status = self.lora_status
        else:
            self.status = 4  # 断开则关闭

    def get_connection_status(self) -> str:
        """获取连接状态描述"""
        if self.mqtt_connected and self.lora_connected:
            return "双通道"
        elif self.mqtt_connected:
            return "MQTT"
        elif self.lora_connected:
            return "LoRa"
        else:
            return "断开"

    def get_connection_color(self) -> str:
        """
        获取连接状态对应的颜色

        Returns:
            颜色代码
            - 红色 (#e74c3c): 全部断开
            - 蓝色 (#3498db): MQTT + LoRa 都连接
            - 黄色 (#f39c12): 只有 MQTT 连接
            - 绿色 (#2ecc71): 只有 LoRa 连接
        """
        if self.mqtt_connected and self.lora_connected:
            return "#3498db"  # 蓝色 - 双通道连接
        elif self.mqtt_connected:
            return "#f39c12"  # 黄色 - 只有 MQTT
        elif self.lora_connected:
            return "#2ecc71"  # 绿色 - 只有 LoRa
        else:
            return "#e74c3c"  # 红色 - 全部断开

    def get_connection_text(self) -> str:
        """获取连接状态显示文本"""
        if self.mqtt_connected and self.lora_connected:
            return "双通道"
        elif self.mqtt_connected:
            return "MQTT"
        elif self.lora_connected:
            return "LoRa"
        else:
            return "断开"

    def has_any_connection(self) -> bool:
        """是否有任何连接"""
        return self.mqtt_connected or self.lora_connected

    def has_both_connection(self) -> bool:
        """是否双通道都连接"""
        return self.mqtt_connected and self.lora_connected


class LEDManager(QObject):
    """LED灯管理器 - 支持 MQTT 和 LoRa 双通道"""

    # 信号
    led_status_changed = pyqtSignal(str, int)  # led_id, status (字符串类型)
    led_connection_changed = pyqtSignal(str, str)  # led_id, connection_status (字符串类型)

    def __init__(self, db_manager, mqtt_manager,logmessage):
        super().__init__()
        self.db_manager = db_manager
        self.logmessage = logmessage
        self.mqtt_manager = mqtt_manager
        self.leds: Dict[str, LEDInfo] = {}
        self.reach_leds: Dict[str, List[LEDInfo]] = {}

        # LoRa 主题映射（用于接收 LoRa 状态消息）
        self.lora_receive_topic_map: Dict[str, List[str]] = {}  # lora_receive_topic -> [led_id1, led_id2, ...]

        # 超时时间（秒）
        self.mqtt_timeout = 60  # 6分钟
        self.lora_timeout = 60  # 6分钟

    def load_leds_by_reachcode(self, reachcode: str) -> List[LEDInfo]:
        """
        加载 LED 灯信息（合并 LedInfo 和 LoraInfo 表）
        """
        try:
            self.leds.clear()
            self.lora_receive_topic_map.clear()

            # 1. 从 LedInfo 表读取 MQTT 信息（每个LED独立的主题）
            mqtt_conditions = {"reachCode": reachcode}
            mqtt_results = self.db_manager.search_records("LedInfo", mqtt_conditions)

            # 2. 从 LoraInfo 表读取 LoRa 信息（整个河段共享主题）
            lora_conditions = {"reachCode": reachcode}
            lora_results = self.db_manager.search_records("LoraInfo", lora_conditions)

            # 提取 LoRa 公共信息（只有一个）
            lora_common = None
            if lora_results:
                lora_common = lora_results[0]  # 取第一个（实际上只有一个）

            # 创建 LED 字典
            led_dict: Dict[str, LEDInfo] = {}

            # 处理 MQTT 数据 (LedInfo 表) - 每个LED有自己的主题
            for row in mqtt_results:
                led_id = str(row.get('ledID', ''))
                if not led_id:
                    continue

                led_dict[led_id] = LEDInfo(
                    led_id=led_id,
                    led_name=row.get('ledName', f"LED{led_id}"),
                    publish_topic=row.get('LEDPublish', ''),
                    receive_topic=row.get('LEDReceive', '')
                )
                print(f"📋 MQTT: LED {led_id} -> 发布: {row.get('LEDPublish', '')}, 接收: {row.get('LEDReceive', '')}")

            # 处理 LoRa 数据（共享主题，按灯序号区分）
            if lora_common:
                lora_id = str(lora_common.get('LoraID', ''))
                lora_publish = lora_common.get('LoRaPublish', '')
                lora_receive = lora_common.get('LoRaReceive', '')

                # 从数据库读取每个灯的序号（如果有单独字段）
                # 假设 loraIndex 字段在 LoraInfo 表中，或者通过其他方式关联
                # 这里我们遍历所有 LED，为每个 LED 分配 LoRa 信息
                for index, led_id in enumerate(led_dict.keys(), start=1):
                    # 获取该 LED 对应的 LoRa 序号（如果数据库中有存储）
                    # 这里假设通过 ledID 关联，或者从某个配置中读取
                    # 简单起见，我们按顺序分配：假设 4 个灯，按 led_id 排序后分配 1-4
                    led = led_dict[led_id]
                    led.lora_id = lora_id
                    led.lora_publish = lora_publish
                    led.lora_receive = lora_receive

                    led.lora_index = index

                    print(f"📋 LoRa: LED {led_id} -> Lora {lora_id}, 序号: {index}")

                # 记录 LoRa 接收主题映射
                if lora_receive:
                    self.lora_receive_topic_map[lora_receive] = list(led_dict.keys())
            else:
                print("⚠️ 未找到 LoRa 配置")

            # 转换字典为列表
            leds = list(led_dict.values())

            # 保存到实例变量
            for led in leds:
                self.leds[led.led_id] = led

            self.reach_leds[reachcode] = leds

            # 订阅主题
            if self.mqtt_manager:
                for led in leds:
                    self._subscribe_led_topics(led)

            print(f"✅ 加载完成: {len(leds)} 个LED灯，控制河段: {reachcode}")
            return leds

        except Exception as e:
            print(f"加载LED灯信息失败: {e}")
            import traceback
            traceback.print_exc()
            return []



    def _subscribe_led_topics(self, led: LEDInfo):
        """订阅 LED 的所有主题"""
        if not self.mqtt_manager:
            return

        # 订阅 MQTT 状态主题（每个LED独立）
        if led.receive_topic:
            self.mqtt_manager.subscribe(led.receive_topic, 0, self._on_mqtt_status)
            print(f"📡 订阅 MQTT: {led.led_name} -> {led.receive_topic}")

        # 订阅 LoRa 状态主题（整个河段共享，只订阅一次）
        if led.lora_receive:
            # 检查是否已经订阅过
            if led.lora_receive not in self.mqtt_manager.subscribed_topics:
                # 只订阅一次
                self.mqtt_manager.subscribe(led.lora_receive, 0, self._on_lora_status)
                print(f"📡 订阅 LoRa: {led.led_name} -> {led.lora_receive}")

    def _on_mqtt_status(self, topic: str, payload: str, qos: int=0):
        """处理 MQTT 状态消息（每个LED独立主题）"""
        try:
            for led in self.leds.values():
                if led.receive_topic == topic:
                    status = int(payload.strip().split(",")[0])
                    led.update_mqtt_receive(status)
                    self.led_status_changed.emit(led.led_id, led.status)
                    self.led_connection_changed.emit(led.led_id, led.get_connection_status())
                    print(f"📩 MQTT [{led.led_name}]: {led.get_status_text()}")
                    break
        except Exception as e:
            print(f"解析 MQTT LED 状态失败: {e}")

    def _on_lora_status(self, topic: str, payload: str, qos: int=0):
        """处理 LoRa 状态消息（格式: loraid 灯序号 状态码）"""
        try:
            # 解析 LoRa 状态: "loraid 1 2"
            parts = payload.strip().split()
            if len(parts) >= 3:
                lora_id = str(parts[0])
                lora_index = int(parts[1])
                status = int(parts[2])

                # 找到该 lora_id 和 lora_index 对应的 LED
                for led in self.leds.values():
                    if led.lora_id == lora_id and led.lora_index == lora_index:
                        led.update_lora_receive(status)
                        self.led_status_changed.emit(led.led_id, led.status)
                        self.led_connection_changed.emit(led.led_id, led.get_connection_status())
                        print(f"📩 LoRa [{led.led_name}]: {led.get_status_text()}")
                        break
            else:
                print(f"⚠️ LoRa 消息格式错误: {payload}")

        except Exception as e:
            print(f"解析 LoRa LED 状态失败: {e}")

    def control_led(self, led_id: str, status: int, mode: str = "auto") -> bool:
        """
        控制 LED 灯

        Args:
            led_id: LED ID
            status: 状态码 (1-5)
            mode: 控制模式 'mqtt', 'lora', 'auto', 'both'
        """
        led = self.leds.get(led_id)
        if not led:
            print(f"未找到 LED: {led_id}")
            return False

        if not self.mqtt_manager or not self.mqtt_manager.is_connected:
            print("MQTT 未连接")
            return False

        if mode == "auto":
            if led.mqtt_connected:
                return self._control_led_mqtt(led, status)
            elif led.lora_connected:
                return self._control_led_lora(led, status)
            else:
                print(f"LED {led.led_name} 没有任何可用通道")
                return False
        elif mode == "mqtt":
            return self._control_led_mqtt(led, status)
        elif mode == "lora":
            return self._control_led_lora(led, status)
        elif mode == "both":
            result1 = self._control_led_mqtt(led, status)
            result2 = self._control_led_lora(led, status)
            return result1 or result2
        else:
            return False

    def _control_led_mqtt(self, led: LEDInfo, status: int) -> bool:
        """通过 MQTT 控制 LED（每个LED独立主题）"""
        if not led.publish_topic:
            print(f"LED {led.led_name} 没有 MQTT 发布主题")
            return False

        try:
            message = str(status)
            result = self.mqtt_manager.publish(led.publish_topic, message)
            if result:
                print(f"📤 MQTT 控制 [{led.led_name}]: {led.get_status_text()}")
            return result
        except Exception as e:
            print(f"MQTT 控制 LED 失败: {e}")
            return False

    def _control_led_lora(self, led: LEDInfo, status: int) -> bool:
        """通过 LoRa 控制 LED（共享主题，通过灯序号区分）"""
        if not led.lora_id or not led.lora_publish:
            print(f"LED {led.led_name} 没有 LoRa 信息")
            return False

        try:
            # LoRa 命令格式: "command loraid 灯序号 状态码"
            message = f"command {led.lora_id} {led.lora_index} {status}"
            result = self.mqtt_manager.publish(led.lora_publish, message)
            if result:
                print(f"📤 LoRa 控制 [{led.led_name}]: {led.get_status_text()}")
            return result
        except Exception as e:
            print(f"LoRa 控制 LED 失败: {e}")
            return False

    def check_led_connections(self) -> int:
        """检查所有 LED 的连接状态"""
        current_time = time.time()
        changed_count = 0

        for led in self.leds.values():
            status_changed = False

            if led.mqtt_connected:
                if current_time - led.mqtt_last_receive > self.mqtt_timeout:
                    led.mqtt_connected = False
                    status_changed = True
                    self.logmessage(f"⚠️ LED {led.led_name} MQTT 连接超时")

            if led.lora_connected:
                if current_time - led.lora_last_receive > self.lora_timeout:
                    led.lora_connected = False
                    status_changed = True
                    self.logmessage(f"⚠️ LED {led.led_name} LoRa 连接超时")

            if status_changed:
                led._update_final_status()
                self.led_connection_changed.emit(led.led_id, led.get_connection_status())
                self.led_status_changed.emit(led.led_id, led.status)
                changed_count += 1

                if not led.has_any_connection():
                    self.logmessage(f"🔴 LED {led.led_name} 所有通道断开，已关闭")

        return changed_count