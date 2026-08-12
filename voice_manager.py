# voice_manager.py
import time
import json
import threading
from typing import List, Dict, Optional, Callable
from PyQt5.QtCore import QObject, pyqtSignal, QThread, QMutex
from PyQt5.QtTextToSpeech import QTextToSpeech
from PyQt5.QtMultimedia import QAudio


class VoiceMessage:
    """语音消息"""

    def __init__(self, text: str, priority: int = 0, source: str = "local"):
        self.text = text
        self.priority = priority  # 优先级，数字越大优先级越高
        self.source = source  # 'local' 或 'vhf'
        self.timestamp = time.time()
        self.id = f"{self.timestamp}_{id(self)}"


class LocalVoiceWorker:
    """本地语音播报工作器"""

    def __init__(self):
        self.tts = None
        self.is_speaking = False
        self._init_tts()

    def _init_tts(self):
        try:
            self.tts = QTextToSpeech()
            self.tts.setRate(0.0)  # 语速 -1.0 到 1.0
            self.tts.setPitch(0.0)  # 音调
            self.tts.setVolume(1.0)  # 音量
        except Exception as e:
            print(f"本地语音初始化失败: {e}")
            self.tts = None

    def speak(self, text: str) -> bool:
        if not self.tts:
            return False
        try:
            self.is_speaking = True
            self.tts.say(text)
            # 等待播报完成（简化处理）
            while self.tts.state() == QTextToSpeech.Speaking:
                time.sleep(0.1)
            self.is_speaking = False
            return True
        except Exception as e:
            print(f"本地语音播报失败: {e}")
            self.is_speaking = False
            return False

    def stop(self):
        if self.tts and self.is_speaking:
            self.tts.stop()
            self.is_speaking = False


class VHFVoiceWorker:
    """高频语音播报工作器"""

    def __init__(self, ip: str = "", port: int = 0, send_type: str = "web"):
        self.ip = ip
        self.port = port
        self.send_type = send_type  # 'web' 或 'ptt'
        self.is_speaking = False

    def speak(self, text: str) -> bool:
        self.is_speaking = True
        try:
            if self.send_type == "web":
                success = self._send_via_web(text)
            else:
                success = self._send_via_ptt(text)
            self.is_speaking = False
            return success
        except Exception as e:
            print(f"高频语音播报失败: {e}")
            self.is_speaking = False
            return False

    def _send_via_web(self, text: str) -> bool:
        """通过Web接口发送高频语音"""
        # TODO: 实现Web接口调用
        print(f"通过Web接口发送高频语音: {text}")
        return True

    def _send_via_ptt(self, text: str) -> bool:
        """通过PTT接口发送高频语音"""
        # TODO: 实现PTT接口调用
        print(f"通过PTT接口发送高频语音: {text}")
        return True

    def stop(self):
        # TODO: 实现停止高频语音
        self.is_speaking = False


class VoiceManager(QObject):
    """语音播报管理器"""

    # 信号
    speak_started = pyqtSignal(str, str)  # text, source
    speak_finished = pyqtSignal(str, str)  # text, source
    speak_error = pyqtSignal(str, str)  # error, source

    def __init__(self):
        super().__init__()
        self.local_voice = LocalVoiceWorker()
        self.vhf_voice = None  # VHFVoiceWorker

        # 消息队列
        self.message_queue: List[VoiceMessage] = []
        self.current_message: Optional[VoiceMessage] = None
        self.is_processing = False

        # 锁
        self.queue_lock = QMutex()

        # 配置
        self.local_enabled = True
        self.vhf_enabled = False
        self.vhf_config = {
            'ip': '',
            'port': 0,
            'send_type': 'web'
        }
        self.rate = 0.0  # 语速

    def set_vhf_config(self, ip: str, port: int, send_type: str):
        """设置高频语音配置"""
        self.vhf_config['ip'] = ip
        self.vhf_config['port'] = port
        self.vhf_config['send_type'] = send_type
        self.vhf_voice = VHFVoiceWorker(ip, port, send_type)
        print(f"高频语音配置已更新: {ip}:{port}, 类型: {send_type}")

    def set_local_enabled(self, enabled: bool):
        """设置本地语音是否启用"""
        self.local_enabled = enabled

    def set_vhf_enabled(self, enabled: bool):
        """设置高频语音是否启用"""
        self.vhf_enabled = enabled
        if enabled and not self.vhf_voice:
            self.vhf_voice = VHFVoiceWorker(
                self.vhf_config['ip'],
                self.vhf_config['port'],
                self.vhf_config['send_type']
            )

    def set_rate(self, rate: float):
        """设置语速"""
        self.rate = rate
        if self.local_voice and self.local_voice.tts:
            self.local_voice.tts.setRate(rate)

    def speak(self, text: str, priority: int = 0, source: str = "auto"):
        """
        添加语音播报消息

        Args:
            text: 播报文本
            priority: 优先级，数字越大优先级越高
            source: 'local', 'vhf', 'auto'
        """
        if not text or not text.strip():
            return

        # 确定来源
        if source == "auto":
            if self.local_enabled and self.vhf_enabled:
                source = "both"
            elif self.local_enabled:
                source = "local"
            elif self.vhf_enabled:
                source = "vhf"
            else:
                print("没有可用的语音播报源")
                return

        message = VoiceMessage(text, priority, source)

        self.queue_lock.lock()
        self.message_queue.append(message)
        # 按优先级排序
        self.message_queue.sort(key=lambda x: x.priority, reverse=True)
        self.queue_lock.unlock()

        # 启动处理
        if not self.is_processing:
            self._process_queue()

    def _process_queue(self):
        """处理消息队列"""
        if not self.message_queue:
            self.is_processing = False
            return

        self.is_processing = True

        # 取出下一条消息
        self.queue_lock.lock()
        self.current_message = self.message_queue.pop(0)
        self.queue_lock.unlock()

        if not self.current_message:
            self.is_processing = False
            return

        message = self.current_message
        self.speak_started.emit(message.text, message.source)

        # 根据来源播报
        success = False
        if message.source == "local":
            success = self._speak_local(message.text)
        elif message.source == "vhf":
            success = self._speak_vhf(message.text)
        elif message.source == "both":
            # 同时播报
            success1 = self._speak_local(message.text)
            success2 = self._speak_vhf(message.text)
            success = success1 or success2

        if success:
            self.speak_finished.emit(message.text, message.source)
        else:
            self.speak_error.emit(message.text, message.source)

        self.current_message = None

        # 继续处理下一条
        self._process_queue()

    def _speak_local(self, text: str) -> bool:
        """本地语音播报"""
        if not self.local_enabled or not self.local_voice:
            return False
        return self.local_voice.speak(text)

    def _speak_vhf(self, text: str) -> bool:
        """高频语音播报"""
        if not self.vhf_enabled or not self.vhf_voice:
            return False
        return self.vhf_voice.speak(text)

    def stop_all(self):
        """停止所有播报"""
        if self.local_voice:
            self.local_voice.stop()
        if self.vhf_voice:
            self.vhf_voice.stop()
        self.message_queue.clear()
        self.is_processing = False

    def clear_queue(self):
        """清空消息队列"""
        self.message_queue.clear()