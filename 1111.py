import math
from typing import Tuple, Optional


def line_intersection_with_direction(point: Tuple[float, float],
                                     heading: float,
                                     line_start: Tuple[float, float],
                                     line_end: Tuple[float, float],
                                     max_distance: float = 0.05) -> Optional[Tuple[float, float]]:
    """
    判断从点出发沿航向方向的射线是否与线段相交

    Args:
        point: 船舶位置 (lat, lon)
        heading: 航向角（度，0=北，顺时针增加，90=东）
        line_start: 线段起点 (lat, lon)
        line_end: 线段终点 (lat, lon)
        max_distance: 最大搜索距离（度）

    Returns:
        交点坐标 (lat, lon)，如果没有交点返回None
    """
    import math

    lat, lon = point
    lat1, lon1 = line_start
    lat2, lon2 = line_end

    print(f"\n点: ({lat:.6f}, {lon:.6f})")
    print(f"线段: ({lat1:.6f}, {lon1:.6f}) -> ({lat2:.6f}, {lon2:.6f})")
    print(f"航向: {heading}°")

    # 计算射线方向向量
    # 航向角：0°北 -> (0, 1) 纬度增加
    # 90°东 -> (1, 0) 经度增加
    heading_rad = math.radians(heading)
    dx = math.sin(heading_rad)  # 经度方向变化
    dy = math.cos(heading_rad)  # 纬度方向变化

    print(f"射线方向: (dx={dx:.6f}, dy={dy:.6f})")

    # 使用向量法判断射线与线段相交
    # 线段向量
    vx = lon2 - lon1
    vy = lat2 - lat1

    # 从线段起点到射线起点的向量
    wx = lon - lon1
    wy = lat - lat1

    # 计算叉积
    # 线段向量与射线向量的叉积
    cross = vx * dy - vy * dx

    print(f"叉积: {cross:.10f}")

    if abs(cross) < 1e-10:
        print("线段与射线平行")
        return None

    # 计算参数
    # t 是线段参数，u 是射线参数
    t = (wx * dy - wy * dx) / cross
    u = (wx * vy - wy * vx) / cross

    print(f"t={t:.6f}, u={u:.6f}")

    # 判断交点是否有效
    # t 在 [0,1] 之间表示交点在线段上
    # u >= 0 表示交点在射线正方向上
    if 0 <= t <= 1 and u >= 0:
        # 计算交点坐标
        intersect_lat = lat1 + t * vy
        intersect_lon = lon1 + t * vx

        # 计算距离
        distance = math.sqrt((intersect_lat - lat) ** 2 + (intersect_lon - lon) ** 2)
        print(f"交点距离: {distance * 111:.2f}公里")

        if distance <= max_distance:
            print(f"找到交点: ({intersect_lat:.6f}, {intersect_lon:.6f})")
            return (intersect_lat, intersect_lon)
        else:
            print(f"交点超出最大距离")
    else:
        print(f"无有效交点: t={t}, u={u}")

    return None


def test_intersection():
    """测试射线与线段相交算法"""
    print("=" * 60)
    print("测试1：射线向北，与水平线段相交")
    print("=" * 60)
    # 点(0,0)，heading=0°（北），线段从(-1,1)到(1,1)
    point = (0, 0)
    heading = 0
    line_start = (-1, 1)
    line_end = (1, 1)
    result = line_intersection_with_direction(point, heading, line_start, line_end, max_distance=2.0)
    print(f"结果: 应该相交于 (1, 0) -> {result}\n")

    print("=" * 60)
    print("测试2：射线向东，与垂直线段相交")
    print("=" * 60)
    # 点(0,0)，heading=90°（东），线段从(1,-1)到(1,1)
    point = (0, 0)
    heading = 90
    line_start = (1, -1)
    line_end = (1, 1)
    result = line_intersection_with_direction(point, heading, line_start, line_end, max_distance=2.0)
    print(f"结果: 应该相交于 (1, 0) -> {result}\n")

    print("=" * 60)
    print("测试3：射线向南，与水平线段相交")
    print("=" * 60)
    # 点(0,0)，heading=180°（南），线段从(-1,-1)到(1,-1)
    point = (0, 0)
    heading = 180
    line_start = (-1, -1)
    line_end = (1, -1)
    result = line_intersection_with_direction(point, heading, line_start, line_end, max_distance=2.0)
    print(f"结果: 应该相交于 (-1, 0) -> {result}\n")

    print("=" * 60)
    print("测试4：射线向西，与垂直线段相交")
    print("=" * 60)
    # 点(0,0)，heading=270°（西），线段从(-1,-1)到(-1,1)
    point = (0, 0)
    heading = 270
    line_start = (-1, -1)
    line_end = (-1, 1)
    result = line_intersection_with_direction(point, heading, line_start, line_end, max_distance=2.0)
    print(f"结果: 应该相交于 (-1, 0) -> {result}\n")

    print("=" * 60)
    print("测试5：射线45°（东北），与斜线段相交")
    print("=" * 60)
    # 点(0,0)，heading=45°，线段从(1,0)到(0,1)
    point = (0, 0)
    heading = 45
    line_start = (1, 0)
    line_end = (0, 1)
    result = line_intersection_with_direction(point, heading, line_start, line_end, max_distance=2.0)
    print(f"结果: 应该相交于 (0.5, 0.5) -> {result}\n")

    print("=" * 60)
    print("测试6：射线225°（西南），与斜线段相交")
    print("=" * 60)
    # 点(0,0)，heading=225°，线段从(-1,0)到(0,-1)
    point = (0, 0)
    heading = 225
    line_start = (-1, 0)
    line_end = (0, -1)
    result = line_intersection_with_direction(point, heading, line_start, line_end, max_distance=2.0)
    print(f"结果: 应该相交于 (-0.5, -0.5) -> {result}\n")

    print("=" * 60)
    print("测试7：射线向北，线段在后方（不应相交）")
    print("=" * 60)
    point = (0, 0)
    heading = 0
    line_start = (-1, -1)
    line_end = (1, -1)
    result = line_intersection_with_direction(point, heading, line_start, line_end, max_distance=2.0)
    print(f"结果: 应该不相交 -> {result}\n")


if __name__ == "__main__":
    test_intersection()

    print("\n使用说明:")
    print("ray_segment_intersection(ray_x, ray_y, angle, seg_start_x, seg_start_y, seg_end_x, seg_end_y)")
    print("- ray_x, ray_y: 射线起点坐标")
    print("- angle: 方向角度(0-360度，正北为0，顺时针)")
    print("- seg_start_x, seg_start_y: 线段起点坐标")
    print("- seg_end_x, seg_end_y: 线段终点坐标")
    print("- 返回: (是否相交, 交点x坐标, 交点y坐标)")