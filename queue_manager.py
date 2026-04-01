# queue_manager.py
from typing import Dict, List, Optional, Any
from datetime import datetime
import time
from PyQt5.QtCore import QObject, pyqtSignal


class QueueManager(QObject):
    """队列管理器 - 管理所有船舶队列"""

    # 信号
    pending_queue_changed = pyqtSignal()  # 待指挥队列变化
    commanded_queue_changed = pyqtSignal()  # 已指挥队列变化
    control_area_queue_changed = pyqtSignal()  # 控制河段区域内队列变化

    def __init__(self,passage_record_manager):
        super().__init__()
        self.passage_record_manager = passage_record_manager#船舶记录管理器
        # 待指挥队列（在上下水计算范围内，等待指挥）
        self.pending_queue: Dict[str, dict] = {}  # mmsi -> ship_info

        # 已指挥队列（已经发送过指令，但还在计算范围内）
        self.commanded_queue: Dict[str, dict] = {}  # mmsi -> ship_info

        # 控制河段区域内队列（已指挥且进入控制河段）
        self.control_area_queue: Dict[str, dict] = {}  # mmsi -> ship_info

        # 船舶过期时间（秒）
        self.ship_timeout = 300  # 5分钟

    def update_ship_queue_status(self, mmsi: str, ship_info: dict,
                                 in_up_calc: bool, in_down_calc: bool,
                                 in_control_area: bool, in_park: bool):
        """
        更新船舶在队列中的状态

        Args:
            mmsi: 船舶MMSI
            ship_info: 船舶信息
            in_up_calc: 是否在上游计算范围内
            in_down_calc: 是否在下游计算范围内
            in_control_area: 是否在控制河段区域内（界限标范围内）
            in_park: 是否在停泊区内
        """
        in_calc_range = (in_up_calc or in_down_calc) and not in_park
        calc_range_type = 'up' if in_up_calc else ('down' if in_down_calc else None)

        # 更新时间戳
        ship_info['last_update'] = time.time()
        ship_info['calc_range'] = calc_range_type
        ship_info['in_control_area'] = in_control_area

        # 1. 首先处理控制河段区域队列
        if in_control_area and not in_park:
            # 如果在控制河段内且不在停泊区
            if mmsi not in self.control_area_queue:
                # 新进入控制河段
                self.control_area_queue[mmsi] = ship_info.copy()
                ship_info['enter_control_time'] = time.time()
                print(f"🚢 船舶 {ship_info.get('name', mmsi)} 进入控制河段区域")
                self.control_area_queue_changed.emit()

            # 如果在已指挥队列中，从已指挥队列移除
            if mmsi in self.commanded_queue:
                del self.commanded_queue[mmsi]
                print(f"➡️ 船舶 {ship_info.get('name', mmsi)} 从已指挥队列移除（进入控制河段）")
                self.commanded_queue_changed.emit()

        else:
            # 不在控制河段内，从控制河段队列移除
            if mmsi in self.control_area_queue:
                del self.control_area_queue[mmsi]
                print(f"⬅️ 船舶 {ship_info.get('name', mmsi)} 离开控制河段区域")
                self.control_area_queue_changed.emit()

        # 2. 处理待指挥队列和已指挥队列
        if in_calc_range and not in_control_area:
            # 在计算范围内且不在控制河段内
            if mmsi in self.commanded_queue:
                # 已经在已指挥队列，更新信息
                self.commanded_queue[mmsi].update(ship_info)
                self.commanded_queue_changed.emit()
            elif mmsi not in self.pending_queue:
                # 不在待指挥队列，加入待指挥队列
                ship_info['enter_pending_time'] = time.time()
                self.pending_queue[mmsi] = ship_info.copy()
                print(f"➕ 船舶 {ship_info.get('name', mmsi)} 加入待指挥队列 ({calc_range_type})")
                self.pending_queue_changed.emit()
            else:
                # 已在待指挥队列，更新信息
                self.pending_queue[mmsi].update(ship_info)
                self.pending_queue_changed.emit()

        else:
            # 不在计算范围内，从待指挥队列和已指挥队列移除
            if mmsi in self.pending_queue:
                del self.pending_queue[mmsi]
                print(f"❌ 船舶 {ship_info.get('name', mmsi)} 从待指挥队列移除")
                self.pending_queue_changed.emit()

            # 注意：已指挥队列的船舶如果离开计算范围，仍然保留在已指挥队列中
            # 除非超过过期时间

    def command_ship(self, mmsi: str, command_data: dict = None):
        """
        指挥船舶 - 从待指挥队列移到已指挥队列

        Args:
            mmsi: 船舶MMSI
            command_data: 指挥数据

        Returns:
            bool: 是否成功
        """
        if mmsi not in self.pending_queue:
            print(f"船舶 {mmsi} 不在待指挥队列中")
            return False

        ship_info = self.pending_queue.pop(mmsi)
        ship_info['command_time'] = time.time()
        ship_info['command_data'] = command_data or {}

        self.commanded_queue[mmsi] = ship_info

        print(f"📡 指挥船舶 {ship_info.get('name', mmsi)}")
        self.pending_queue_changed.emit()
        self.commanded_queue_changed.emit()
        return True

    def batch_command_ships(self, mmsi_list: List[str], command_data: dict = None):
        """批量指挥船舶"""
        count = 0
        for mmsi in mmsi_list:
            if self.command_ship(mmsi, command_data):
                count += 1
        return count

    def remove_from_pending(self, mmsi: str):
        """从待指挥队列移除"""
        if mmsi in self.pending_queue:
            ship_info = self.pending_queue.pop(mmsi)
            print(f"移除船舶 {ship_info.get('name', mmsi)} 从待指挥队列")
            self.pending_queue_changed.emit()
            return True
        return False

    def remove_from_commanded(self, mmsi: str):
        """从已指挥队列移除"""
        if mmsi in self.commanded_queue:
            ship_info = self.commanded_queue.pop(mmsi)
            print(f"移除船舶 {ship_info.get('name', mmsi)} 从已指挥队列")
            self.commanded_queue_changed.emit()
            return True
        return False

    def remove_from_control_area(self, mmsi: str):
        """从控制河段队列移除"""
        if mmsi in self.control_area_queue:
            ship_info = self.control_area_queue.pop(mmsi)
            print(f"移除船舶 {ship_info.get('name', mmsi)} 从控制河段队列")
            self.control_area_queue_changed.emit()
            return True
        return False

    def clean_expired_ships(self):
        """清理过期船舶"""
        current_time = time.time()
        timeout = self.ship_timeout
        removed_count = 0

        # 清理待指挥队列
        expired_pending = []
        for mmsi, ship in self.pending_queue.items():
            last = ship.get('last_update', ship.get('enter_pending_time', 0))
            if current_time - last > timeout:
                expired_pending.append(mmsi)

        for mmsi in expired_pending:
            del self.pending_queue[mmsi]
            removed_count += 1

        # 清理已指挥队列
        expired_commanded = []
        for mmsi, ship in self.commanded_queue.items():
            last = ship.get('last_update', ship.get('command_time', 0))
            if current_time - last > timeout:
                expired_commanded.append(mmsi)

        for mmsi in expired_commanded:
            del self.commanded_queue[mmsi]
            removed_count += 1

        # 清理控制河段队列
        expired_control = []
        for mmsi, ship in self.control_area_queue.items():
            last = ship.get('last_update', ship.get('enter_control_time', 0))
            if current_time - last > timeout:
                expired_control.append(mmsi)

        for mmsi in expired_control:
            del self.control_area_queue[mmsi]
            removed_count += 1

        if removed_count > 0:
            print(f"清理了 {removed_count} 艘过期船舶")
            self.pending_queue_changed.emit()
            self.commanded_queue_changed.emit()
            self.control_area_queue_changed.emit()

        return removed_count

    def get_pending_list(self) -> List[dict]:
        """获取待指挥队列列表"""
        ships = list(self.pending_queue.values())
        ships.sort(key=lambda x: x.get('enter_pending_time', 0))
        return ships

    def get_commanded_list(self) -> List[dict]:
        """获取已指挥队列列表"""
        ships = list(self.commanded_queue.values())
        ships.sort(key=lambda x: x.get('command_time', 0))
        return ships

    def get_control_area_list(self) -> List[dict]:
        """获取控制河段区域内队列列表"""
        ships = list(self.control_area_queue.values())
        ships.sort(key=lambda x: x.get('enter_control_time', 0))
        return ships

    def get_queue_stats(self) -> dict:
        """获取队列统计信息"""
        return {
            'pending': len(self.pending_queue),
            'commanded': len(self.commanded_queue),
            'control_area': len(self.control_area_queue),
            'total': len(self.pending_queue) + len(self.commanded_queue) + len(self.control_area_queue)
        }

    def clear_all_queues(self):
        """
        清空所有队列（切换控制河段时调用）
        保留实例，只清空数据
        """
        # 记录被清空的船舶数量用于日志
        pending_count = len(self.pending_queue)
        commanded_count = len(self.commanded_queue)
        control_count = len(self.control_area_queue)

        # 清空所有队列
        self.pending_queue.clear()
        self.commanded_queue.clear()
        self.control_area_queue.clear()

        # 发射信号通知界面更新
        self.pending_queue_changed.emit()
        self.commanded_queue_changed.emit()
        self.control_area_queue_changed.emit()

        print(f"🔄 切换控制河段：已清空队列 (待指挥:{pending_count}, 已指挥:{commanded_count}, 控制区内:{control_count})")

        return pending_count + commanded_count + control_count