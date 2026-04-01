# passage_record_manager.py
from typing import Dict, List, Optional
import time
from datetime import datetime, timedelta
from PyQt5.QtCore import QObject, pyqtSignal
from command_record_db import CommandRecordDB
from ship_passage_record import ShipPassageRecord


class PassageRecordManager(QObject):
    """船舶通行记录管理器（基于数据库）"""

    # 信号
    record_created = pyqtSignal(str)  # 记录创建 (mmsi)
    record_updated = pyqtSignal(str)  # 记录更新 (mmsi)
    record_completed = pyqtSignal(str)  # 记录完成 (mmsi)
    record_deleted = pyqtSignal(str)  # 记录删除 (mmsi)

    def __init__(self, db_manager):
        super().__init__()
        # 数据库操作对象
        self.db = CommandRecordDB(db_manager)

        # 配置
        self.auto_cleanup_days =  1 # 自动清理超过7天的记录
        self.active_timeout_hours = 4  # 活跃记录超时时间（小时）

        # 缓存活跃记录（用于快速访问）
        self._active_cache: Dict[str, dict] = {}
        self._load_active_cache()

    def _load_active_cache(self):
        """加载活跃记录到缓存"""
        active_records = self.db.get_active_records()
        for record in active_records:
            self._active_cache[record['mmsi']] = record
        print(f"加载了 {len(self._active_cache)} 条活跃记录到缓存")

    def create_record(self, mmsi: str, name: str, direction: str) -> Optional[Dict]:
        """
        创建新的通行记录（船舶进入揭示区时调用）

        Args:
            mmsi: 船舶MMSI
            name: 船舶名称
            direction: 方向 ('up' 或 'down')

        Returns:
            创建的记录字典
        """
        # 检查是否已有活跃记录
        existing = self.db.get_active_by_mmsi(mmsi)
        if existing:
            # 检查是否超时
            current_time = int(time.time())
            forecast_time = existing.get('forecast_time', 0)
            if current_time - forecast_time > self.active_timeout_hours * 3600:
                # 超时，删除旧记录
                self.db.delete_by_mmsi(mmsi)
                if mmsi in self._active_cache:
                    del self._active_cache[mmsi]
            else:
                print(f"船舶 {name} ({mmsi}) 已有活跃记录，不重复创建")
                return existing

        # 创建新记录
        current_time = int(time.time())
        record = {
            'mmsi': mmsi,
            'name': name,
            'direction': direction,
            'forecast_time': current_time,
            'create_time': current_time,
            'last_update': current_time,
            'is_active': 1
        }

        record_id = self.db.insert(record)
        if record_id > 0:
            record['id'] = record_id
            self._active_cache[mmsi] = record
            self.record_created.emit(mmsi)
            print(f"创建通行记录: {name} ({mmsi}) - {direction}")
            return record

        return None

    def update_record(self, mmsi: str, **kwargs) -> bool:
        """
        更新通行记录

        Args:
            mmsi: 船舶MMSI
            **kwargs: 要更新的字段
        """
        # 更新数据库
        success = self.db.update_by_mmsi(mmsi, kwargs)

        if success:
            # 更新缓存
            if mmsi in self._active_cache:
                self._active_cache[mmsi].update(kwargs)
            self.record_updated.emit(mmsi)

        return success

    def record_enter_channel(self, mmsi: str, time_value: int = None) -> bool:
        """
        记录进漕时间（船舶进入控制河段）

        Args:
            mmsi: 船舶MMSI
            time_value: 时间戳，默认当前时间
        """
        enter_time = time_value or int(time.time())
        return self.update_record(mmsi, enter_channel_time=enter_time)

    def record_exit_channel(self, mmsi: str, time_value: int = None) -> bool:
        """
        记录出漕时间（船舶离开控制河段），完成通行记录

        Args:
            mmsi: 船舶MMSI
            time_value: 时间戳，默认当前时间
        """
        exit_time = time_value or int(time.time())

        # 完成记录
        success = self.db.complete_record(mmsi, exit_time)

        if success:
            # 从缓存中移除
            if mmsi in self._active_cache:
                del self._active_cache[mmsi]
            self.record_completed.emit(mmsi)
            print(f"船舶 {mmsi} 通行记录完成")

        return success

    def get_active_records(self) -> List[Dict]:
        """获取活跃记录列表"""
        return list(self._active_cache.values())

    def get_today_records(self) -> List[Dict]:
        """获取今天的记录"""
        return self.db.get_today_records()

    def get_records_by_date(self, date_str: str) -> List[Dict]:
        """获取指定日期的记录"""
        records = self.db.get_records_by_date(date_str)

        # 计算通过时间
        for record in records:
            enter_time = record.get('enter_channel_time', 0)
            exit_time = record.get('exit_channel_time', 0)
            if enter_time > 0 and exit_time > 0:
                record['passage_time'] = (exit_time - enter_time) / 60.0
            else:
                record['passage_time'] = 0

            # 格式化时间字符串
            for field in ['forecast_time', 'supplement_time', 'start_hang_time',
                          'half_pole_time', 'enter_channel_time', 'exit_channel_time', 'create_time']:
                ts = record.get(field, 0)
                if ts > 0:
                    record[f'{field}_str'] = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S')
                else:
                    record[f'{field}_str'] = ''

        return records

    def get_records_by_mmsi(self, mmsi: str) -> List[Dict]:
        """获取指定船舶的所有记录"""
        return self.db.get_records_by_mmsi(mmsi)

    def delete_record(self, mmsi: str) -> bool:
        """删除船舶的记录"""
        success = self.db.delete_by_mmsi(mmsi)

        if success:
            if mmsi in self._active_cache:
                del self._active_cache[mmsi]
            self.record_deleted.emit(mmsi)

        return success

    def delete_record_by_id(self, record_id: int) -> bool:
        """根据ID删除记录"""
        # 先获取记录
        records = self.db.get_records_by_mmsi(str(record_id))  # 需要先查询
        success = self.db.delete_record(record_id)

        if success:
            # 从缓存中移除
            for mmsi, record in list(self._active_cache.items()):
                if record.get('id') == record_id:
                    del self._active_cache[mmsi]
                    break
            self.record_deleted.emit(str(record_id))

        return success

    def auto_cleanup(self) -> int:
        """自动清理过期记录"""
        # 清理超时的活跃记录
        current_time = int(time.time())
        timeout_seconds = self.active_timeout_hours * 3600
        expired = []

        for mmsi, record in self._active_cache.items():
            forecast_time = record.get('forecast_time', 0)
            if current_time - forecast_time > timeout_seconds:
                expired.append(mmsi)

        for mmsi in expired:
            self.db.delete_by_mmsi(mmsi)
            del self._active_cache[mmsi]

        # 清理过期的历史记录
        deleted_count = self.db.delete_expired_records(self.auto_cleanup_days)

        total_cleaned = len(expired) + deleted_count
        if total_cleaned > 0:
            print(f"自动清理了 {total_cleaned} 条过期记录")

        return total_cleaned

    def update_from_ship_manager(self, ship_info: dict,
                                 in_reveal_area: bool,
                                 in_control_area: bool):
        """
        根据船舶状态更新通行记录

        Args:
            ship_info: 船舶信息
            in_reveal_area: 是否在揭示区
            in_control_area: 是否在控制河段
        """
        mmsi = ship_info.get('MMSI')
        name = ship_info.get('name', '')
        direction = ship_info.get('direction', 'unknown')

        if in_reveal_area and direction in ['up', 'down']:
            # 在揭示区内，创建或更新记录
            if mmsi not in self._active_cache:
                self.create_record(mmsi, name, direction)
            else:
                # 更新船舶名称
                record = self._active_cache[mmsi]
                if record.get('name') != name:
                    self.update_record(mmsi, name=name)

        elif mmsi in self._active_cache:
            record = self._active_cache[mmsi]

            if in_control_area and record.get('enter_channel_time', 0) == 0:
                # 进入控制河段，记录进漕时间
                self.record_enter_channel(mmsi)

            elif not in_reveal_area and record.get('exit_channel_time', 0) == 0:
                # 离开揭示区且未出漕，完成记录
                self.record_exit_channel(mmsi)

    def get_statistics(self, date_str: str = None) -> Dict:
        """获取统计信息"""
        return self.db.get_statistics(date_str)