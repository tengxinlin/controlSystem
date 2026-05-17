# queue_processor.py
from PyQt5.QtCore import QThread, pyqtSignal
import time
from datetime import datetime
from typing import List, Dict


class QueueProcessor(QThread):
    """队列处理器 - 定时遍历并处理三个队列"""

    # 信号
    pending_updated = pyqtSignal(list)  # 待指挥队列更新
    commanded_updated = pyqtSignal(list)  # 已指挥队列更新
    control_area_updated = pyqtSignal(list)  # 控制河段队列更新

    def __init__(self, queue_manager, get_signal_callback):
        super().__init__()
        self.queue_manager = queue_manager
        self.get_signal_callback = get_signal_callback
        self.is_running = True
        self.update_interval = 15  # 15秒更新一次

    def run(self):
        """线程主循环"""
        while self.is_running:
            try:
                # 1. 处理待指挥队列
                self._process_pending_queue()

                # 2. 处理已指挥队列
                self._process_commanded_queue()

                # 3. 处理控制河段队列
                self._process_control_area_queue()

            except Exception as e:
                print(f"队列处理出错: {e}")

            # 等待下一次更新
            time.sleep(self.update_interval)

    def _process_pending_queue(self):
        """处理待指挥队列 - 排序并判断揭示信号"""
        ships = self.queue_manager.get_pending_list()

        if not ships:
            self.pending_updated.emit([])
            return

        # 1. 根据到达上界限标的时间排序（升序，时间短的优先）
        sorted_ships = sorted(ships, key=lambda x: x.get('time_minutes', 9999))

        # 2. 获取已指挥队列和控制河段队列
        commanded_ships = self.queue_manager.get_commanded_list()
        control_area_ships = self.queue_manager.get_control_area_list()

        # 3. 获取第一艘船舶
        first_ship = sorted_ships[0] if sorted_ships else None

        # 4. 判断是否需要揭示信号以及揭示什么信号
        signal_to_reveal = self._determine_signal_to_reveal(
            first_ship,
            commanded_ships,
            control_area_ships,
            sorted_ships
        )

        # 5. 根据判断结果揭示信号
        if signal_to_reveal != 'none':
            print(f"🚦 揭示信号: {signal_to_reveal}")
            # 这里调用实际的控制信号函数
            self._reveal_signal(signal_to_reveal)

        # 6. 更新待指挥队列表格
        self.pending_updated.emit(sorted_ships)

        print(f"待指挥队列处理完成: {len(sorted_ships)}艘, 揭示信号: {signal_to_reveal}")

    def _determine_signal_to_reveal(self, first_ship: dict,
                                    commanded_ships: List[dict],
                                    control_area_ships: List[dict],
                                    all_pending_ships: List[dict]) -> str:
        """
        判断需要揭示什么信号

        Returns:
            'up': 上水信号
            'down': 下水信号
            'half': 半杆信号
            'none': 不揭示信号
        """
        if not first_ship:
            return 'none'

        # 获取第一艘船舶的信息
        first_ship_direction = first_ship.get('calc_range')  # 'up' 或 'down'
        first_ship_is_arrived = first_ship.get('is_arrived', False)  # 是否到达揭示区

        # 如果第一艘船舶没有到达揭示区，不揭示信号
        if not first_ship_is_arrived:
            print(f"第一艘船舶 {first_ship.get('name')} 未到达揭示区，不揭示信号")
            return 'none'

        # 获取已指挥队列中的船舶方向
        commanded_directions = [s.get('calc_range') for s in commanded_ships if s.get('calc_range')]
        has_commanded_up = 'up' in commanded_directions
        has_commanded_down = 'down' in commanded_directions

        # 获取控制河段队列中的船舶方向
        control_directions = [s.get('direction') for s in control_area_ships if s.get('direction')]
        has_control_up = 'up' in control_directions
        has_control_down = 'down' in control_directions

        print(f"队列状态 - 第一艘船: {first_ship_direction}, 已到达: {first_ship_is_arrived}")
        print(f"已指挥队列 - 上水: {has_commanded_up}, 下水: {has_commanded_down}")
        print(f"控制河段队列 - 上水: {has_control_up}, 下水: {has_control_down}")

        # ========== 下水船舶情况 ==========
        if first_ship_direction == 'down':
            # 情况1: 已指挥队列为空且控制河段队列为空，揭示下水信号
            if not commanded_ships and not control_area_ships:
                return 'down'

            # 情况2: 已指挥队列为空，控制河段队列有船舶且是下水船舶，揭示下水信号
            if not commanded_ships and has_control_down:
                return 'down'

            # 情况3: 已指挥队列有船舶且船舶状态是下水，揭示下水信号
            if has_commanded_down:
                return 'down'

            # 情况4: 已指挥队列为空，控制河段队列有船舶且是上水船舶
            if not commanded_ships and has_control_up:
                # 检查通行队列中是否有上水船舶且到达揭示区
                has_up_pending_arrived = self._has_up_pending_arrived(all_pending_ships)
                if has_up_pending_arrived:
                    return 'half'  # 半杆信号

        # ========== 上水船舶情况 ==========
        elif first_ship_direction == 'up':
            # 情况5: 已指挥队列为空且控制河段队列为空，揭示上水信号
            if not commanded_ships and not control_area_ships:
                return 'up'

            # 情况6: 已指挥队列有船舶且船舶揭示上水，揭示上水信号
            if has_commanded_up:
                return 'up'

            # 情况7: 控制河段队列中有船舶且船舶信号是上水，揭示上水信号
            if has_control_up:
                return 'up'

        return 'none'

    def _has_up_pending_arrived(self, pending_ships: List[dict]) -> bool:
        """
        检查通行队列中是否有上水船舶且到达揭示区

        Returns:
            True: 有上水船舶已到达揭示区
        """
        for ship in pending_ships:
            if ship.get('calc_range') == 'up' and ship.get('is_arrived', False):
                print(f"发现上水船舶 {ship.get('name')} 已到达揭示区")
                return True
        return False

    def _reveal_signal(self, signal_type: str):
        """
        揭示信号

        Args:
            signal_type: 'up', 'down', 'half'
        """
        # 这里调用实际的信号控制函数
        # 例如：控制LED灯、发送MQTT消息等

        if signal_type == 'up':
            print("🔴 揭示上水信号")
            # self.control_up_signal(True)
        elif signal_type == 'down':
            print("🔵 揭示下水信号")
            # self.control_down_signal(True)
        elif signal_type == 'half':
            print("🟡 揭示半杆信号")
            # self.control_half_signal(True)


    def _process_commanded_queue(self):
        """处理已指挥队列"""
        ships = self.queue_manager.get_commanded_list()

        if not ships:
            self.commanded_updated.emit([])
            return

        processed_ships = []
        current_time = time.time()

        for ship in ships:
            mmsi = ship.get('mmsi')
            ship_name = ship.get('name')
            command_time = ship.get('command_time', 0)
            calc_range = ship.get('calc_range')

            # 计算揭示时间（距离指挥过去了多少分钟）
            if command_time > 0:
                elapsed_minutes = (current_time - command_time) / 60
                ship['elapsed_minutes'] = round(elapsed_minutes, 1)
            else:
                ship['elapsed_minutes'] = 0

            # 检查是否需要从已指挥队列移除
            # 条件：船舶已离开计算范围 或 超过30分钟
            should_remove = False
            remove_reason = ""

            if not ship.get('in_calc_range', False):
                should_remove = True
                remove_reason = "离开计算范围"
            elif elapsed_minutes > 30:
                should_remove = True
                remove_reason = "超过30分钟"

            if should_remove:
                # 从已指挥队列移除
                self.queue_manager.remove_from_commanded(mmsi)
                # 移除船舶通行记录
                self._remove_passage_record(mmsi)
                print(f"🗑️ 船舶 {ship_name} ({mmsi}) 从已指挥队列移除，原因: {remove_reason}")
            else:
                processed_ships.append(ship)

        # 按揭示时间排序
        sorted_ships = sorted(processed_ships, key=lambda x: x.get('elapsed_minutes', 0))

        # 更新已指挥队列表格
        self.commanded_updated.emit(sorted_ships)

        print(f"已指挥队列处理完成: {len(sorted_ships)}艘")

    def _process_control_area_queue(self):
        """处理控制河段内队列"""
        ships = self.queue_manager.get_control_area_list()

        if not ships:
            self.control_area_updated.emit([])
            return

        processed_ships = []
        current_time = time.time()

        for ship in ships:
            mmsi = ship.get('mmsi')
            ship_name = ship.get('name')
            enter_time = ship.get('enter_control_time', 0)

            # 计算进入控制河段的时间
            if enter_time > 0:
                enter_time_str = datetime.fromtimestamp(enter_time).strftime('%H:%M:%S')
                elapsed_minutes = (current_time - enter_time) / 60
                ship['enter_time_str'] = enter_time_str
                ship['elapsed_minutes'] = round(elapsed_minutes, 1)
            else:
                ship['enter_time_str'] = "-"
                ship['elapsed_minutes'] = 0

            processed_ships.append(ship)

        # 按进入时间排序（先进入的在前）
        sorted_ships = sorted(processed_ships, key=lambda x: x.get('enter_control_time', 0))

        # 更新控制河段队列表格
        self.control_area_updated.emit(sorted_ships)

        print(f"控制河段队列处理完成: {len(sorted_ships)}艘")

    def _remove_passage_record(self, mmsi: str):
        """移除船舶通行记录"""
        if hasattr(self.queue_manager, 'passage_record_manager'):
            self.queue_manager.passage_record_manager.delete_record(mmsi)

    def stop(self):
        """停止线程"""
        self.is_running = False
        self.quit()
        self.wait()