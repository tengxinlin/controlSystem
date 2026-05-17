# led_manager.py
from PyQt5.QtCore import QObject, pyqtSignal
from typing import Dict, List, Optional
import json


class LEDInfo:
    """LED灯信息"""

    def __init__(self, led_id: int, led_name: str, publish_topic: str, receive_topic: str):
        self.led_id = led_id
        self.led_name = led_name
        self.publish_topic = publish_topic
        self.receive_topic = receive_topic
        self.status = 4  # 默认关闭状态 (4)

    # 状态映射
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


class LEDManager(QObject):
    """LED灯管理器"""

    # 信号
    led_status_changed = pyqtSignal(int, int)  # led_id, new_status

    def __init__(self, db_manager, mqtt_manager=None):
        super().__init__()
        self.db_manager = db_manager
        self.mqtt_manager = mqtt_manager
        self.leds: Dict[int, LEDInfo] = {}  # led_id -> LEDInfo
        self.reach_leds: Dict[str, List[LEDInfo]] = {}  # reachcode -> list of LEDs

    def load_leds_by_reachcode(self, reachcode: str) -> List[LEDInfo]:
        """
        根据控制河段代码加载LED灯信息

        Args:
            reachcode: 控制河段代码

        Returns:
            LEDInfo列表
        """
        try:
            # 查询数据库
            conditions = {"reachCode": reachcode}
            results = self.db_manager.search_records("LedInfo", conditions)

            leds = []
            for row in results:
                led = LEDInfo(
                    led_id=row.get('ledID'),
                    led_name=row.get('ledName'),
                    publish_topic=row.get('LEDPublish'),
                    receive_topic=row.get('LEDReceive')
                )
                leds.append(led)
                self.leds[led.led_id] = led

            # 缓存
            self.reach_leds[reachcode] = leds

            # 订阅LED状态主题
            if self.mqtt_manager:
                for led in leds:
                    self._subscribe_led_topic(led)

            print(f"加载了 {len(leds)} 个LED灯，控制河段: {reachcode}")
            return leds

        except Exception as e:
            print(f"加载LED灯信息失败: {e}")
            return []

    def _subscribe_led_topic(self, led: LEDInfo):
        """订阅LED状态主题"""
        if self.mqtt_manager and led.receive_topic:
            self.mqtt_manager.subscribe(led.receive_topic, 0, self._on_led_status)
            print(f"订阅LED状态主题: {led.led_name} -> {led.receive_topic}")

    def _on_led_status(self, topic: str, payload: str, qos: int):
        """处理LED状态消息"""
        try:
            # 解析状态消息
            data = json.loads(payload) if payload.startswith('{') else {'status': int(payload)}
            status = data.get('status', data.get('state', 1))

            # 找到对应的LED
            for led in self.leds.values():
                if led.receive_topic == topic:
                    old_status = led.status
                    led.set_status(status)
                    if old_status != status:
                        self.led_status_changed.emit(led.led_id, status)
                    print(f"LED状态更新: {led.led_name} -> {led.get_status_text()}")
                    break

        except Exception as e:
            print(f"解析LED状态消息失败: {e}")

    def control_led(self, led_id: int, status: int) -> bool:
        """
        控制LED灯

        Args:
            led_id: LED灯ID
            status: 状态码 (0-4)

        Returns:
            是否成功
        """
        led = self.leds.get(led_id)
        if not led:
            print(f"未找到LED灯: {led_id}")
            return False

        if not self.mqtt_manager:
            print("MQTT管理器未初始化")
            return False

        if not self.mqtt_manager.is_connected:
            print("MQTT未连接")
            return False

        try:
            # 构建控制消息
            message = json.dumps({"status": status, "led_id": led_id})

            # 发布控制命令
            success = self.mqtt_manager.publish(led.publish_topic, message)

            if success:
                print(f"发送LED控制命令: {led.led_name} -> {led.get_status_text()}")
            else:
                print(f"发送LED控制命令失败: {led.led_name}")

            return success

        except Exception as e:
            print(f"控制LED灯失败: {e}")
            return False

    def get_leds_for_reach(self, reachcode: str) -> List[LEDInfo]:
        """获取指定控制河段的LED列表"""
        return self.reach_leds.get(reachcode, [])