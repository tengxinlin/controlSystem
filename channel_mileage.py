# channel_mileage.py
import math
import json
from typing import List, Tuple, Optional
from dataclasses import dataclass
import numpy as np


@dataclass
class MileageLine:
    """航道里程线数据类"""
    km: float  # 里程数（公里）
    start_point: Tuple[float, float]  # 起点坐标 (lat, lon)
    end_point: Tuple[float, float]  # 终点坐标 (lat, lon)

    def get_center(self) -> Tuple[float, float]:
        """获取线段中心点"""
        return ((self.start_point[0] + self.end_point[0]) / 2,
                (self.start_point[1] + self.end_point[1]) / 2)

    def get_length(self) -> float:
        """获取线段长度（米）"""
        return haversine_distance(
            self.start_point[0], self.start_point[1],
            self.end_point[0], self.end_point[1]
        )


@dataclass
class MileageRegion:
    """里程区域（两条里程线之间的区域）"""
    upstream_line: MileageLine  # 上游里程线
    downstream_line: MileageLine  # 下游里程线
    region_id: str = ""  # 区域标识
    polygon: List[Tuple[float, float]] = None  # 区域多边形顶点

    @property
    def upstream_km(self) -> float:
        return self.upstream_line.km

    @property
    def downstream_km(self) -> float:
        return self.downstream_line.km

    @property
    def km_range(self) -> Tuple[float, float]:
        """里程范围（从小到大）"""
        return sorted([self.downstream_km, self.upstream_km])

    def contains_point(self, lat: float, lon: float) -> bool:
        """判断点是否在这个区域的多边形内"""
        if not self.polygon:
            return False
        return point_in_polygon((lat, lon), self.polygon)



def point_in_polygon(point: Tuple[float, float], polygon: List[Tuple[float, float]]) -> bool:
    """
    判断点是否在多边形内（射线法）

    Args:
        point: 待判断的点 (lat, lon)
        polygon: 多边形顶点列表 [(lat, lon), ...]

    Returns:
        True 如果在多边形内
    """
    x, y = point
    inside = False
    n = len(polygon)

    for i in range(n):
        x1, y1 = polygon[i]
        x2, y2 = polygon[(i + 1) % n]

        # 检查射线是否与边相交
        if ((y1 > y) != (y2 > y)) and (x < (x2 - x1) * (y - y1) / (y2 - y1) + x1):
            inside = not inside

    return inside

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    计算两点间的球面距离（米）
    """
    R = 6371000  # 地球半径（米）

    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    delta_phi = math.radians(lat2 - lat1)
    delta_lambda = math.radians(lon2 - lon1)

    a = math.sin(delta_phi / 2) ** 2 + \
        math.cos(phi1) * math.cos(phi2) * math.sin(delta_lambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))

    return R * c


def point_to_line_distance(point: Tuple[float, float],
                           line_start: Tuple[float, float],
                           line_end: Tuple[float, float]) -> float:
    """
    计算点到线段的距离（米）
    """
    lat, lon = point
    lat1, lon1 = line_start
    lat2, lon2 = line_end

    # 将经纬度转换为平面坐标（近似）
    x, y = lon, lat
    x1, y1 = lon1, lat1
    x2, y2 = lon2, lat2

    # 计算点到线段的距离
    A = x - x1
    B = y - y1
    C = x2 - x1
    D = y2 - y1

    dot = A * C + B * D
    len_sq = C * C + D * D
    param = -1

    if len_sq != 0:
        param = dot / len_sq

    if param < 0:
        xx, yy = x1, y1
    elif param > 1:
        xx, yy = x2, y2
    else:
        xx = x1 + param * C
        yy = y1 + param * D

    # 将距离转换回米
    dx = (xx - x) * 111320 * math.cos(math.radians((yy + y) / 2))
    dy = (yy - y) * 110540

    return math.sqrt(dx * dx + dy * dy)