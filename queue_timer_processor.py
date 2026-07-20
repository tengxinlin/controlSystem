# queue_timer_processor.py
from PyQt5.QtCore import QObject, QTimer, pyqtSignal
import time
from datetime import datetime
from typing import List, Dict


class QueueTimerProcessor(QObject):
    """队列处理器 - 使用定时器模式（在主线程中运行，便于调试）"""

    # 信号
    pending_updated = pyqtSignal(list)  # 待指挥队列更新
    commanded_updated = pyqtSignal(list)  # 已指挥队列更新
    control_area_updated = pyqtSignal(list)  # 控制河段队列更新
    show_signal_dialog = pyqtSignal(str,str, str)  # 显示信号确认对话框

    def __init__(self, queue_manager, get_signal_callback, parent=None):
        super().__init__(parent)
        self.queue_manager = queue_manager
        self.get_signal_callback = get_signal_callback
        self.update_interval = 15000  # 15秒 = 15000毫秒
        self.queue_manager.pending_queue_changed.connect(self.update_pending_queue)
        self.queue_manager.commanded_queue_changed.connect(self.update_commanded_queue)
        self.queue_manager.control_area_queue_changed.connect(self.update_control_queue)

        # 记录被取消的船舶（2分钟内不再弹窗）
        self.cancelled_ships = {}  # mmsi -> 取消时间

        # 对话框状态标志
        self.is_dialog_showing = False  # 是否正在显示对话框
        self.pending_dialog_ship = None  # 等待弹出对话框的船舶
        self.pending_dialog_signal = None  # 等待弹出对话框的信号类型

        # 创建定时器
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.process_all_queues)

        print(f"QueueTimerProcessor 初始化完成，更新间隔: {self.update_interval / 1000}秒")

    def update_pending_queue(self,queue):
        """更新pending_queue"""
        self.queue_manager.pending_queue=queue

    def update_commanded_queue(self,queue):
        """更新pending_queue"""
        self.queue_manager.commanded_queue=queue

    def update_control_queue(self,queue):
        """更新pending_queue"""
        self.queue_manager.control_area_queue=queue

    def start(self):
        """启动定时器"""
        self.timer.start(self.update_interval)
        print("队列定时器已启动")

        # 立即执行一次
        self.process_all_queues()

    def stop(self):
        """停止定时器"""
        self.timer.stop()
        print("队列定时器已停止")

    def process_all_queues(self):
        """处理所有队列（定时器回调）"""
        print(f"\n{'=' * 50}")
        print(f"开始处理队列 - {datetime.now().strftime('%H:%M:%S')}")
        print(f"{'=' * 50}")

        try:
            # 1. 处理待指挥队列
            self._process_pending_queue()

            # 2. 处理已指挥队列
            self._process_commanded_queue()

            # 3. 处理控制河段队列
            self._process_control_area_queue()

        except Exception as e:
            print(f"队列处理出错: {e}")
            import traceback
            traceback.print_exc()

        print(f"队列处理完成\n")

    def _is_ship_blocked(self, mmsi: str) -> bool:
        """检查船舶是否被阻止弹窗（2分钟内）"""
        if mmsi in self.cancelled_ships:
            elapsed = time.time() - self.cancelled_ships[mmsi]
            if elapsed < 120:  # 2分钟
                return True
            else:
                del self.cancelled_ships[mmsi]
        return False

    def _block_ship(self, mmsi: str):
        """阻止船舶弹窗（2分钟）"""
        self.cancelled_ships[mmsi] = time.time()
        print(f"🚫 船舶 {mmsi} 将在2分钟内不再弹窗")

    def _process_pending_queue(self):
        """处理待指挥队列 - 排序并判断揭示信号"""
        print("\n--- 处理待指挥队列 ---")
        # 如果正在显示对话框，跳过本次处理
        if self.is_dialog_showing:
            print(f"对话框正在显示中（船舶: {self.pending_dialog_ship}），跳过本次队列处理")
            return

        ships = self.queue_manager.get_pending_list()
        print(f"待指挥队列长度: {len(ships)}")


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

        if first_ship:
            mmsi = first_ship.get('mmsi')
            ship_name = first_ship.get('name')
            first_ship_direction = first_ship.get('calc_range')
            first_ship_is_arrived = first_ship.get('is_arrived', False)

            print(f"第一艘船舶: {ship_name}, 方向: {first_ship_direction}, 是否到达揭示区: {first_ship_is_arrived}")

            # 检查是否被阻止弹窗
            if self._is_ship_blocked(mmsi):
                print(f"船舶 {ship_name} 被阻止弹窗，跳过")
                self.pending_updated.emit(sorted_ships)
                return

            # 4. 判断是否需要揭示信号以及揭示什么信号
            signal_to_reveal = self._determine_signal_to_reveal(
                first_ship,
                commanded_ships,
                control_area_ships,
                sorted_ships
            )

            print(f"需要揭示的信号: {signal_to_reveal}")

            # 5. 如果需要揭示信号且尚未揭示，弹出确认对话框
            if signal_to_reveal != 'none' and not first_ship.get('signal_revealed', False):
                # 设置对话框状态标志，防止重复弹出
                self.is_dialog_showing = True
                self.pending_dialog_ship = ship_name
                self.pending_dialog_signal = signal_to_reveal

                print(f"准备弹出信号确认对话框: {ship_name} -> {signal_to_reveal}")
                # 发射信号显示对话框
                self.show_signal_dialog.emit(mmsi,ship_name, signal_to_reveal)

        # 6. 更新待指挥队列表格
        self.pending_updated.emit(sorted_ships)
        print(f"待指挥队列处理完成，已排序 {len(sorted_ships)} 艘")

    def _determine_signal_to_reveal(self, first_ship: dict,
                                    commanded_ships: List[dict],
                                    control_area_ships: List[dict],
                                    all_pending_ships: List[dict]) -> str:
        """
        判断需要揭示什么信号:”上水“、”下水“、”半杆“
        """
        if not first_ship:
            return 'none'

        first_ship_direction = first_ship.get('calc_range')
        first_ship_is_arrived = first_ship.get('is_arrived', False)

        if not first_ship_is_arrived:
            print(f"第一艘船舶 {first_ship.get('name')} 未到达揭示区，不揭示信号")
            return 'none'

        # 获取队列状态
        commanded_directions = [s.get('calc_range') for s in commanded_ships if s.get('calc_range')]
        has_commanded_up = 'up' in commanded_directions
        has_commanded_down = 'down' in commanded_directions

        control_directions = [s.get('direction') for s in control_area_ships if s.get('direction')]
        has_control_up = 'up' in control_directions
        has_control_down = 'down' in control_directions

        print(f"队列状态 - 第一艘船: {first_ship_direction}")
        print(f"已指挥队列 - 上水: {has_commanded_up}, 下水: {has_commanded_down}")
        print(f"控制河段队列 - 上水: {has_control_up}, 下水: {has_control_down}")

        # 下水船舶情况
        if first_ship_direction == 'down':
            if not commanded_ships and not control_area_ships:
                return '下水'
            if not commanded_ships and has_control_down:
                return '下水'
            if has_commanded_down:
                return '下水'
            if not commanded_ships and has_control_up:
                if self._has_up_pending_arrived(all_pending_ships):
                    return '半杆'

        # 上水船舶情况
        elif first_ship_direction == 'up':
            if not commanded_ships and not control_area_ships:
                return '上水'
            if has_commanded_up:
                return '上水'
            if has_control_up:
                return '上水'

        return 'none'

    def _has_up_pending_arrived(self, pending_ships: List[dict]) -> bool:
        """检查通行队列中是否有上水船舶且到达揭示区"""
        for ship in pending_ships:
            if ship.get('calc_range') == 'up' and ship.get('is_arrived', False):
                print(f"发现上水船舶 {ship.get('name')} 已到达揭示区")
                return True
        return False

    def _process_commanded_queue(self):
        """处理已指挥队列"""
        print("\n--- 处理已指挥队列 ---")

        ships = self.queue_manager.get_commanded_list()
        print(f"已指挥队列长度: {len(ships)}")

        if not ships:
            self.commanded_updated.emit([])
            return

        processed_ships = []
        current_time = time.time()

        for ship in ships:
            mmsi = ship.get('mmsi')
            ship_name = ship.get('name')
            command_time = ship.get('command_time', 0)

            if command_time > 0:
                elapsed_minutes = (current_time - command_time) / 60
                ship['elapsed_minutes'] = round(elapsed_minutes, 1)
            else:
                ship['elapsed_minutes'] = 0

            # 检查是否需要移除
            should_remove = False
            remove_reason = ""

            if not ship.get('in_calc_range', False):
                should_remove = True
                remove_reason = "离开计算范围"
            elif ship.get('elapsed_minutes', 0) > 30:
                should_remove = True
                remove_reason = "超过30分钟"

            if should_remove:
                self.queue_manager.remove_from_commanded(mmsi)
                self._remove_passage_record(mmsi)
                print(f"🗑️ 船舶 {ship_name} ({mmsi}) 从已指挥队列移除，原因: {remove_reason}")
            else:
                processed_ships.append(ship)

        sorted_ships = sorted(processed_ships, key=lambda x: x.get('elapsed_minutes', 0))
        self.commanded_updated.emit(sorted_ships)
        print(f"已指挥队列处理完成: {len(sorted_ships)}艘")

    def _process_control_area_queue(self):
        """处理控制河段内队列"""
        print("\n--- 处理控制河段队列 ---")

        ships = self.queue_manager.get_control_area_list()
        print(f"控制河段队列长度: {len(ships)}")

        if not ships:
            self.control_area_updated.emit([])
            return

        processed_ships = []
        current_time = time.time()

        for ship in ships:
            enter_time = ship.get('enter_channel_time', 0)

            if enter_time > 0:
                enter_time_str = datetime.fromtimestamp(enter_time).strftime('%H:%M:%S')
                elapsed_minutes = (current_time - enter_time) / 60
                ship['enter_time_str'] = enter_time_str
                ship['elapsed_minutes'] = round(elapsed_minutes, 1)
            else:
                ship['enter_time_str'] = "-"
                ship['elapsed_minutes'] = 0

            processed_ships.append(ship)

        sorted_ships = sorted(processed_ships, key=lambda x: x.get('enter_control_time', 0))
        self.control_area_updated.emit(sorted_ships)
        print(f"控制河段队列处理完成: {len(sorted_ships)}艘")

    def on_dialog_closed(self):
        """
        对话框关闭时的回调（在主窗口中调用）
        """
        # 清除对话框状态标志
        self.is_dialog_showing = False

        self.pending_dialog_ship = None
        self.pending_dialog_signal = None


    def _handle_signal_confirmed(self, ship_name: str, signal_type: str):
        """处理信号确认"""
        # 找到待指挥队列中的对应船舶
        ships = self.queue_manager.get_pending_list()
        target_ship = None
        target_mmsi = None

        for ship in ships:
            if ship.get('name') == ship_name:
                target_ship = ship.copy()
                target_mmsi = ship.get('mmsi')
                break

        if target_ship and target_mmsi:

            # 更新船舶信息
            target_ship['signal_revealed'] = True
            target_ship['reveal_time'] = time.time()
            target_ship['reveal_signal'] = signal_type
            target_ship['command_time'] = time.time()

            # 从待指挥队列移除
            self.queue_manager.remove_from_pending(target_mmsi)

            # 添加到已指挥队列
            self.queue_manager.add_to_commanded(target_mmsi, target_ship)

            print(f"🔔 船舶 {ship_name} ({target_mmsi}) 信号已揭示: {signal_type}，已移至已指挥队列")
    def _remove_passage_record(self, mmsi: str):
        """移除船舶通行记录"""
        if hasattr(self.queue_manager, 'passage_record_manager'):
            self.queue_manager.passage_record_manager.delete_record(mmsi)

    def _get_ship_mmsi_by_name(self, ship_name: str) -> str:
        """根据船名获取MMSI"""
        ships = self.queue_manager.get_pending_list()
        for ship in ships:
            if ship.get('name') == ship_name:
                return ship.get('mmsi')
        return None