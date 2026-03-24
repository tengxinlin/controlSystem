# map_ship_drawer.py
import json
from typing import Dict, List
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QObject, pyqtSignal


class MapShipDrawer(QObject):
    """地图船舶绘制器 - 负责在Leaflet地图上绘制船舶"""

    def __init__(self, web_view: QWebEngineView):
        super().__init__()
        self.web_view = web_view
        self.ships = {}  # 记录已绘制的船舶mmsi

    def draw_ship(self, ship:Dict) -> None:
        """
        在地图上绘制单个船舶

        Args:
            :param ship:
        """
        js_code = f"""
        
        updateShipMarker({ship})
        """

        self.web_view.page().runJavaScript(js_code)

    def draw_ships_batch(self, ships: List[Dict]):
        """
        批量绘制船舶，主要是绘制历史轨迹时

        Args:
            ships: 船舶信息字典列表
        """
        ships_json = json.dumps(ships, ensure_ascii=False)

        js_code = f"""
        // 清除所有现有船舶标记
        if (window.shipMarkers) {{
            for (var mmsi in window.shipMarkers) {{
                map.removeLayer(window.shipMarkers[mmsi]);
            }}
        }}
        window.shipMarkers = {{}};

        // 批量添加新标记
        var ships = {ships_json};
        ships.forEach(function(ship) {{
            var iconColor = ship.direction === '上行' ? '#ff4444' : 
                           (ship.direction === '下行' ? '#4444ff' : '#888888');

            var shipIcon = L.divIcon({{
                className: 'ship-marker',
                html: `<div style="
                    transform: rotate(${{ship.course}}deg);
                    font-size: 24px;
                    color: ${{iconColor}};
                    text-shadow: 2px 2px 2px rgba(0,0,0,0.5);
                ">🚢</div>`,
                iconSize: [24, 24],
                iconAnchor: [12, 12],
                popupAnchor: [0, -12]
            }});

            var marker = L.marker([ship.lat, ship.lon], {{
                icon: shipIcon,
                title: ship.name
            }}).addTo(map);

            marker.bindPopup(`
                <b>${{ship.name}}</b><br>
                MMSI: ${{ship.mmsi}}<br>
                航向: ${{ship.course}}°<br>
                方向: ${{ship.direction}}<br>
                位置: ${{ship.lat.toFixed(4)}}, ${{ship.lon.toFixed(4)}}
            `);

            window.shipMarkers[ship.mmsi] = marker;
        }});
        """

        self.web_view.page().runJavaScript(js_code)

    def remove_ship(self, mmsi: str):
        """从地图上移除船舶"""
        js_code = f"""
        removeShipMarker({mmsi})
        """
        self.web_view.page().runJavaScript(js_code)

    def clear_all_ships(self):
        """清除地图上所有船舶"""
        js_code = """
        if (window.shipMarkers) {
            for (var mmsi in window.shipMarkers) {
                map.removeLayer(window.shipMarkers[mmsi]);
            }
            window.shipMarkers = {};
        }
        """
        self.web_view.page().runJavaScript(js_code)

    def _get_direction_color(self, direction: str) -> str:
        """根据方向获取图标颜色"""
        color_map = {
            "上行": "#ff4444",  # 红色
            "下行": "#4444ff",  # 蓝色
            "未知": "#888888"  # 灰色
        }
        return color_map.get(direction, "#888888")

