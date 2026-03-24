# map_drawer.py
import json
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QObject, pyqtSignal
from reach_data import ControlReach


class MapDrawer(QObject):
    """地图绘制器"""

    def __init__(self, web_view: QWebEngineView):
        super().__init__()
        self.web_view = web_view
        self.current_reach = None

        # 等待地图加载完成
        self.web_view.loadFinished.connect(self.on_map_loaded)
        self.map_ready = False

    def on_map_loaded(self, ok):
        """地图加载完成"""
        if ok:
            self.map_ready = True
            print("地图已就绪")

    def set_center(self, lat: float, lon: float, zoom: int = 14):
        """设置地图中心点"""
        if not self.map_ready:
            print("地图未就绪")
            return

        js_code = f"""
        if (typeof setMapView === 'function') {{
            setMapView({lat}, {lon}, {zoom});
        }} else {{
            map.setView([{lat}, {lon}], {zoom});
        }}
        """
        self.web_view.page().runJavaScript(js_code)
        print(f"设置地图中心: {lat}, {lon}, 缩放: {zoom}")

    def draw_reach(self, reach: ControlReach):
        """
        在地图上绘制控制河段的所有要素

        Args:
            reach: 控制河段数据
        """
        if not self.map_ready:
            print("地图未就绪，延迟绘制")
            # 可以缓存起来等地图就绪后再绘制
            self.current_reach = reach
            return

        self.current_reach = reach

        # 先设置中心点
        self.set_center(reach.center_point.lat, reach.center_point.lon, 14)

        # 构建要绘制的数据
        reach_data = reach.to_dict()
        data_json = json.dumps(reach_data, ensure_ascii=False)

        # 调用JavaScript函数绘制
        js_code = f"""
        (function() {{
            // 清除现有的所有图层
            if (window.reachLayers) {{
                window.reachLayers.clearLayers();
            }} else {{
                window.reachLayers = L.layerGroup().addTo(map);
            }}

            var data = {data_json};

            // 定义样式
            var lineStyle = {{
                color: '#ff0000',
                weight: 3,
                opacity: 0.8
            }};

            var boundStyle = {{
                color: '#0000ff',
                weight: 4,
                opacity: 0.9,
                dashArray: '5, 5'
            }};

            var whistleStyle = {{
                color: '#00ff00',
                weight: 2,
                fillColor: '#00ff00',
                fillOpacity: 0.8
            }};

            // 绘制上下界限标
            if (data.upBoundLine) {{
                var polyline = L.polyline(data.upBoundLine, {{
                    color: '#ff0000',
                    weight: 4,
                    opacity: 0.9
                }}).addTo(window.reachLayers);
                polyline.bindPopup('上游界限标');
            }}

            if (data.downBoundLine) {{
                var polyline = L.polyline(data.downBoundLine, {{
                    color: '#0000ff',
                    weight: 4,
                    opacity: 0.9
                }}).addTo(window.reachLayers);
                polyline.bindPopup('下游界限标');
            }}

            // 绘制上下鸣笛标
            if (data.upWhistle) {{
                var marker = L.circleMarker(data.upWhistle, {{
                    radius: 8,
                    color: '#ff9900',
                    weight: 2,
                    fillColor: '#ff9900',
                    fillOpacity: 0.8
                }}).addTo(window.reachLayers);
                marker.bindPopup('上游鸣笛标');
            }}

            if (data.downWhistle) {{
                var marker = L.circleMarker(data.downWhistle, {{
                    radius: 8,
                    color: '#ff9900',
                    weight: 2,
                    fillColor: '#ff9900',
                    fillOpacity: 0.8
                }}).addTo(window.reachLayers);
                marker.bindPopup('下游鸣笛标');
            }}

            // 绘制上下水计算范围
            if (data.upCalcLine) {{
                var polyline = L.polyline(data.upCalcLine, {{
                    color: '#00ff00',
                    weight: 3,
                    opacity: 0.7,
                    dashArray: '10, 10'
                }}).addTo(window.reachLayers);
                polyline.bindPopup('上游计算范围');
            }}

            if (data.downCalcLine) {{
                var polyline = L.polyline(data.downCalcLine, {{
                    color: '#00ff00',
                    weight: 3,
                    opacity: 0.7,
                    dashArray: '10, 10'
                }}).addTo(window.reachLayers);
                polyline.bindPopup('下游计算范围');
            }}

            // 添加河段名称标签
            var center = data.center;
            var label = L.marker(center, {{
                icon: L.divIcon({{
                    className: 'reach-label',
                    html: '<div style="background-color: white; padding: 2px 5px; border-radius: 3px; border: 1px solid #333; font-weight: bold;">' + data.reachName + '</div>',
                    iconSize: [100, 20],
                    iconAnchor: [50, 10]
                }})
            }}).addTo(window.reachLayers);

            console.log('河段 ' + data.reachName + ' 绘制完成');
        }})();
        """

        self.web_view.page().runJavaScript(js_code)
        print(f"河段 {reach.reach_name} 绘制完成")

    def clear_reach(self):
        """清除当前绘制的河段"""
        js_code = """
        if (window.reachLayers) {
            window.reachLayers.clearLayers();
        }
        """
        self.web_view.page().runJavaScript(js_code)
        print("已清除河段绘制")

