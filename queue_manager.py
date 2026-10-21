# queue_manager.py
from typing import Dict, List, Optional, Any
from datetime import datetime
import time
from PyQt5.QtCore import QObject, pyqtSignal
from numpy.core.records import record


class QueueManager(QObject):
    """队列管理器 - 管理所有船舶队列"""

    # 信号
    pending_queue_changed = pyqtSignal(dict)  # 待指挥队列变化
    commanded_queue_changed = pyqtSignal(dict)  # 已指挥队列变化
    control_area_queue_changed = pyqtSignal(dict)  # 控制河段区域内队列变化
    upload_passage_record=pyqtSignal(dict) #需要上传到服务器的通行记录


    def __init__(self,passage_record_manager,get_signal_callback,log_current_message,current_reach,get_api_service):
        super().__init__()
        self.passage_record_manager = passage_record_manager#船舶记录管理器
        self.get_signal_callback = get_signal_callback
        self.log_current_message = log_current_message
        self.current_reach=current_reach
        self.get_api_service=get_api_service

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
        更新船舶在队列中的状态（重构版）
        """
        try:
            direction = ship_info.get('status', 'unknown')
            in_calc_range = ((in_up_calc and direction=='up') or (in_down_calc and direction=='down')) and not in_park
            calc_range_type = 'up' if in_up_calc else ('down' if in_down_calc else None)


            # 更新时间戳
            ship_info['last_update'] = time.time()
            ship_info['calc_range'] = calc_range_type
            ship_info['in_control_area'] = in_control_area
            ship_info['in_calc_range'] = in_calc_range

            # 获取跨线检测结果
            cross_up_whistle = ship_info.get('cross_up_whistle', False)
            cross_down_whistle = ship_info.get('cross_down_whistle', False)
            cross_up_bound = ship_info.get('cross_up_bound', False)
            cross_down_bound = ship_info.get('cross_down_bound', False)

            # ----- 1. 停泊区：直接移除 -----
            if in_park:
                self._remove_from_all_queues(mmsi, ship_info.get('name', mmsi))
                return





            # ----- 辅助：获取当前控制河段信号（需外部提供）-----
            current_signal = self.get_signal_callback()  # '上水', '下水', '半杆'、‘关闭’

            # ----- 3. 下水船舶处理（在下水范围内且不在已指挥队列）-----
            if direction == 'down' and in_down_calc and mmsi not in self.commanded_queue:
                # 判断是否在下水揭示区
                if ship_info.get('is_arrived', False) or ship_info.get('cross_up_whistle', False):
                    self._create_passage_record_if_not_exists(mmsi, ship_info)
                    if ship_info.get('cross_up_whistle', False):
                        self._update_passage_record_notice_time(mmsi, time.time())
                        self.log_current_message(f"⏰ 下水船舶 {ship_info.get('name', mmsi)} 预告时间已记录")

                    if current_signal == '上水':
                        self._add_passage_remark(mmsi, "松车下")
                        self.log_current_message(f"⚠️ 现在是上水信号，请船舶{ship_info.get('name', mmsi)}松车，等待上水信号完成")

                self._add_or_update_pending(mmsi, ship_info)
                return

            # ----- 4. 上水船舶处理（在上水范围内且不在已指挥队列）-----
            elif direction == 'up' and in_up_calc and mmsi not in self.commanded_queue:
                if ship_info.get('is_arrived', False) or ship_info.get('cross_down_whistle', False):
                    self._create_passage_record_if_not_exists(mmsi, ship_info)
                    if ship_info.get('cross_down_whistle', False):
                        self._update_passage_record_notice_time(mmsi, time.time())
                        self.log_current_message(f"⏰ 上水船舶 {ship_info.get('name', mmsi)} 预告时间已记录")

                    if current_signal == '下水':
                        self._add_passage_remark(mmsi, "下界限标等候")
                        self.log_current_message(f"⚠️ 现在是下水信号，请船舶{ship_info.get('name', mmsi)}等待")

                self._add_or_update_pending(mmsi, ship_info)
                return

            # ----- 5. 上水进漕（跨越下界限标）-----
            if direction == 'up' and ship_info.get('cross_down_bound', False):
                if mmsi in self.commanded_queue:
                    if mmsi not in self.control_area_queue:
                        # 记录进漕时间
                        enter_time = time.time()
                        ship_info['enter_channel_time'] = enter_time
                        self.control_area_queue[mmsi] = ship_info.copy()
                        self.control_area_queue_changed.emit(self.control_area_queue)
                        self.log_current_message(f"🚢 船舶 {ship_info.get('name', mmsi)} 进入控制河段（上水进漕）")

                        self._update_passage_record_enter_time(mmsi, enter_time)
                        self.log_current_message(
                            f"🚪 船舶 {ship_info.get('name', mmsi)} 进漕时间: {datetime.fromtimestamp(enter_time).strftime('%Y-%m-%d %H:%M:%S')}")
                        return
                else:
                    if self._is_in_tolerance_zone(mmsi, ship_info, 'down_bound', 'upstream'):
                        self.log_current_message(f"⚠️ 船舶 {ship_info.get('name', mmsi)} 已进漕但在容忍区之内，暂不记录违规进漕")
                    else:
                        self.log_current_message(f"⚠️ 船舶 {ship_info.get('name', mmsi)} 违规进漕（不在已指挥队列且不在容忍区）")

            # ----- 6. 上水出漕（跨越上界限标）-----
            if direction == 'up' and ship_info.get('cross_up_bound', False):
                exit_time = time.time()
                self._update_passage_record_exit_time(mmsi, exit_time)
                print(
                    f"🚪 船舶 {ship_info.get('name', mmsi)} 出漕时间: {datetime.fromtimestamp(exit_time).strftime('%Y-%m-%d %H:%M:%S')}")

                if self._passage_record_has_enter_and_exit(mmsi):
                    self._upload_passage_record_to_server(mmsi)

                self._remove_from_commanded_and_control(mmsi)
                return

            # ----- 7. 下水进漕（跨越上界限标）-----
            if direction == 'down' and ship_info.get('cross_up_bound', False):
                if mmsi in self.commanded_queue:
                    if mmsi not in self.control_area_queue:
                        enter_time = time.time()
                        ship_info['enter_channel_time'] = enter_time
                        self.control_area_queue[mmsi] = ship_info.copy()
                        self.log_current_message(f"🚢 船舶 {ship_info.get('name', mmsi)} 进入控制河段（下水进漕）")

                        self._update_passage_record_enter_time(mmsi, enter_time)
                        self.log_current_message(
                            f"🚪 船舶 {ship_info.get('name', mmsi)} 进漕时间: {datetime.fromtimestamp(enter_time).strftime('%Y-%m-%d %H:%M:%S')}")
                        return
                else:
                    if self._is_in_tolerance_zone(mmsi, ship_info, 'up_bound', 'downstream'):
                        self.log_current_message(f"⚠️ 船舶 {ship_info.get('name', mmsi)} 已进漕但在容忍区之内，暂不记录违规进漕")
                    else:
                        self.log_current_message(f"⚠️ 船舶 {ship_info.get('name', mmsi)} 违规进漕（不在已指挥队列且不在容忍区）")

            # ----- 8. 下水出漕（跨越下界限标）-----
            if direction == 'down' and ship_info.get('cross_down_bound', False):
                exit_time = time.time()
                self._update_passage_record_exit_time(mmsi, exit_time)
                print(
                    f"🚪 船舶 {ship_info.get('name', mmsi)} 出漕时间: {datetime.fromtimestamp(exit_time).strftime('%Y-%m-%d %H:%M:%S')}")

                if self._passage_record_has_enter_and_exit(mmsi):
                    self._upload_passage_record_to_server(mmsi)

                self._remove_from_commanded_and_control(mmsi)
                return

            # ----- 更新待指挥队列或已指挥队列的信息（非上述特定事件）-----
            if in_calc_range and not in_control_area:
                if mmsi not in self.pending_queue:
                    if mmsi not in self.commanded_queue:
                        self.pending_queue[mmsi] = ship_info.copy()
                    else:
                        #若在已指挥队列，需要把已指挥队列已有的信息复制过去
                        old_ship_info = self.commanded_queue[mmsi]
                        old_ship_info['last_update'] = time.time()
                        old_ship_info['calc_range'] = calc_range_type
                        old_ship_info['in_control_area'] = in_control_area
                        old_ship_info['in_calc_range'] = in_calc_range
                        self.commanded_queue[mmsi] = old_ship_info.copy()
                else:
                    self.pending_queue[mmsi].update(ship_info)

            elif  in_control_area :
                # 若在已指挥队列，需要把已指挥队列已有的信息复制过去
                old_ship_info = self.control_area_queue[mmsi]
                old_ship_info['last_update'] = time.time()
                old_ship_info['calc_range'] = calc_range_type
                old_ship_info['in_control_area'] = in_control_area
                old_ship_info['in_calc_range'] = in_calc_range
                self.control_area_queue[mmsi] = old_ship_info.copy()

            # ----- 2. 方向与计算范围匹配检查 -----
            if (direction == 'up' and not in_up_calc and not in_control_area) or (
                    direction == 'down' and not in_down_calc and not in_control_area):
                # 存在从控制河段出漕的时候
                if mmsi in self.pending_queue:
                    del self.pending_queue[mmsi]
                    self.log_current_message(
                        f"⚠️ 船舶 {ship_info.get('name', mmsi)} ({mmsi}) 方向误判，从待指挥队列移除")
                # 方向不匹配就返回，不进行计算了
                return

        except Exception as e:
            print(f"更新船舶队列状态失败: {e}")
            import traceback
            traceback.print_exc()







    def _add_or_update_pending(self, mmsi: str, ship_info: dict):
        """加入或更新待指挥队列"""
        if mmsi not in self.pending_queue:
            self.pending_queue[mmsi] = ship_info.copy()
        else:
            self.pending_queue[mmsi].update(ship_info)


    def _add_passage_remark(self, mmsi: str, remark: str):
        """添加通行记录备注"""
        if hasattr(self, 'passage_record_manager') and self.passage_record_manager:
            active = self.passage_record_manager.get_active_records()
            for rec in active:
                if rec.get('mmsi') == mmsi:
                    old = rec.get('remark', '')
                    new = f"{old}；{remark}" if old else remark
                    self.passage_record_manager.update_record(mmsi, remark=new)
                    break

    def _is_in_tolerance_zone(self, mmsi: str, ship_info: dict, bound_type: str, side: str) -> bool:
        """判断船舶是否在容忍区（界限标上游/下游10米内）"""
        reach = self.current_reach if hasattr(self, 'current_reach') else None
        if not reach:
            return False
        if bound_type == 'up_bound':
            line = reach.up_bound_line
        else:
            line = reach.down_bound_line
        if not line:
            return False
        from channel_mileage import point_to_line_distance
        ship_point = (ship_info['lat'], ship_info['lon'])
        dist = point_to_line_distance(ship_point, line.start_point, line.end_point)
        # 距离小于20米即认为在容忍区（简化）
        if dist <= 20:
            return True
        return False

    def _remove_from_all_queues(self, mmsi: str,name):
        """从所有队列中移除"""
        if mmsi in self.pending_queue:
            del self.pending_queue[mmsi]
            self.log_current_message(f"🚢 船舶 {name} 进入停泊区，从待指挥队列移除")
        if mmsi in self.commanded_queue:
            del self.commanded_queue[mmsi]
            self.log_current_message(f"🚢 船舶 {name} 进入停泊区，从已指挥队列移除")
            self.commanded_queue_changed.emit(self.commanded_queue)
        if mmsi in self.control_area_queue:
            del self.control_area_queue[mmsi]
            self.log_current_message(f"🚢 船舶 {name} 进入停泊区，从控制河段队列移除")
            self.control_area_queue_changed.emit(self.control_area_queue)

    def _remove_from_commanded_and_control(self, mmsi: str):
        """从已指挥队列和控制河段队列移除"""
        if mmsi in self.commanded_queue:
            del self.commanded_queue[mmsi]
            self.commanded_queue_changed.emit(self.commanded_queue)
        if mmsi in self.control_area_queue:
            del self.control_area_queue[mmsi]
            self.control_area_queue_changed.emit(self.control_area_queue)

    def _passage_record_has_enter_and_exit(self, mmsi: str) -> bool:
        """检查通行记录是否同时有进漕和出漕时间"""
        if hasattr(self, 'passage_record_manager') and self.passage_record_manager:
            records = self.passage_record_manager.get_records_by_mmsi(mmsi)
            for rec in records:
                if rec.get('enter_channel_time', 0) > 0 and rec.get('exit_channel_time', 0) > 0:
                    return True
        return False

    def _upload_passage_record_to_server(self, mmsi: str):
        """上传通行记录到服务器"""
        if hasattr(self, 'passage_record_manager') and self.passage_record_manager:
            records = self.passage_record_manager.get_records_by_mmsi(mmsi)
            if records:
                record = records[0]  # 最新的一条
                #获取到的数据库的字段与上传到web段的字段名字不一样，需要变换
                dict={}
                dict["id"]=record['oracleID']
                dict["weather"]=record['weather']
                dict["reachId"]=record['reachId']
                dict['shipMmsi'] = mmsi
                dict["shipName"]=record['name']
                dict["tugboatNumber"]=record['tug_count']
                dict["shipUpOrDown"]= 0 if record['direction']=="up" else 1
                ts=record.get("creat_time",0)
                dict["operatTime"] = datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else ""
                ts=record.get("forecast_time",0)
                dict["noticeTime"]=datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else ""
                ts=record.get("supplement_time",0)
                dict["supplementTime"]=datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else ""
                ts=record.get("start_hang_time",0)
                dict["suspendTime"]=datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else ""
                ts=record.get("half_pole_time",0)
                dict["halfTime"]=datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else ""
                ts=record.get("enter_channel_time",0)
                dict["slotTime"]=datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else ""
                ts=record.get("exit_channel_time",0)
                dict["outTime"]=datetime.fromtimestamp(ts).strftime('%Y-%m-%d %H:%M:%S') if ts else ""
                dict["goods"]=record['cargo']
                dict["tonnage"]=record['actual_load']
                dict['maxTonnage']=record['rated_load']
                dict["maxDraught"]=record['draught']
                dict["waterLevel"]=record['water_level']
                dict["attendant"]=record['duty_person']
                dict["remarks"]=record['remarks']
                dict["reachWork"]=0 if record['reach_work']== "收班" else 1
                dict["reachCode"]=record['reach_code']

                print(f"构造的上传web的字典{dict}")

                # 调用你的 API 上传方法
                self.get_api_service.upload_record(dict)

                self.log_current_message(f"📤 上传船舶 {mmsi} 通行记录到服务器: {record}   {dict}")
                # 示例: self.api.upload_passage(record)


    def update_ship_in_pending(self, mmsi: str, updates: dict) -> bool:
        """
        更新待指挥队列中的船舶信息

        Args:
            mmsi: 船舶MMSI
            updates: 要更新的字段字典

        Returns:
            bool: 是否成功
        """
        if mmsi in self.pending_queue:
            self.pending_queue[mmsi].update(updates)
            self.pending_queue_changed.emit(self.pending_queue)
            print(f"✅ 已更新待指挥船舶 {mmsi}: {updates}")
            return True
        else:
            print(f"❌ 船舶 {mmsi} 不在待指挥队列中")
            return False

    def update_ship_in_commanded(self, mmsi: str, updates: dict) -> bool:
        """
        更新已指挥队列中的船舶信息

        Args:
            mmsi: 船舶MMSI
            updates: 要更新的字段字典
        """
        if mmsi in self.commanded_queue:
            self.commanded_queue[mmsi].update(updates)
            self.commanded_queue_changed.emit(self.commanded_queue)
            return True
        return False

    def add_to_commanded(self, mmsi: str, ship_info: dict) -> bool:
        """
        添加船舶到已指挥队列

        Args:
            mmsi: 船舶MMSI
            ship_info: 船舶信息
        """
        if mmsi not in self.commanded_queue:
            self.commanded_queue[mmsi] = ship_info
            self.commanded_queue_changed.emit(self.commanded_queue)
            print(f"📋 船舶 {ship_info.get('name', mmsi)} 已加入已指挥队列")
            return True
        return False

    def update_ship_in_control_area(self, mmsi: str, updates: dict) -> bool:
        """
        更新控制河段队列中的船舶信息

        Args:
            mmsi: 船舶MMSI
            updates: 要更新的字段字典
        """
        if mmsi in self.control_area_queue:
            self.control_area_queue[mmsi].update(updates)
            self.control_area_queue_changed.emit(self.control_area_queue)
            return True
        return False

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
        self.pending_queue_changed.emit(self.pending_queue)
        self.commanded_queue_changed.emit(self.commanded_queue)
        return True



    def remove_from_pending(self, mmsi: str):
        """从待指挥队列移除"""
        if mmsi in self.pending_queue:
            ship_info = self.pending_queue.pop(mmsi)
            print(f"移除船舶 {ship_info.get('name', mmsi)} 从待指挥队列")
            self.pending_queue_changed.emit(self.pending_queue)
            return True
        return False

    def remove_from_commanded(self, mmsi: str):
        """从已指挥队列移除"""
        if mmsi in self.commanded_queue:
            ship_info = self.commanded_queue.pop(mmsi)
            print(f"移除船舶 {ship_info.get('name', mmsi)} 从已指挥队列")
            self.commanded_queue_changed.emit(self.commanded_queue)
            return True
        return False

    def remove_from_control_area(self, mmsi: str):
        """从控制河段队列移除"""
        if mmsi in self.control_area_queue:
            ship_info = self.control_area_queue.pop(mmsi)
            print(f"移除船舶 {ship_info.get('name', mmsi)} 从控制河段队列")
            self.control_area_queue_changed.emit(self.control_area_queue)
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

        if expired_pending:
            self.log_current_message(f"控制河段队列清理了过期船舶")
            self.pending_queue_changed.emit(self.pending_queue)

        # 清理已指挥队列
        expired_commanded = []
        for mmsi, ship in self.commanded_queue.items():
            last = ship.get('last_update', ship.get('command_time', 0))
            if current_time - last > timeout:
                expired_commanded.append(mmsi)

        for mmsi in expired_commanded:
            del self.commanded_queue[mmsi]
        if expired_commanded:
            self.log_current_message(f"已指挥船舶队列清理了过期船舶")
            self.commanded_queue_changed.emit(self.commanded_queue)

        # 清理控制河段队列
        expired_control = []
        for mmsi, ship in self.control_area_queue.items():
            last = ship.get('last_update', ship.get('enter_control_time', 0))
            if current_time - last > timeout:
                expired_control.append(mmsi)

        for mmsi in expired_control:
            del self.control_area_queue[mmsi]
            removed_count += 1

        if expired_control:
            self.log_current_message(f"控制河段船舶队列清理了过期船舶")
            self.control_area_queue_changed.emit(self.control_area_queue)

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
        self.pending_queue_changed.emit(self.pending_queue)
        self.commanded_queue_changed.emit(self.commanded_queue)
        self.control_area_queue_changed.emit(self.control_area_queue)

        print(f"🔄 切换控制河段：已清空队列 (待指挥:{pending_count}, 已指挥:{commanded_count}, 控制区内:{control_count})")

        return pending_count + commanded_count + control_count