# reach_loader.py
from typing import List, Optional, Dict
from reach_data import ControlReach, ReachPoint, ReachLine


class ReachLoader:
    """控制河段数据加载器"""

    def __init__(self, db_manager):
        self.db_manager = db_manager
        self.reaches: Dict[str, ControlReach] = {}  # reach_code -> ControlReach

    def load_reach_by_name(self, reach_name: str) -> Optional[ControlReach]:
        """
        根据河段名称加载控制河段数据

        Args:
            reach_name: 河段名称

        Returns:
            ControlReach对象，如果找不到返回None
        """
        try:

            # 查询Reaches表
            query = """
                    SELECT ReachName, \
                           ReachCode, \
                           CenterP, \
                           UpBordLine, \
                           DownBordLine,
                           UpWhistle, \
                           DownWhistle,
                           UpCalculateRange, \
                           DownCalculateRange
                    FROM Reaches
                    WHERE ReachName = ? \
                    """
            results = self.db_manager.fetch_all(query, (reach_name,))

            if not results:
                print(f"未找到河段: {reach_name}")
                return None

            row = results[0]

            # 解析地图中心点
            center_coords = row.get('CenterP', '')
            if center_coords:
                try:
                    lon, lat = center_coords.split(',')
                    center_point = ReachPoint(lat=float(lat), lon=float(lon))
                except:
                    # 如果解析失败，使用默认值
                    center_point = ReachPoint(lat=29.58, lon=106.65)
            else:
                center_point = ReachPoint(lat=29.58, lon=106.65)

            # 创建控制河段对象
            reach = ControlReach(
                reach_name=row['ReachName'],
                reach_code=row['ReachCode'],
                center_point=center_point
            )

            # 加载上下界限标
            if row.get('UpBordLine'):
                reach.up_bound_line = ReachLine.from_coords_str(row['UpBordLine'])
            if row.get('DownBordLine'):
                reach.down_bound_line = ReachLine.from_coords_str(row['DownBordLine'])

            # 加载上下鸣笛标
            if row.get('UpWhistle'):
                reach.up_whistle_line = ReachLine.from_coords_str(row['UpWhistle'])

            if row.get('DownWhistle'):
                try:
                    reach.down_whistle_line = ReachLine.from_coords_str(row['DownWhistle'])
                except:
                    pass

            # 加载上下水计算范围（多边形）
            if row.get('UpCalculateRange'):
                reach.up_calc_polygon = ReachPolygon.from_coords_str(row['UpCalculateRange'])
                if reach.up_calc_polygon:
                    print(f"上游计算范围: {len(reach.up_calc_polygon.points)} 个点")

            if row.get('DownCalculateRange'):
                reach.down_calc_polygon = ReachPolygon.from_coords_str(row['DownCalculateRange'])
                if reach.down_calc_polygon:
                    print(f"下游计算范围: {len(reach.down_calc_polygon.points)} 个点")

            # 缓存
            self.reaches[reach.reach_code] = reach

            print(f"成功加载河段: {reach_name}")
            return reach

        except Exception as e:
            print(f"加载河段数据失败: {e}")
            import traceback
            traceback.print_exc()
            return None

    def load_all_reaches(self) -> List[ControlReach]:
        """加载所有控制河段"""
        try:
            query = "SELECT ReachName FROM Reaches"
            results = self.db_manager.fetch_all(query)

            reaches = []
            for row in results:
                reach = self.load_reach_by_name(row['ReachName'])
                if reach:
                    reaches.append(reach)

            return reaches

        except Exception as e:
            print(f"加载所有河段失败: {e}")
            return []