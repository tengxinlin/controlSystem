# reach_data.py
import math
from dataclasses import dataclass
from typing import List, Tuple, Optional
import json


@dataclass
class ReachPoint:
    """河段点坐标"""
    lat: float  # 纬度
    lon: float  # 经度

    def to_list(self) -> List[float]:
        return [self.lat, self.lon]

    def to_tuple(self) -> Tuple[float, float]:
        return (self.lat, self.lon)


@dataclass
class ReachLine:
    """河段线段（由两个端点定义）"""
    start: ReachPoint
    end: ReachPoint

    def to_coords_list(self) -> List[List[float]]:
        """转换为Leaflet坐标格式 [[lat, lon], [lat, lon]]"""
        return [self.start.to_list(), self.end.to_list()]

    @classmethod
    def from_coords_str(cls, coords_str: str) -> Optional['ReachLine']:
        """
        从坐标字符串创建线段
        格式: "[[106.645681858063,29.5886843165235],[106.665573120117,29.6004390725959]]"
        """
        try:
            coords = json.loads(coords_str)
            if len(coords) >= 2:
                return cls(
                    start=ReachPoint(lat=coords[0][1], lon=coords[0][0]),
                    end=ReachPoint(lat=coords[1][1], lon=coords[1][0])
                )
        except Exception as e:
            print(f"解析坐标字符串失败: {e}")
        return None



def sort_points_by_angle(center: ReachPoint, points: List[ReachPoint]) -> List[ReachPoint]:
    """
    按相对于中心点的角度排序点（用于多边形排序）

    Args:
        center: 中心点
        points: 待排序的点列表

    Returns:
        按角度排序后的点列表
    """

    def get_angle(p: ReachPoint) -> float:
        return math.atan2(p.lat - center.lat, p.lon - center.lon)

    return sorted(points, key=get_angle)


def order_polygon_points(points: List[ReachPoint]) -> List[ReachPoint]:
    """
    将四个点排序为正确的多边形顺序（按角度排序）

    Args:
        points: 四个点

    Returns:
        排序后的点列表
    """
    if len(points) != 4:
        return points

    # 计算中心点
    center_lat = sum(p.lat for p in points) / 4
    center_lon = sum(p.lon for p in points) / 4
    center = ReachPoint(lat=center_lat, lon=center_lon)

    # 按角度排序
    sorted_points = sort_points_by_angle(center, points)

    return sorted_points




@dataclass
class ReachPolygon:
    """河段多边形区域（由多个点围成）"""
    points: List[ReachPoint]  # 按顺序排列的点，首尾相连形成封闭区域

    def to_coords_list(self) -> List[List[float]]:
        """转换为Leaflet坐标格式 [[lat, lon], [lat, lon], ...]"""
        return [p.to_list() for p in self.points]

    def get_bounds(self) -> Tuple[float, float, float, float]:
        """获取区域的边界 (min_lat, max_lat, min_lon, max_lon)"""
        if not self.points:
            return (0, 0, 0, 0)

        lats = [p.lat for p in self.points]
        lons = [p.lon for p in self.points]

        return (min(lats), max(lats), min(lons), max(lons))

    def contains_point(self, lat: float, lon: float) -> bool:
        """
        判断点是否在多边形内（射线法）

        Args:
            lat: 纬度
            lon: 经度

        Returns:
            True 如果在多边形内，否则 False
        """
        if not self.points:
            return False

        n = len(self.points)
        inside = False

        for i in range(n):
            j = (i + 1) % n

            # 获取当前边的两个端点
            lat_i, lon_i = self.points[i].lat, self.points[i].lon
            lat_j, lon_j = self.points[j].lat, self.points[j].lon

            # 检查射线是否与边相交
            if ((lat_i > lat) != (lat_j > lat)) and \
                    (lon < (lon_j - lon_i) * (lat - lat_i) / (lat_j - lat_i) + lon_i):
                inside = not inside

        return inside

    def get_area(self) -> float:
        """计算多边形面积（近似值，单位：平方米）"""
        if len(self.points) < 3:
            return 0

        # 使用鞋带公式计算面积（经纬度需要转换为平面坐标）
        # 这里简化处理，返回相对值
        area = 0
        n = len(self.points)

        for i in range(n):
            j = (i + 1) % n
            area += (self.points[i].lon * self.points[j].lat -
                     self.points[j].lon * self.points[i].lat)

        return abs(area) / 2 * 111319.9 * 111319.9  # 粗略转换为平方米

    @classmethod
    def from_coords_str(cls, coords_str: str) -> Optional['ReachPolygon']:
        """
        从坐标字符串创建多边形
        格式: "[[106.645681858063,29.5886843165235],[106.665573120117,29.6004390725959], ...]"
        """
        try:
            coords = json.loads(coords_str)
            points = []

            for coord in coords:
                if len(coord) >= 2:
                    # 假设存储的是 [经度, 纬度]
                    points.append(ReachPoint(lat=coord[1], lon=coord[0]))

            if len(points) >= 3:  # 至少需要3个点才能形成多边形
                return cls(points=points)
            else:
                print(f"多边形点数不足: {len(points)}")
                return None

        except Exception as e:
            print(f"解析多边形坐标字符串失败: {e}")
        return None

@dataclass
class ControlArea:
    """控制河段区域（由上下界限标围成的四边形）"""
    up_line: ReachLine  # 上游界限标线段
    down_line: ReachLine  # 下游界限标线段

    def __post_init__(self):
        """初始化后验证并构建多边形"""
        self.polygon = self._create_polygon()
        self._validate_area()

    def _create_polygon(self) -> List[ReachPoint]:
        """
        由上下界限标创建多边形（需要判断方向）
        返回按顺序排列的四个点
        """
        # 获取四个端点
        up_start = self.up_line.start
        up_end = self.up_line.end
        down_start = self.down_line.start
        down_end = self.down_line.end
        pointsList=[up_start, up_end, down_start, down_end]

        points=order_polygon_points(pointsList)

        return points

    def _validate_area(self):
        """验证区域是否有效"""
        if len(self.polygon) != 4:
            raise ValueError("控制河段区域必须由4个点组成")

        # 可以添加更多的验证，比如检查线段是否交叉等

    def to_polygon(self) -> ReachPolygon:
        """转换为多边形对象"""
        return ReachPolygon(points=self.polygon)

    def contains_point(self, lat: float, lon: float) -> bool:
        """
        判断点是否在控制河段区域内

        Args:
            lat: 纬度
            lon: 经度

        Returns:
            True如果在区域内
        """
        # 转换为多边形判断
        polygon = self.to_polygon()
        return polygon.contains_point(lat, lon)

    def get_bounds(self) -> Tuple[float, float, float, float]:
        """获取区域边界"""
        lats = [p.lat for p in self.polygon]
        lons = [p.lon for p in self.polygon]
        return (min(lats), max(lats), min(lons), max(lons))

    def get_center(self) -> ReachPoint:
        """获取区域中心点"""
        center_lat = sum(p.lat for p in self.polygon) / 4
        center_lon = sum(p.lon for p in self.polygon) / 4
        return ReachPoint(lat=center_lat, lon=center_lon)

@dataclass
class FenceArea:
    """围栏区域（停泊区/特殊区）"""
    fence_name: str
    fence_type: str  # 'park' 停泊区, 'special' 特殊区
    points: List[ReachPoint]  # 多边形顶点

    def to_coords_list(self) -> List[List[float]]:
        """转换为Leaflet坐标格式 [[lat, lon], [lat, lon], ...]"""
        return [p.to_list() for p in self.points]

    def get_bounds(self) -> Tuple[float, float, float, float]:
        """获取区域的边界 (min_lat, max_lat, min_lon, max_lon)"""
        if not self.points:
            return (0, 0, 0, 0)

        lats = [p.lat for p in self.points]
        lons = [p.lon for p in self.points]

        return (min(lats), max(lats), min(lons), max(lons))

    def contains_point(self, lat: float, lon: float) -> bool:
        """
        判断点是否在多边形内（射线法）

        Args:
            lat: 纬度
            lon: 经度

        Returns:
            True 如果在多边形内，否则 False
        """
        if not self.points or len(self.points) < 3:
            return False

        n = len(self.points)
        inside = False

        for i in range(n):
            j = (i + 1) % n

            lat_i, lon_i = self.points[i].lat, self.points[i].lon
            lat_j, lon_j = self.points[j].lat, self.points[j].lon

            # 检查射线是否与边相交
            if ((lat_i > lat) != (lat_j > lat)) and \
                    (lon < (lon_j - lon_i) * (lat - lat_i) / (lat_j - lat_i) + lon_i):
                inside = not inside

        return inside

    def get_area(self) -> float:
        """计算多边形面积（平方米）"""
        if len(self.points) < 3:
            return 0

        # 使用鞋带公式
        area = 0
        n = len(self.points)

        for i in range(n):
            j = (i + 1) % n
            area += (self.points[i].lon * self.points[j].lat -
                     self.points[j].lon * self.points[i].lat)

        # 粗略转换为平方米（纬度1度≈111公里，经度1度随纬度变化）
        avg_lat = sum(p.lat for p in self.points) / n
        meter_per_deg_lat = 111320
        meter_per_deg_lon = 111320 * math.cos(math.radians(avg_lat))

        return abs(area) / 2 * meter_per_deg_lat * meter_per_deg_lon

    @classmethod
    def from_db_row(cls, row: dict) -> Optional['FenceArea']:
        """
        从数据库行创建围栏区域

        Args:
            row: 数据库查询结果行，应包含 fence_id, fence_name, fence_type, coordinates, description
        """
        try:
            import json
            coords_str = row.get('PointList', '')
            if not coords_str:
                return None

            coords = json.loads(coords_str)
            points = []

            for coord in coords:
                if len(coord) >= 2:
                    # 假设存储的是 [经度, 纬度]
                    points.append(ReachPoint(lat=coord[1], lon=coord[0]))

            if len(points) < 3:
                print(f"围栏 {row.get('FenceName')} 点数不足: {len(points)}")
                return None

            return cls(
                fence_name=row.get('FenceName', ''),
                fence_type=row.get('FenceType', 'park'),
                points=points,

            )

        except Exception as e:
            print(f"解析围栏坐标失败: {e}")
            return None


@dataclass
class RevealArea:
    """揭示区域（由鸣笛标和界限标围成的四边形）"""
    name: str  # 区域名称 'up_reveal' 或 'down_reveal'
    whistle_line: ReachLine  # 鸣笛标线段
    bound_line: ReachLine  # 界限标线段
    description: str = ""  # 描述信息

    def __post_init__(self):
        """初始化后构建多边形"""
        self.polygon = self._create_polygon()

    def _create_polygon(self) -> List[ReachPoint]:
        """
        由鸣笛标和界限标创建多边形
        返回按顺序排列的四个点
        """
        # 获取鸣笛标的两个端点
        whistle_start = self.whistle_line.start
        whistle_end = self.whistle_line.end

        # 获取界限标的两个端点
        bound_start = self.bound_line.start
        bound_end = self.bound_line.end

        # 构建四边形，按顺序连接四个点
        # 顺序：鸣笛标起点 -> 鸣笛标终点 -> 界限标终点 -> 界限标起点
        points = [
            whistle_start,
            whistle_end,
            bound_end,
            bound_start
        ]

        return order_polygon_points(points)

    def to_polygon(self) -> ReachPolygon:
        """转换为多边形对象"""
        return ReachPolygon(points=self.polygon)

    def to_coords_list(self) -> List[List[float]]:
        """转换为Leaflet坐标格式"""
        return [p.to_list() for p in self.polygon]

    def contains_point(self, lat: float, lon: float) -> bool:
        """
        判断点是否在揭示区域内

        Args:
            lat: 纬度
            lon: 经度

        Returns:
            True如果在区域内
        """
        polygon = self.to_polygon()
        return polygon.contains_point(lat, lon)

    def get_bounds(self) -> Tuple[float, float, float, float]:
        """获取区域边界"""
        lats = [p.lat for p in self.polygon]
        lons = [p.lon for p in self.polygon]
        return (min(lats), max(lats), min(lons), max(lons))

    def get_center(self) -> ReachPoint:
        """获取区域中心点"""
        center_lat = sum(p.lat for p in self.polygon) / 4
        center_lon = sum(p.lon for p in self.polygon) / 4
        return ReachPoint(lat=center_lat, lon=center_lon)

@dataclass
class ControlReach:
    """控制河段数据"""
    reach_name: str
    reach_code: str
    center_point: ReachPoint  # 地图中心点

    # 上下界限标
    up_bound_line: Optional[ReachLine] = None
    down_bound_line: Optional[ReachLine] = None

    # 上下鸣笛标
    up_whistle_line: Optional[ReachLine] = None
    down_whistle_line: Optional[ReachLine] = None

    # 上下水计算范围（多边形）
    up_calc_polygon: Optional[ReachPolygon] = None
    down_calc_polygon: Optional[ReachPolygon] = None

    # 围栏区域列表
    park_areas: List[FenceArea] = None  # 停泊区
    special_areas: List[FenceArea] = None  # 特殊区

    # 控制河段区域（由上下界限标围成）
    control_area: Optional[ControlArea] = None

    # 揭示区域（由鸣笛标和界限标围成）
    up_reveal_area: Optional[RevealArea] = None  # 上水揭示区
    down_reveal_area: Optional[RevealArea] = None  # 下水揭示区

    def __post_init__(self):
        if self.park_areas is None:
            self.park_areas = []
        if self.special_areas is None:
            self.special_areas = []

        # 如果有上下界限标，创建控制区域
        if self.up_bound_line and self.down_bound_line:
            self.control_area = ControlArea(
                up_line=self.up_bound_line,
                down_line=self.down_bound_line
                )

        # 如果有上鸣笛标和上界限标，创建上水揭示区域
        if self.up_whistle_line and self.up_bound_line:
            self.up_reveal_area = RevealArea(
                name='up_reveal',
                whistle_line=self.up_whistle_line,
                bound_line=self.up_bound_line,
                description='上水揭示区'
            )

        # 如果有下鸣笛标和下界限标，创建下水揭示区域
        if self.down_whistle_line and self.down_bound_line:
            self.down_reveal_area = RevealArea(
                name='down_reveal',
                whistle_line=self.down_whistle_line,
                bound_line=self.down_bound_line,
                description='下水揭示区'
            )

    def to_dict(self) -> dict:
        """转换为字典，用于JavaScript"""
        data = {
            'reachName': self.reach_name,
            'reachCode': self.reach_code,
            'center': self.center_point.to_list()
        }

        # 添加上下界限标
        if self.up_bound_line:
            data['upBordLine'] = self.up_bound_line.to_coords_list()
        if self.down_bound_line:
            data['downBordLine'] = self.down_bound_line.to_coords_list()

        # 添加上下鸣笛标
        if self.up_whistle_line:
            data['upWhistle'] = self.up_whistle_line.to_coords_list()
        if self.down_whistle_line:
            data['downWhistle'] = self.down_whistle_line.to_coords_list()

        # 添加控制河段区域（用于地图显示）
        if self.control_area:
            data['controlArea'] = self.control_area.to_polygon().to_coords_list()

        # 添加上下水计算范围（多边形）
        if self.up_calc_polygon:
            data['upCalcPolygon'] = self.up_calc_polygon.to_coords_list()
        if self.down_calc_polygon:
            data['downCalcPolygon'] = self.down_calc_polygon.to_coords_list()

        # 添加上水揭示区域
        if self.up_reveal_area:
            data['upRevealArea'] = self.up_reveal_area.to_coords_list()
            data['upRevealName'] = '上水揭示区'

        # 添加下水揭示区域
        if self.down_reveal_area:
            data['downRevealArea'] = self.down_reveal_area.to_coords_list()
            data['downRevealName'] = '下水揭示区'

        # 添加停泊区
        if self.park_areas:
            data['parkAreas'] = [
                {
                    'name': area.fence_name,
                    'points': area.to_coords_list()
                }
                for area in self.park_areas
            ]

        # 添加特殊区
        if self.special_areas:
            data['specialAreas'] = [
                {
                    'name': area.fence_name,
                    'points': area.to_coords_list()
                }
                for area in self.special_areas
            ]

        return data

    def is_point_in_up_calc_area(self, lat: float, lon: float) -> bool:
        """判断点是否在上游计算区域内"""
        if self.up_calc_polygon:
            return self.up_calc_polygon.contains_point(lat, lon)
        return False

    def is_point_in_down_calc_area(self, lat: float, lon: float) -> bool:
        """判断点是否在下游计算区域内"""
        if self.down_calc_polygon:
            return self.down_calc_polygon.contains_point(lat, lon)
        return False

    def is_point_in_up_reveal_area(self, lat: float, lon: float) -> bool:
        """判断点是否在上水揭示区域内"""
        if self.up_reveal_area:
            return self.up_reveal_area.contains_point(lat, lon)
        return False

    def is_point_in_down_reveal_area(self, lat: float, lon: float) -> bool:
        """判断点是否在下水揭示区域内"""
        if self.down_reveal_area:
            return self.down_reveal_area.contains_point(lat, lon)
        return False

    def get_park_area_by_name(self, name: str) -> Optional[FenceArea]:
        """根据名称获取停泊区"""
        for area in self.park_areas:
            if area.fence_name == name:
                return area
        return None

    def get_special_area_by_name(self, name: str) -> Optional[FenceArea]:
        """根据名称获取特殊区"""
        for area in self.special_areas:
            if area.fence_name == name:
                return area
        return None

    def is_point_in_any_park(self, lat: float, lon: float) -> Optional[FenceArea]:
        """判断点是否在任意停泊区内"""
        for area in self.park_areas:
            if area.contains_point(lat, lon):
                return area
        return None

    def is_point_in_any_special(self, lat: float, lon: float) -> Optional[FenceArea]:
        """判断点是否在任意特殊区内"""
        for area in self.special_areas:
            if area.contains_point(lat, lon):
                return area
        return None

    def is_point_in_control_area(self, lat: float, lon: float) -> bool:
        """
        判断点是否在控制河段区域内（由上下界限标围成）

        Args:
            lat: 纬度
            lon: 经度

        Returns:
            True如果在控制区域内
        """
        if self.control_area:
            return self.control_area.contains_point(lat, lon)
        return False

    def get_calc_area_bounds(self) -> dict:
        """获取所有计算区域的边界"""
        bounds = {}

        if self.up_calc_polygon:
            min_lat, max_lat, min_lon, max_lon = self.up_calc_polygon.get_bounds()
            bounds['up'] = {
                'min_lat': min_lat, 'max_lat': max_lat,
                'min_lon': min_lon, 'max_lon': max_lon
            }

        if self.down_calc_polygon:
            min_lat, max_lat, min_lon, max_lon = self.down_calc_polygon.get_bounds()
            bounds['down'] = {
                'min_lat': min_lat, 'max_lat': max_lat,
                'min_lon': min_lon, 'max_lon': max_lon
            }

        return bounds