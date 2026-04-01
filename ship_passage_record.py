# ship_passage_record.py
from dataclasses import dataclass
from typing import Optional
import time
from datetime import datetime


@dataclass
class ShipPassageRecord:
    """船舶通行记录"""
    mmsi: str
    name: str
    direction: str  # 'up' 或 'down'
    tug_count: int = 0  # 拖驳数
    cargo: str = ""  # 货物
    actual_load: float = 0.0  # 实际载重（吨）
    rated_load: float = 0.0  # 额定载重（吨）
    water_level: float = 0.0  # 水位信息
    duty_person: str = ""  # 值班人
    weather: str = ""  # 晴、雨、阴、霾、雾
    pushing_status: str = ""  # 顶推情况：顶推、调头等待
    remark: str = ""  # 备注

    # 时间字段
    forecast_time: float = 0.0  # 预告时间（进入揭示区时间）
    supplement_time: float = 0.0  # 补充时间
    start_hang_time: float = 0.0  # 起挂时间
    half_pole_time: float = 0.0  # 半杆时间
    enter_channel_time: float = 0.0  # 进漕时间（进入控制河段时间）
    exit_channel_time: float = 0.0  # 出漕时间（离开控制河段时间）
    create_time: float = 0.0  # 记录创建时间

    def __post_init__(self):
        if self.create_time == 0:
            self.create_time = time.time()

    @property
    def passage_time(self) -> float:
        """通过时间（分钟）"""
        if self.enter_channel_time > 0 and self.exit_channel_time > 0:
            return (self.exit_channel_time - self.enter_channel_time) / 60
        return 0.0

    @property
    def is_complete(self) -> bool:
        """记录是否完整（有出漕时间）"""
        return self.exit_channel_time > 0

    @property
    def is_active(self) -> bool:
        """是否活跃记录（进入揭示区但未出漕）"""
        return self.forecast_time > 0 and self.exit_channel_time == 0

    def to_dict(self) -> dict:
        """转换为字典"""
        return {
            'mmsi': self.mmsi,
            'name': self.name,
            'direction': self.direction,
            'tug_count': self.tug_count,
            'cargo': self.cargo,
            'actual_load': self.actual_load,
            'rated_load': self.rated_load,
            'water_level': self.water_level,
            'duty_person': self.duty_person,
            'weather': self.weather,
            'pushing_status': self.pushing_status,
            'remark': self.remark,
            'forecast_time': self.forecast_time,
            'forecast_time_str': datetime.fromtimestamp(self.forecast_time).strftime(
                '%Y-%m-%d %H:%M:%S') if self.forecast_time > 0 else '',
            'supplement_time': self.supplement_time,
            'supplement_time_str': datetime.fromtimestamp(self.supplement_time).strftime(
                '%Y-%m-%d %H:%M:%S') if self.supplement_time > 0 else '',
            'start_hang_time': self.start_hang_time,
            'start_hang_time_str': datetime.fromtimestamp(self.start_hang_time).strftime(
                '%Y-%m-%d %H:%M:%S') if self.start_hang_time > 0 else '',
            'half_pole_time': self.half_pole_time,
            'half_pole_time_str': datetime.fromtimestamp(self.half_pole_time).strftime(
                '%Y-%m-%d %H:%M:%S') if self.half_pole_time > 0 else '',
            'enter_channel_time': self.enter_channel_time,
            'enter_channel_time_str': datetime.fromtimestamp(self.enter_channel_time).strftime(
                '%Y-%m-%d %H:%M:%S') if self.enter_channel_time > 0 else '',
            'exit_channel_time': self.exit_channel_time,
            'exit_channel_time_str': datetime.fromtimestamp(self.exit_channel_time).strftime(
                '%Y-%m-%d %H:%M:%S') if self.exit_channel_time > 0 else '',
            'passage_time': self.passage_time,
            'create_time': self.create_time,
            'create_time_str': datetime.fromtimestamp(self.create_time).strftime('%Y-%m-%d %H:%M:%S'),
            'is_complete': self.is_complete,
            'is_active': self.is_active
        }