# ship_manager.py
import json
import math
import time
from typing import Dict, List, Tuple, Optional, Union
from dataclasses import dataclass
from enum import Enum
from PyQt5.QtCore import QObject, pyqtSignal
from sqlalchemy import false

from mileage_region_manager import MileageRegionManager
from queue_manager import QueueManager
from sqlite3Manager import SQLiteTableManager


class ShipDirection(Enum):
    """船舶方向枚举"""
    UPSTREAM = "up"  # 上行
    DOWNSTREAM = "down"  # 下行
    DOCKER = "docked"
    UNKNOWN = "未知"  # 未知


@dataclass
class ShipInfo:
    """船舶信息数据类"""
    MMSI: str  # MMSI 编号
    name: str  # 船名
    longitude: float  # 经度
    latitude: float  # 纬度
    heading: float  # 航向 (0-360度)
    speed: float  # 速度 (节)
    direction: ShipDirection = ShipDirection.UNKNOWN  # 上下行状态和停靠状态
    timestamp: float = 0  # 时间戳
    last_update_time: str=''  # 最后更新时间
    position_and_direction:dict = None  #位置和方向信息
    calc_range:str = None #船舶是否在上下水计算范围，"up"，‘down’
    up_or_down: list = None  #四个bool值列表，true为下水，false为上水
    status: str = None #船舶的状态，上水、下水、停靠、特殊
    shipType: str =None  #船舶的人工设定状态,None:未设定，'up','down','docked','special'
    staticInfo: dict = None #船舶静态信息



    def to_dict(self):
        """转换为字典"""
        return {
            'MMSI': self.MMSI,
            'name': self.name,
            'longitude': self.longitude,
            'latitude': self.latitude,
            'heading': self.heading,
            'speed': self.speed,
            'timestamp': self.timestamp,
            'status': self.status,
            'shipType': self.shipType if self.shipType is not None else "",
            'last_update_time': self.last_update_time,
            'staticInfo': self.staticInfo if self.staticInfo is not None else "",
        }



class ShipManager(QObject):
    """船舶管理器 - 管理所有船舶状态"""

    # 信号
    ship_added = pyqtSignal(object)  # 新船舶添加
    ship_updated = pyqtSignal(object)  # 船舶信息更新
    ship_removed = pyqtSignal(str)  # 船舶移除 (MMSI)
    update_queue_status = pyqtSignal(str, object,object)  # 更新船舶队列状态信息 (MMSI, 新方向)

    def __init__(self,api_service,mileage_manager=None,reach=None,queue_manager=None):
        super().__init__()
        self.queue_manager = queue_manager
        self.ships: Dict[str, ShipInfo] = {}  # MMSI -> ShipInfo


        self.get_channel_position_callback = None

        # 用于记录船舶是否在计算范围内
        self.ships_in_calc_range = {}  # mmsi -> 计算范围类型 ('up'/'down')

        self.api_service=api_service
        self.mileage_manager = mileage_manager  # 直接持有引用
        self.current_reach=reach #引用控制河段的信息

        # 创建管理器实例
        self.db_manager = SQLiteTableManager("test.db")
        # 连接到数据库
        self.db_manager.connect()


        # 超时时间（秒），超过此时间未更新则视为离线
        self.timeout_seconds = 60 *1 # 5分钟

        # 历史轨迹存储（可选）
        self.track_history: Dict[str, List[Tuple[float, float, float]]] = {}
        self.max_track_points = 100  # 每艘船最多保存的轨迹点数

    def set_mileage_manager(self, mileage_manager,reach,queue_manager):
        """设置航道里程管理器"""
        self.mileage_manager = mileage_manager
        self.current_reach = reach
        self.queue_manager = queue_manager


    def parse_ais_message(self, message: str,min_update_interval: float = 5.0) :
        """
        解析AIS消息字符串

        Args:
            message: AIS消息字符串，格式如 "0MMSI,1时间戳,2经度,3纬度,4航向,6速度"

        Returns:
            ShipInfo对象，如果解析失败返回None
            :param message:
            :param min_update_interval:
        """
        try:
            # 按逗号分割
            parts = message.strip().split(',')

            # 根据实际格式调整索引
            # 0MMSI,1时间戳,2经度,3纬度,4航向,6速度


            mmsi = parts[0].strip()
            longitude = float(parts[2].strip())
            latitude = float(parts[3].strip())
            course = float(parts[4].strip())/10
            speed = float(parts[6].strip()) / 10 if float(parts[6].strip()) / 10 <20 else 0
            timestamp = time.time()

            current_time = time.time()
            # 检查是否已有该船舶
            if mmsi in self.ships:
                old_ship = self.ships[mmsi]

                # 检查上次更新时间是否在最小间隔内
                time_diff = current_time - old_ship.timestamp
                if time_diff < min_update_interval:
                    # 可选：记录调试信息
                    # print(f"船舶 {mmsi} 更新过于频繁，上次更新在 {time_diff:.2f} 秒前，跳过更新")
                    return None

                ship_name=self.ships[mmsi].name
                #mmsi做船名，说明上一次读取船名不正确
                if ship_name==mmsi:
                    ship_name = self.api_service.get_ship_name(mmsi)
                    if ship_name :
                        self.db_manager.insert_record("ShipName", {"ShipName": ship_name, "MMSI": mmsi})
                    else:
                        ship_name = mmsi

                # 创建船舶信息对象
                ship = ShipInfo(
                    MMSI=mmsi,
                    name=ship_name,
                    longitude=longitude,
                    latitude=latitude,
                    heading=course,
                    speed=speed,
                    timestamp=timestamp
                )

                # staticInfo = self.api_service.get_static_info(mmsi)
                # ship.static_info = staticInfo

                #计算船舶的位置和方向,方向是docked就表示是停泊了，是up或down表示这次判断
                position_and_direction=self.calculate_ship_position_and_direction(
                     latitude, longitude, course,speed
                )

                #判断船舶是上下水，四次判断为up，才真正算上水，四次判断为down，才真正算下水，否则保持先前的状态
                if position_and_direction["direction"] == "up":
                    del old_ship.up_or_down[0]
                    old_ship.up_or_down.append(False)
                if position_and_direction["direction"] == "down":
                    del old_ship.up_or_down[0]
                    old_ship.up_or_down.append(True)
                if position_and_direction["direction"] == "docked":
                    ship.status='docked'

                #船舶不是特殊船舶就再调用一次
                if old_ship.status!= 'special':
                    is_special_ship = self.api_service.is_special_ship(mmsi)
                    #如果是特殊船舶，但是之前没判断成特殊船舶
                    if is_special_ship:
                        old_ship.status = 'special'

                # 船舶设定状态了
                if old_ship.shipType:
                    ship.status = old_ship.shipType
                    ship.shipType = old_ship.shipType

                #船舶是特殊船舶
                elif old_ship.status=='special':
                    ship.status = 'special'

                #新船舶是停靠船舶
                elif  ship.status=='docked':
                    ship.status = 'docked'

                # 上下水状态列表全为真,并且船舶类型未被设定
                elif all(old_ship.up_or_down):
                    ship.status = "down"
                elif not all(old_ship.up_or_down):
                    ship.status = "up"
                else:
                    ship.status = old_ship.status

                #船舶的上下水列表更新
                ship.up_or_down=old_ship.up_or_down
                ship.position_and_direction=position_and_direction



                # 判断是否在计算范围内
                in_up_calc = position_and_direction.get('in_up_calc_range', False)
                in_down_calc = position_and_direction.get('in_down_calc_range', False)
                calc_range = None

                #在上水计算范围内
                if in_up_calc and ship.status=='up':
                    calc_range = 'up'

                elif in_down_calc and ship.status=='down':
                    calc_range = 'down'

                # 速度转换：节 -> 公里/分钟
                # 1节 = 1.852公里/小时 = 1.852/60 ≈ 0.0308667公里/分钟
                speed_km_per_min = speed * 1.852 / 60
                km_diff=abs(position_and_direction.get('estimated_km') - self.mileage_manager.up_bound_km)
                # 计算时间（分钟）
                if speed_km_per_min:
                    time_minutes = km_diff / speed_km_per_min
                    position_and_direction['time_minutes']=round(time_minutes, 1) #保留一位小数

                #船舶在哪个计算范围区域
                ship.calc_range = calc_range

                # 转换为本地时间的结构化对象
                local_time = time.localtime(current_time)
                ship.last_update_time = time.strftime("%Y-%m-%d %H:%M:%S", local_time)

                # 更新信息
                self.ships[mmsi] = ship

                # 更新队列状态
                self.update_queue_status.emit(mmsi, ship, position_and_direction)

                # 添加到轨迹历史
                self._add_to_track_history(mmsi, ship.longitude,
                                           ship.latitude, current_time)

                # 发射更新信号
                self.ship_updated.emit(ship.to_dict())
                return None

            else:
                ship_name=self.api_service.get_ship_name(mmsi)
                #读取到船名，本地数据库保存
                if ship_name:
                    if self.db_manager.search_records("ShipName",{"MMSI":mmsi}):
                        self.db_manager.update_single_field("ShipName","ShipName",ship_name,{"MMSI":mmsi})
                    else:
                        self.db_manager.insert_record("ShipName",{"ShipName":ship_name,"MMSI":mmsi})
                else:
                    shipList=self.db_manager.search_records("ShipName",{"MMSI":mmsi})
                    if shipList:
                        ship_name=shipList[0]["ShipName"]
                    else:
                        ship_name=mmsi

                # 添加新船舶，不需要检查时间
                # 创建船舶信息对象
                ship = ShipInfo(
                    MMSI=mmsi,
                    name=ship_name,
                    longitude=longitude,
                    latitude=latitude,
                    heading=course,
                    speed=speed,
                    timestamp=timestamp
                )

                # 计算船舶的位置和方向
                position_and_direction = self.calculate_ship_position_and_direction(
                    latitude, longitude, course,speed
                )

                #第一次判断上下水时,定义好上下水列表
                if position_and_direction["direction"] == "down":
                    ship.up_or_down = [True,True,True,True]
                elif position_and_direction["direction"] == "up":
                    ship.up_or_down = [False,False,False,False]
                elif position_and_direction["direction"] == "docked":
                    ship.status='docked'
                    ship.up_or_down = [True,False,True,False]
                else:
                    ship.up_or_down = [False,True,False,True]#不是的就一半真一半假

                is_special_ship = self.api_service.is_special_ship(mmsi)
                #如果是特殊船舶，判断状态未特殊船舶
                if is_special_ship:
                    ship.status = "special"
                #不是特殊船舶但是是停靠船舶
                elif ship.status=='docked':
                    ship.status = "docked"
                # 上下水状态列表全为真,方向确定为下水
                elif all(ship.up_or_down) :
                    ship.status = "down"
                elif not all(ship.up_or_down):
                    ship.status = "up"
                #第一次状态没判断出来是上下水
                else:
                    ship.status = "unknown"


                ship.position_and_direction = position_and_direction

                # 转换为本地时间的结构化对象
                local_time = time.localtime(current_time)
                ship.last_update_time = time.strftime("%Y-%m-%d %H:%M:%S", local_time)

                self.ships[mmsi] = ship

                self._init_track_history(mmsi)
                self._add_to_track_history(mmsi, ship.longitude,
                                           ship.latitude, current_time)


                # 发射添加信号，用来绘制船舶
                self.ship_updated.emit(ship.to_dict())
                return None



        except (ValueError, IndexError) as e:
            print(f"解析AIS消息失败: {e}, 消息: {message}")
            return None

    def calculate_time_to_up_bound(self, ship_estimated_km: float, ship_speed: float, up_bound_km: float) -> Optional[
        float]:
        """
        计算船舶到达上界限标所需的时间

        Args:
            ship_estimated_km: 船舶当前的预估里程数（公里）
            ship_speed: 船舶速度（节）
            up_bound_km: 上界限标所在的里程数（公里）

        Returns:
            到达所需时间（分钟），如果速度无效或船舶已过界限标返回None
        """
        # 速度必须大于0
        if ship_speed <= 0:
            return None

        # 计算里程差（公里）
        km_diff = up_bound_km - ship_estimated_km

        # 如果里程差为负，说明船舶已经过了上界限标
        if km_diff <= 0:
            return 0  # 已到达或已通过

        # 速度转换：节 -> 公里/分钟
        # 1节 = 1.852公里/小时 = 1.852/60 ≈ 0.0308667公里/分钟
        speed_km_per_min = ship_speed * 1.852 / 60

        # 计算时间（分钟）
        time_minutes = km_diff / speed_km_per_min

        # 保留一位小数
        return round(time_minutes, 1)

    def calculate_time_to_down_bound(self, ship_estimated_km: float, ship_speed: float, down_bound_km: float) -> \
    Optional[float]:
        """
        计算船舶到达下界限标所需的时间

        Args:
            ship_estimated_km: 船舶当前的预估里程数（公里）
            ship_speed: 船舶速度（节）
            down_bound_km: 下界限标所在的里程数（公里）

        Returns:
            到达所需时间（分钟），如果速度无效或船舶已过界限标返回None
        """
        # 速度必须大于0
        if ship_speed <= 0:
            return None

        # 计算里程差（公里）
        km_diff = ship_estimated_km - down_bound_km

        # 如果里程差为负，说明船舶已经过了下界限标
        if km_diff <= 0:
            return 0  # 已到达或已通过

        # 速度转换：节 -> 公里/分钟
        speed_km_per_min = ship_speed * 1.852 / 60

        # 计算时间（分钟）
        time_minutes = km_diff / speed_km_per_min

        # 保留一位小数
        return round(time_minutes, 1)

    def calculate_ship_position_and_direction(self, ship_lat: float, ship_lon: float,
                                              ship_heading: float,speed:float, ship_mmsi: str = None,) -> dict:
        """
        计算船舶在控制河段区域内的位置和方向

        Args:
            ship_lat: 船舶纬度
            ship_lon: 船舶经度
            ship_heading: 船舶航向
            speed:船舶速度（节）
            ship_mmsi: 船舶MMSI（可选）

        Returns:
            包含位置和方向信息的字典

        """
        # 计算航道位置和方向
        pos_info = self.mileage_manager.find_ship_position(
            ship_lat, ship_lon, ship_heading
        )

        # . 先判断是否在停泊区内
        if hasattr(self, 'current_reach') and self.current_reach:
            isInPark = False
            for park in self.current_reach.park_areas:
                if park.contains_point(ship_lat, ship_lon):
                    isInPark = True
                    break

            # 在停靠区且速度小于1节的
            if isInPark and speed < 1:
                pos_info['in_park'] = True
                pos_info['direction'] = 'docked'  # 停泊状态
                return pos_info
            # 不在停靠去但是速度小于0.5节
            elif not isInPark and speed < 0.5:
                pos_info['in_park'] = True
                pos_info['direction'] = 'docked'  # 停泊状态
                return pos_info
            # 2. 判断是否在特殊区内
            for special in self.current_reach.special_areas:
                if special.contains_point(ship_lat, ship_lon):
                    pos_info['in_special'] = True
                    pos_info['special_name'] = special.fence_name
                    return pos_info


        # 1. 判断是否在上下水计算范围内
        pos_info['in_up_calc_range'] = self.current_reach.is_point_in_up_calc_area(ship_lat, ship_lon)
        pos_info['in_down_calc_range'] = self.current_reach.is_point_in_down_calc_area(ship_lat, ship_lon)

        pos_info['in_control_area'] = self.current_reach.is_point_in_control_area(ship_lat, ship_lon)



        # 2. 判断是否在揭示区域内
        pos_info['in_up_reveal_area'] = self.current_reach.is_point_in_up_reveal_area(ship_lat, ship_lon)
        pos_info['in_down_reveal_area'] = self.current_reach.is_point_in_down_reveal_area(ship_lat, ship_lon)


        return pos_info

    def update_ship(self, ship_info: ShipInfo, min_update_interval: float = 5.0):
        """
        更新船舶信息

        Args:
            ship_info: 新的船舶信息
            min_update_interval: 最小更新间隔（秒），默认5秒

        Returns:
            bool: 是否执行了更新
        """
        import time

        current_time = time.time()
        mmsi = ship_info.MMSI

        # 检查是否已有该船舶
        if mmsi in self.ships:
            old_ship = self.ships[mmsi]

            # 检查上次更新时间是否在最小间隔内
            time_diff = current_time - old_ship.last_update
            if time_diff < min_update_interval:
                # 可选：记录调试信息
                # print(f"船舶 {mmsi} 更新过于频繁，上次更新在 {time_diff:.2f} 秒前，跳过更新")
                return False

            # 可选：记录重要更新（比如位置变化较大时）
            position_changed = self._significant_position_change(
                old_ship, ship_info, threshold_meters=10
            )

            if position_changed:
                print(f"船舶 {mmsi} 位置显著变化，距上次更新 {time_diff:.2f} 秒")

            # 更新时间戳
            ship_info.last_update = current_time


            # 更新信息
            self.ships[mmsi] = ship_info

            # 添加到轨迹历史
            self._add_to_track_history(mmsi, ship_info.longitude,
                                       ship_info.latitude, current_time)

            # 发射更新信号
            self.ship_updated.emit(ship_info.to_dict())
            return True
        else:
            # 添加新船舶，不需要检查时间
            print(f"添加新船舶: {mmsi} - {ship_info.name}")
            ship_info.last_update = current_time
            self.ships[mmsi] = ship_info
            self._init_track_history(mmsi)
            self._add_to_track_history(mmsi, ship_info.longitude,
                                       ship_info.latitude, current_time)

            # 发射添加信号
            self.ship_updated.emit(ship_info.to_dict())
            return True

    def _significant_position_change(self, old_ship: ShipInfo, new_ship: ShipInfo,
                                     threshold_meters: float = 10) -> bool:
        """
        判断船舶位置是否有显著变化

        Args:
            old_ship: 旧船舶信息
            new_ship: 新船舶信息
            threshold_meters: 变化阈值（米）

        Returns:
            是否有显著变化
        """
        # 计算两点之间的距离（简化版）
        import math

        lat1, lon1 = old_ship.latitude, old_ship.longitude
        lat2, lon2 = new_ship.latitude, new_ship.longitude

        # 粗略计算距离（纬度1度≈111公里，经度1度随纬度变化）
        avg_lat = (lat1 + lat2) / 2
        lat_diff = (lat2 - lat1) * 111320  # 米
        lon_diff = (lon2 - lon1) * 111320 * math.cos(math.radians(avg_lat))  # 米

        distance = math.sqrt(lat_diff ** 2 + lon_diff ** 2)

        return distance > threshold_meters


    def _init_track_history(self, mmsi: str):
        """初始化船舶轨迹历史"""
        if mmsi not in self.track_history:
            self.track_history[mmsi] = []

    def _add_to_track_history(self, mmsi: str, lon: float, lat: float, timestamp: float):
        """添加轨迹点"""
        if mmsi in self.track_history:
            history = self.track_history[mmsi]
            history.append((lon, lat, timestamp))

            # 限制历史点数量
            if len(history) > self.max_track_points:
                self.track_history[mmsi] = history[-self.max_track_points:]

    def remove_offline_ships(self):
        """移除超时未更新的船舶"""
        import time
        current_time = time.time()

        offline_mmsi = []
        for mmsi, ship in self.ships.items():
            if current_time - ship.timestamp > self.timeout_seconds:
                offline_mmsi.append(mmsi)

        for mmsi in offline_mmsi:
            del self.ships[mmsi]
            if mmsi in self.track_history:
                del self.track_history[mmsi]
            self.ship_removed.emit(mmsi)

    def get_ship(self, mmsi: str) -> Optional[ShipInfo]:
        """获取船舶信息"""
        return self.ships.get(mmsi)

    def get_all_ships(self) -> List[ShipInfo]:
        """获取所有船舶"""
        return list(self.ships.values())

    def get_ships_by_direction(self, direction: ShipDirection) -> List[ShipInfo]:
        """按方向获取船舶"""
        return [ship for ship in self.ships.values()
                if ship.direction == direction]

    def clear_all_ships(self):
        """清除所有船舶"""
        mmsi_list = list(self.ships.keys())
        self.ships.clear()
        self.track_history.clear()
        for mmsi in mmsi_list:
            self.ship_removed.emit(mmsi)