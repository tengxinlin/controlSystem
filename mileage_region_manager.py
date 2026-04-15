# mileage_region_manager.py
import math
import json
from typing import List, Dict, Tuple, Optional
from channel_mileage import MileageLine, MileageRegion, haversine_distance, point_to_line_distance


class MileageRegionManager:
    """航道里程区域管理器"""

    def __init__(self):
        self.mileage_lines: Dict[float, MileageLine] = {}  # km -> MileageLine
        self.mileage_regions: List[MileageRegion] = []  # 按里程排序的区域列表
        self.subregions: Dict[str, List[Tuple[float, float]]] = {}  # 细分区域

        # 细分参数
        self.subdivision_count = 100  # 每个区域细分成100份

        self.up_bound_km=0


    def load_from_db(self, db_manager):
        """
        从数据库加载航道里程线数据

        Args:
            db_manager: 数据库管理器实例
        """
        try:
            # 查询ChannelMileageLine表中的数据
            query = "SELECT KM, Points FROM ChannelMileageLine ORDER BY KM"
            results = db_manager.fetch_all(query)

            self.mileage_lines.clear()

            for row in results:
                km = float(row['KM'])
                point_str = row['Points']

                # 解析坐标字符串
                coords = self._parse_coordinates(point_str)
                if coords and len(coords) >= 4:
                    # 假设字符串格式: lat1,lon1,lat2,lon2
                    line = MileageLine(
                        km=km,
                        start_point=(coords[0], coords[1]),
                        end_point=(coords[2], coords[3])
                    )
                    self.mileage_lines[km] = line

            print(f"成功加载 {len(self.mileage_lines)} 条航道里程线")

            # 构建里程区域
            self._build_mileage_regions()

            # 细分区域
            self._subdivide_regions()

        except Exception as e:
            print(f"加载航道里程数据失败: {e}")
            import traceback
            traceback.print_exc()

    def _parse_coordinates(self, point_str: str) -> List[float]:
        """
        解析坐标字符串

        Args:
            point_str: 格式如 "29.6160446595008,106.862549185753,29.6116234772418,106.872462630272"

        Returns:
            浮点数列表 [lat1, lon1, lat2, lon2]
        """
        try:
            parts = point_str.strip().split(',')
            return [float(p.strip()) for p in parts]
        except Exception as e:
            print(f"解析坐标失败: {point_str}, 错误: {e}")
            return []

    def _build_mileage_regions(self):
        """
        构建里程区域（相邻两条里程线之间的区域）
        """
        # 按里程排序
        sorted_kms = sorted(self.mileage_lines.keys())
        self.mileage_regions.clear()

        for i in range(len(sorted_kms) - 1):
            km1 = sorted_kms[i]
            km2 = sorted_kms[i + 1]

            # 确定上下游
            # 假设km越小越靠近上游
            if km1 > km2:
                upstream_line = self.mileage_lines[km1]
                downstream_line = self.mileage_lines[km2]
            else:
                upstream_line = self.mileage_lines[km2]
                downstream_line = self.mileage_lines[km1]

            region = MileageRegion(
                upstream_line=upstream_line,
                downstream_line=downstream_line,
                region_id=f"{upstream_line.km:.1f}_{downstream_line.km:.1f}"
            )

            self.mileage_regions.append(region)

        # 按上游里程排序
        self.mileage_regions.sort(key=lambda r: r.upstream_km)

        print(f"构建了 {len(self.mileage_regions)} 个里程区域")

    def _subdivide_regions(self):
        """
        将每个里程区域细分为1000份
        """
        self.subregions.clear()
        self.subdivision_areas = {}  # 新增：存储细分区域（相邻两条线之间的区域）

        for region in self.mileage_regions:
            region_id = region.region_id

            # 获取两条里程线的端点
            up_start = region.upstream_line.start_point
            up_end = region.upstream_line.end_point
            down_start = region.downstream_line.start_point
            down_end = region.downstream_line.end_point

            # 匹配端点：判断上游起点应该对应下游起点还是下游终点
            # 计算上游起点到下游两个端点的距离
            dist_start_to_down_start = haversine_distance(
                up_start[0], up_start[1], down_start[0], down_start[1]
            )
            dist_start_to_down_end = haversine_distance(
                up_start[0], up_start[1], down_end[0], down_end[1]
            )

            # 计算上游终点到下游两个端点的距离
            dist_end_to_down_start = haversine_distance(
                up_end[0], up_end[1], down_start[0], down_start[1]
            )
            dist_end_to_down_end = haversine_distance(
                up_end[0], up_end[1], down_end[0], down_end[1]
            )

            # 确定匹配关系
            # 方案1: 起点匹配到最近的，终点匹配到另一个
            if dist_start_to_down_start + dist_end_to_down_end < dist_start_to_down_end + dist_end_to_down_start:
                # 起点对应下游起点，终点对应下游终点
                matched_down_start = down_start
                matched_down_end = down_end
                match_type = "正常匹配"
            else:
                # 起点对应下游终点，终点对应下游起点（交叉）
                matched_down_start = down_end
                matched_down_end = down_start
                match_type = "交叉匹配"

            # 细分点列表
            sub_points = []

            # 在上下游里程线的对应端点之间进行线性插值
            for i in range(self.subdivision_count + 1):
                t = i / self.subdivision_count  # 插值参数 0~1

                # 起点之间的插值（上游起点 -> 下游起点）
                start_lat = up_start[0] + t * (matched_down_start[0] - up_start[0])
                start_lon = up_start[1] + t * (matched_down_start[1] - up_start[1])

                # 终点之间的插值（上游终点 -> 下游终点）
                end_lat = up_end[0] + t * (matched_down_end[0] - up_end[0])
                end_lon = up_end[1] + t * (matched_down_end[1] - up_end[1])

                # 保存当前细分位置的线段（两个端点）
                sub_points.append({
                    'index': i,
                    't': t,
                    'start_point': (start_lat, start_lon),  # 靠近起点侧的点
                    'end_point': (end_lat, end_lon),  # 靠近终点侧的点,
                    'km': region.upstream_km + t * (region.downstream_km - region.upstream_km)  # 对应的里程数
                })

            self.subregions[region_id] = sub_points

            # 构建细分区域（相邻两条细分线之间的区域）
            areas = []
            for i in range(len(sub_points) - 1):
                line_down = sub_points[i]
                line_up = sub_points[i + 1]

                # 区域由四条线段围成：
                # 上边界：当前细分线（line_current）
                # 下边界：下一条细分线（line_next）
                # 左侧边：当前线的起点到下一条线的起点
                # 右侧边：当前线的终点到下一条线的终点

                # # 构建区域的多边形顶点（按顺序）
                # # 顺序：当前线起点 -> 当前线终点 -> 下一条线终点 -> 下一条线起点
                # polygon_points = [
                #     line_current['start_point'],  # 当前线起点
                #     line_current['end_point'],  # 当前线终点
                #     line_next['end_point'],  # 下一条线终点
                #     line_next['start_point']  # 下一条线起点
                # ]
                #
                # # 计算区域中心点（用于快速定位）
                # center_lat = sum(p[0] for p in polygon_points) / 4
                # center_lon = sum(p[1] for p in polygon_points) / 4

                areas.append({
                    'area_index': i,
                    'up_line_index': i,  # 上边界线索引
                    'down_line_index': i + 1,  # 下边界线索引
                    'line_down': line_down,
                    'line_up': line_up,
                    # 'up_km': line_current['km'],  # 上边界里程
                    # 'down_km': line_next['km'],  # 下边界里程
                    # 'polygon': polygon_points,  # 区域多边形顶点
                    # 'center': (center_lat, center_lon)  # 区域中心点
                })

            self.subdivision_areas[region_id] = areas

        print(f"完成了 {len(self.subregions)} 个区域的细分，每个区域 {self.subdivision_count + 1} 个细分点")



    def line_intersection_with_direction(self, point: Tuple[float, float],
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

        # 计算射线方向向量
        # 航向角：0°北 -> (0, 1) 纬度增加
        # 90°东 -> (1, 0) 经度增加
        heading_rad = math.radians(heading)
        dx = math.sin(heading_rad)  # 经度方向变化
        dy = math.cos(heading_rad)  # 纬度方向变化



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

        if abs(cross) < 1e-10:

            return None

        # 计算参数
        # t 是线段参数，u 是射线参数
        t = (wx * dy - wy * dx) / cross
        u = (wx * vy - wy * vx) / cross


        # 判断交点是否有效
        # t 在 [0,1] 之间表示交点在线段上
        # u >= 0 表示交点在射线正方向上
        if 0 <= t <= 1 and u >= 0:
            # 计算交点坐标
            intersect_lat = lat1 + t * vy
            intersect_lon = lon1 + t * vx

            # 计算距离
            distance = math.sqrt((intersect_lat - lat) ** 2 + (intersect_lon - lon) ** 2)


            if distance <= max_distance:

                return (intersect_lat, intersect_lon)
            else:
                pass
        else:
           pass

        return None

    def get_subdivision_area_by_index(self, region_id: str, area_index: int) -> Optional[Dict]:
        """
        根据索引获取细分区域

        Args:
            region_id: 区域ID
            area_index: 细分区域索引（0 到 subdivision_count-1）

        Returns:
            细分区域信息
        """
        if region_id not in self.subdivision_areas:
            return None

        areas = self.subdivision_areas[region_id]
        if 0 <= area_index < len(areas):
            return areas[area_index]

        return None

    def determine_ship_direction(self, ship_lat: float, ship_lon: float,
                                        ship_heading: float, target_region) -> str:
        """
        简化的射线法方向判断
        """
        # 只向前方发射射线
        forward_up = self.line_intersection_with_direction(
            (ship_lat, ship_lon), ship_heading,
            target_region['line_up']['start_point'],
            target_region['line_up']['end_point']
        )

        forward_down = self.line_intersection_with_direction(
            (ship_lat, ship_lon), ship_heading,
            target_region['line_down']['start_point'],
            target_region['line_down']['end_point']
        )

        # 判断逻辑：
        # 前方与上游线相交 -> 向上游行驶（上水）
        # 前方与下游线相交 -> 向下游行驶（下水）

        if forward_up and not forward_down:
            return 'up'
        elif forward_down and not forward_up:
            return 'down'
        elif forward_up and forward_down:
            # 选择距离较近的
            dist_up = ((ship_lat - forward_up[0]) ** 2 + (ship_lon - forward_up[1]) ** 2) ** 0.5
            dist_down = ((ship_lat - forward_down[0]) ** 2 + (ship_lon - forward_down[1]) ** 2) ** 0.5
            return 'up' if dist_up < dist_down else 'down'

        # 如果没有交点，尝试后方射线
        backward_up = self.line_intersection_with_direction(
            (ship_lat, ship_lon), (ship_heading + 180) % 360,
            target_region['line_up']['start_point'],
            target_region['line_up']['end_point']
        )

        backward_down = self.line_intersection_with_direction(
            (ship_lat, ship_lon), (ship_heading + 180) % 360,
            target_region['line_down']['start_point'],
            target_region['line_down']['end_point']
        )

        if backward_up and not backward_down:
            return 'down'  # 后方与上游线相交，说明船从上游来（下水）
        elif backward_down and not backward_up:
            return 'up'  # 后方与下游线相交，说明船从下游来（上水）

        return 'unknown'

    def _point_to_line_distance(self, point: Tuple[float, float],
                                line_start: Tuple[float, float],
                                line_end: Tuple[float, float]) -> float:
        """计算点到线段的距离"""
        import math

        lat, lon = point
        lat1, lon1 = line_start
        lat2, lon2 = line_end

        # 使用Haversine公式计算距离（简化版）
        # 这里用平面近似
        avg_lat = (lat + lat1 + lat2) / 3
        meter_per_deg_lat = 111320
        meter_per_deg_lon = 111320 * math.cos(math.radians(avg_lat))

        x = lon * meter_per_deg_lon
        y = lat * meter_per_deg_lat
        x1 = lon1 * meter_per_deg_lon
        y1 = lat1 * meter_per_deg_lat
        x2 = lon2 * meter_per_deg_lon
        y2 = lat2 * meter_per_deg_lat

        # 计算点到线段的距离
        A = x - x1
        B = y - y1
        C = x2 - x1
        D = y2 - y1

        dot = A * C + B * D
        len_sq = C * C + D * D

        if len_sq == 0:
            return math.sqrt((x - x1) ** 2 + (y - y1) ** 2)

        param = dot / len_sq

        if param < 0:
            xx, yy = x1, y1
        elif param > 1:
            xx, yy = x2, y2
        else:
            xx = x1 + param * C
            yy = y1 + param * D

        return math.sqrt((x - xx) ** 2 + (y - yy) ** 2)

    def _calculate_bearing(self, lat1: float, lon1: float, lat2: float, lon2: float) -> float:
        """计算两点间的方位角"""
        import math

        lat1_rad = math.radians(lat1)
        lat2_rad = math.radians(lat2)
        lon_diff_rad = math.radians(lon2 - lon1)

        x = math.sin(lon_diff_rad) * math.cos(lat2_rad)
        y = math.cos(lat1_rad) * math.sin(lat2_rad) - \
            math.sin(lat1_rad) * math.cos(lat2_rad) * math.cos(lon_diff_rad)

        bearing_rad = math.atan2(x, y)
        bearing_deg = math.degrees(bearing_rad)
        bearing_deg = (bearing_deg + 360) % 360

        return bearing_deg

    def calculate_upBoardkm(self,lat,lon):
        """计算上界限标中心点在航道里程线的距离"""
        # 1. 找到船舶所在的区域
        target_region = None
        min_distance = float('inf')

        for region in self.mileage_regions:
            # 计算到上游线和下游线的距离
            dist_up = point_to_line_distance(
                (lat, lon),
                region.upstream_line.start_point,
                region.upstream_line.end_point
            )

            dist_down = point_to_line_distance(
                (lat, lon),
                region.downstream_line.start_point,
                region.downstream_line.end_point
            )

            # 取较小的距离作为到该区域的距离
            distance = min(dist_up, dist_down)

            if distance < min_distance:
                min_distance = distance
                target_region = region

        if not target_region:
            return None

        # 2. 在目标区域的细分点中找到最近的索引
        region_id = target_region.region_id
        sub_points = self.subregions.get(region_id, [])

        if not sub_points:
            return None

        # 计算船舶到每个细分点的距离
        best_index = 0
        best_distance = float('inf')


        for i, point_info in enumerate(sub_points):
            # 计算到线段的距离

            # 计算到下游细分点的距离
            dist_down = point_to_line_distance(
                (lat, lon),
                point_info['start_point'], point_info['end_point']
            )

            if dist_down < best_distance:
                best_distance = dist_down
                best_index = i


        # 3. 计算里程和偏移
        km_range = target_region.km_range
        total_km = km_range[1] - km_range[0]

        # 根据索引计算里程
        t = best_index / self.subdivision_count
        estimated_km = km_range[0] + t * total_km


        self.up_bound_km=estimated_km
        return None

    def find_ship_position(self, ship_lat: float, ship_lon: float,
                           ship_heading: float = None) -> Optional[Dict]:
        """
        计算船舶在航道中的位置和方向

        Args:
            ship_lat: 船舶纬度
            ship_lon: 船舶经度
            ship_heading: 船舶航向角（度），可选

        Returns:
            包含位置信息的字典，如果找不到返回None
        """
        # 1. 找到船舶所在的区域
        target_region = None
        min_distance = float('inf')

        for region in self.mileage_regions:
            # 计算到上游线和下游线的距离
            dist_up = point_to_line_distance(
                (ship_lat, ship_lon),
                region.upstream_line.start_point,
                region.upstream_line.end_point
            )

            dist_down = point_to_line_distance(
                (ship_lat, ship_lon),
                region.downstream_line.start_point,
                region.downstream_line.end_point
            )

            # 取较小的距离作为到该区域的距离
            distance = min(dist_up, dist_down)

            if distance < min_distance:
                min_distance = distance
                target_region = region

        if not target_region:
            return None

        # 2. 在目标区域的细分点中找到最近的索引
        region_id = target_region.region_id
        sub_points = self.subregions.get(region_id, [])

        if not sub_points:
            return None

        # 计算船舶到每个细分点的距离
        best_index = 0
        best_distance = float('inf')
        best_point_type = 'up'

        for i, point_info in enumerate(sub_points):
            dist = point_to_line_distance(
                (ship_lat, ship_lon),
                point_info['start_point'],
                point_info['end_point']
            )

            if dist < best_distance:
                best_distance = dist
                best_index = i

        region_sub_points = self.get_subdivision_area_by_index(region_id,best_index)
        # 3. 计算里程和偏移
        km_range = target_region.km_range
        total_km = km_range[1] - km_range[0]

        # 根据索引计算里程
        t = best_index / self.subdivision_count
        estimated_km = km_range[0] + t * total_km



        # 4. 判断船舶的上下水方向
        direction = 'unknown'
        if ship_heading is not None:
            direction = self.determine_ship_direction(
                ship_lat, ship_lon, ship_heading,region_sub_points
            )

        result = {
            'region_id': region_id,
            'upstream_km': target_region.upstream_km,
            'downstream_km': target_region.downstream_km,
            'estimated_km': estimated_km,  # 估计的里程数
            'subdivision_index': best_index,  # 细分索引
            'subdivision_t': t,  # 细分参数
            'direction': direction,  # 上下水方向
        }

        return result

    def calculate_distance_between_ships(self, ship1_lat: float, ship1_lon: float,
                                         ship2_lat: float, ship2_lon: float) -> Optional[float]:
        """
        计算两艘船之间的航道距离

        Args:
            ship1_lat, ship1_lon: 第一艘船坐标
            ship2_lat, ship2_lon: 第二艘船坐标

        Returns:
            航道距离（公里），如果无法计算返回None
        """
        pos1 = self.find_ship_position(ship1_lat, ship1_lon)
        pos2 = self.find_ship_position(ship2_lat, ship2_lon)

        if not pos1 or not pos2:
            return None

        # 使用估计的里程计算距离
        return abs(pos1['estimated_km'] - pos2['estimated_km'])

    def get_mileage_at_index(self, region_id: str, index: int) -> Optional[float]:
        """
        根据区域ID和细分索引获取里程数
        """
        if region_id not in self.subregions:
            return None

        # 找到对应的区域
        target_region = None
        for region in self.mileage_regions:
            if region.region_id == region_id:
                target_region = region
                break

        if not target_region:
            return None

        km_range = target_region.km_range
        t = index / self.subdivision_count

        return km_range[0] + t * (km_range[1] - km_range[0])

    def visualize_subdivision(self):
        """
        可视化细分结果，用于验证
        需要 matplotlib 支持
        """
        import matplotlib.pyplot as plt

        for region_id, sub_lines in self.subregions.items():
            # 找到对应的区域
            region = None
            for r in self.mileage_regions:
                if r.region_id == region_id:
                    region = r
                    break

            if not region:
                continue

            fig, ax = plt.subplots(figsize=(12, 10))

            # 绘制上游线（红色）
            up_start = region.upstream_line.start_point
            up_end = region.upstream_line.end_point
            ax.plot([up_start[1], up_end[1]], [up_start[0], up_end[0]], 'r-', linewidth=3, label='上游线')

            # 绘制下游线（蓝色）
            down_start = region.downstream_line.start_point
            down_end = region.downstream_line.end_point
            ax.plot([down_start[1], down_end[1]], [down_start[0], down_end[0]], 'b-', linewidth=3, label='下游线')

            # 绘制细分线（绿色，每隔50条画一条）
            for i, line_info in enumerate(sub_lines):
                if i % 20 == 0 or i == len(sub_lines) - 1:
                    start = line_info['start_point']
                    end = line_info['end_point']
                    ax.plot([start[1], end[1]], [start[0], end[0]], 'g-', linewidth=1, alpha=0.5)
                    # 标注里程
                    if i % 100 == 0:
                        mid_lat = (start[0] + end[0]) / 2
                        mid_lon = (start[1] + end[1]) / 2
                        ax.text(mid_lon, mid_lat, f'{line_info["km"]:.1f}km', fontsize=8, ha='center')

            ax.set_xlabel('经度')
            ax.set_ylabel('纬度')
            ax.set_title(f'里程区域细分 - {region_id}')
            ax.legend()
            ax.grid(True, alpha=0.3)
            plt.tight_layout()
            plt.show()

            # break  # 只显示第一个区域