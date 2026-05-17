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
        direction = ship_info.get('status', 'unknown')

        # 更新时间戳
        ship_info['last_update'] = time.time()
        ship_info['calc_range'] = calc_range_type
        ship_info['in_control_area'] = in_control_area

        # 获取跨线检测结果
        cross_up_whistle = ship_info.get('cross_up_whistle', False)
        cross_down_whistle = ship_info.get('cross_down_whistle', False)
        cross_up_bound = ship_info.get('cross_up_bound', False)
        cross_down_bound = ship_info.get('cross_down_bound', False)

        # ========== 如果船舶在停泊区内，从所有队列中移除 ==========
        if in_park:
            # 从待指挥队列移除
            if mmsi in self.pending_queue:
                del self.pending_queue[mmsi]
                print(f"🚢 船舶 {ship_info.get('name', mmsi)} 进入停泊区，从待指挥队列移除")


            # 从已指挥队列移除
            if mmsi in self.commanded_queue:
                del self.commanded_queue[mmsi]
                print(f"🚢 船舶 {ship_info.get('name', mmsi)} 进入停泊区，从已指挥队列移除")


            # 从控制河段队列移除
            if mmsi in self.control_area_queue:
                del self.control_area_queue[mmsi]
                print(f"🚢 船舶 {ship_info.get('name', mmsi)} 进入停泊区，从控制河段队列移除")


            # 不再继续处理其他队列逻辑
            return

        # ========== 2. 检查方向是否与计算范围匹配 ==========
        # 如果上水船舶不在上游计算范围，或下水船舶不在下游计算范围，说明方向误判
        is_direction_mismatch = (in_up_calc and  direction != 'up') or \
                                (direction != 'down' and  in_down_calc)

        if is_direction_mismatch and mmsi in self.pending_queue:
            # 方向误判，从待指挥队列移除
            del self.pending_queue[mmsi]
            print(f"⚠️ 船舶 ({mmsi}) 方向误判（{direction}），从待指挥队列移除")
            return

        # 检查是否刚到达揭示区（is_arrived 变为 True）
        previous_is_arrived = False
        if mmsi in self.pending_queue:
            previous_is_arrived = self.pending_queue[mmsi].get('is_arrived', False)

        current_is_arrived = ship_info.get('is_arrived', False)

        # 记录到达揭示区的时间戳
        if current_is_arrived and not previous_is_arrived:
            ship_info['arrival_time'] = time.time()
            print(f"⏰ 船舶 {ship_info.get('name', mmsi)} 到达揭示区")
            self._create_passage_record_if_not_exists(mmsi, ship_info)

        # ========== 处理鸣笛标跨越（揭示区） ==========
        # 上水船舶：跨过下鸣笛标进入上水揭示区
        # 下水船舶：跨过上鸣笛标进入下水揭示区
        # ========== 3. 处理揭示区（鸣笛标跨越） ==========
        # 判断是否进入揭示区
        is_entering_reveal = False
        reveal_type = None

        if direction == 'up' and cross_down_whistle:
            is_entering_reveal = True
            reveal_type = 'up'
            print(f"⏰ 船舶  ({mmsi}) 进入上水揭示区（跨过下鸣笛标）")
        elif direction == 'down' and cross_up_whistle:
            is_entering_reveal = True
            reveal_type = 'down'
            print(f"⏰ 船舶 {mmsi} 进入下水揭示区（跨过上鸣笛标）")

        # 检查是否刚到达揭示区
        previous_is_arrived = False
        if mmsi in self.pending_queue:
            previous_is_arrived = self.pending_queue[mmsi].get('is_arrived', False)

        current_is_arrived = ship_info.get('is_arrived', False) or is_entering_reveal

        # 记录到达揭示区的时间戳
        if current_is_arrived and not previous_is_arrived:
            ship_info['arrival_time'] = time.time()
            print(
                f"⏰ 船舶 {ship_info.get('name', mmsi)} 到达揭示区，时间: {datetime.fromtimestamp(ship_info['arrival_time']).strftime('%Y-%m-%d %H:%M:%S')}")

            # 创建通行记录（如果没有）
            self._create_passage_record_if_not_exists(mmsi, ship_info)

            #如果是下水船舶
            if reveal_type == 'down':
                #记录预告时间
                self._update_passage_record_notice_time(mmsi, time.time())



        # ========== 处理界限标跨越（控制河段） ==========
        # 记录进漕时间（进入控制河段）
        previous_in_control = False
        if mmsi in self.commanded_queue:
            previous_in_control = self.pending_queue[mmsi].get('in_control_area', False)

        # 判断是否进入控制河段（跨过相应的界限标）
        entering_control = False
        if direction == 'up' and cross_down_bound:
            entering_control = True
            print(f"🚪 船舶 {ship_info.get('name', mmsi)} 进入控制河段（跨过下界限标）")
        elif direction == 'down' and cross_up_bound:
            entering_control = True
            print(f"🚪 船舶 {ship_info.get('name', mmsi)} 进入控制河段（跨过上界限标）")

        # 刚进入控制河段
        if (in_control_area or entering_control) and not previous_in_control and not in_park:
            enter_time = time.time()
            ship_info['enter_channel_time'] = enter_time
            print(
                f"🚪 船舶 {ship_info.get('name', mmsi)} 进漕时间: {datetime.fromtimestamp(enter_time).strftime('%Y-%m-%d %H:%M:%S')}")

            # 更新通行记录的进漕时间
            self._update_passage_record_enter_time(mmsi, enter_time)

        # 判断是否离开控制河段（跨过相应的界限标）
        leaving_control = False
        if direction == 'up' and cross_up_bound:
            leaving_control = True
            print(f"🚪 船舶 {ship_info.get('name', mmsi)} 离开控制河段（跨过上界限标）")
        elif direction == 'down' and cross_down_bound:
            leaving_control = True
            print(f"🚪 船舶 {ship_info.get('name', mmsi)} 离开控制河段（跨过下界限标）")

        # 刚离开控制河段
        if (not in_control_area or leaving_control) and previous_in_control and not in_park:
            exit_time = time.time()
            ship_info['exit_channel_time'] = exit_time

            # 计算通过时间
            enter_time = ship_info.get('enter_channel_time', 0)
            if enter_time > 0:
                passage_minutes = (exit_time - enter_time) / 60
                print(
                    f"🚪 船舶 {ship_info.get('name', mmsi)} 出漕时间: {datetime.fromtimestamp(exit_time).strftime('%Y-%m-%d %H:%M:%S')}, 通过时间: {passage_minutes:.1f}分钟")

            # 更新通行记录的出漕时间
            self._update_passage_record_exit_time(mmsi, exit_time)

        # 添加用于表格显示的信息
        ship_info['time_minutes'] = ship_info.get('time_minutes', 0)  # 到达上界限标的时间（分钟）
        ship_info['is_arrived'] = ship_info.get('is_arrived', False)  # 是否到达揭示区
        ship_info['arrival_time'] = ship_info.get('arrival_time', 0)  # 到达揭示区的时间戳

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

            elif mmsi not in self.pending_queue:
                # 不在待指挥队列，加入待指挥队列
                ship_info['enter_pending_time'] = time.time()
                self.pending_queue[mmsi] = ship_info.copy()
                print(f"➕ 船舶 {ship_info.get('name', mmsi)} 加入待指挥队列 ({calc_range_type})")

            else:
                # 已在待指挥队列，更新信息
                self.pending_queue[mmsi].update(ship_info)


        else:
            # 不在计算范围内，从待指挥队列和已指挥队列移除
            if mmsi in self.pending_queue:
                del self.pending_queue[mmsi]
                print(f"❌ 船舶 {ship_info.get('name', mmsi)} 从待指挥队列移除")



    def _update_passage_record_enter_time(self, mmsi: str, enter_time: float):
        """
        更新通行记录的进漕时间

        Args:
            mmsi: 船舶MMSI
            enter_time: 进漕时间戳
        """
        try:
            if not hasattr(self, 'passage_record_manager') or not self.passage_record_manager:
                return

            # 获取船舶的活跃通行记录
            active_records = self.passage_record_manager.get_active_records()
            for record in active_records:
                if record.get('mmsi') == mmsi:
                    # 更新进漕时间
                    self.passage_record_manager.update_record(
                        mmsi,
                        enter_channel_time=int(enter_time)
                    )
                    print(f"📝 更新通行记录进漕时间: {record.get('name', mmsi)}")
                    break

        except Exception as e:
            print(f"更新通行记录进漕时间失败: {e}")

    def _update_passage_record_notice_time(self, mmsi: str, notice_time: float):
        """
        更新通行记录的预告时间

        Args:
            mmsi: 船舶MMSI
            notice_time: 预告时间戳
        """
        try:
            if not hasattr(self, 'passage_record_manager') or not self.passage_record_manager:
                return

            # 获取船舶的活跃通行记录
            active_records = self.passage_record_manager.get_active_records()
            for record in active_records:
                if record.get('mmsi') == mmsi:
                    # 更新进漕时间
                    self.passage_record_manager.update_record(
                        mmsi,
                        forecast_time=int(notice_time)
                    )
                    print(f"📝 更新通行记录预告时间: {record.get('name', mmsi)}")
                    break

        except Exception as e:
            print(f"更新通行记录进漕时间失败: {e}")
    def _update_passage_record_exit_time(self, mmsi: str, exit_time: float):
        """
        更新通行记录的出漕时间，并完成记录

        Args:
            mmsi: 船舶MMSI
            exit_time: 出漕时间戳
        """
        try:
            if not hasattr(self, 'passage_record_manager') or not self.passage_record_manager:
                return

            # 获取船舶的活跃通行记录
            active_records = self.passage_record_manager.get_active_records()
            for record in active_records:
                if record.get('mmsi') == mmsi:
                    # 更新出漕时间并完成记录
                    self.passage_record_manager.record_exit_channel(mmsi, int(exit_time))
                    print(f"📝 更新通行记录出漕时间: {record.get('name', mmsi)}")
                    break

        except Exception as e:
            print(f"更新通行记录出漕时间失败: {e}")

    def _create_passage_record_if_not_exists(self, mmsi: str, ship_info: dict):
        """
        如果船舶没有通行记录，则创建新的通行记录

        Args:
            mmsi: 船舶MMSI
            ship_info: 船舶信息
        """
        try:
            # 检查是否已有活跃的通行记录
            existing_record = None
            if hasattr(self, 'passage_record_manager') and self.passage_record_manager:
                # 获取活跃记录
                active_records = self.passage_record_manager.get_active_records()
                for record in active_records:
                    if record.get('mmsi') == mmsi:
                        existing_record = record
                        break

            # 如果没有通行记录，创建新的
            if existing_record is None:
                # 获取必要的船舶信息
                name = ship_info.get('name', '')
                direction = ship_info.get('status', 'unknown')

                # 确定方向
                if direction == 'up' or ship_info.get('calc_range') == 'up':
                    direction = 'up'
                elif direction == 'down' or ship_info.get('calc_range') == 'down':
                    direction = 'down'
                else:
                    # 如果无法确定方向，不创建记录
                    print(f"⚠️ 无法确定船舶 {name} ({mmsi}) 的方向，跳过创建通行记录")
                    return

                # 创建通行记录
                if hasattr(self, 'passage_record_manager') and self.passage_record_manager:
                    record = self.passage_record_manager.create_record(
                        mmsi=mmsi,
                        name=name,
                        direction=direction
                    )
                    if record:
                        print(f"📝 创建通行记录: {name} ({mmsi}) - {direction}")
                    else:
                        print(f"⚠️ 创建通行记录失败: {name} ({mmsi})")

        except Exception as e:
            print(f"创建通行记录时出错: {e}")

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