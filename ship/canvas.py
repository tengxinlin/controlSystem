import sys
from PyQt5.QtWidgets import *
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QTimer, QUrl
import folium


class OptimizedShipMap(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ships = {}
        self.initUI()

    def initUI(self):
        self.setWindowTitle('船舶位置显示 - 优化版')
        self.setGeometry(100, 100, 1000, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.webview = QWebEngineView()
        layout.addWidget(self.webview)

        # 初始加载
        self.create_base_html()

    def create_base_html(self):
        """创建基础HTML页面"""
        html = '''
        <!DOCTYPE html>
        <html>
        <head>
            <title>船舶地图</title>
            <meta charset="utf-8" />
            <meta name="viewport" content="width=device-width, initial-scale=1.0">
            <link rel="stylesheet" href="https://unpkg.com/leaflet@1.9.4/dist/leaflet.css" />
            <script src="https://unpkg.com/leaflet@1.9.4/dist/leaflet.js"></script>
            <style>
                #map { height: 600px; }
                .leaflet-control-attribution { display: none !important; }
                .ship-icon { background: transparent; border: none; }
            </style>
        </head>
        <body>
            <div id="map"></div>

            <script>
                // 地图初始化
                var map = L.map('map').setView([23.1291, 113.2644], 12);

                L.tileLayer('https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png', {
                    attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors'
                }).addTo(map);

                // 船舶标记存储
                var shipMarkers = {};

                // 创建船舶图标
                function createShipIcon(color, angle) {
                    var size = 30;
                    var html = '<div style="' +
                        'width: 0; height: 0;' +
                        'border-left: ' + size + 'px solid transparent;' +
                        'border-right: ' + size + 'px solid transparent;' +
                        'border-bottom: ' + size + 'px solid ' + color + ';' +
                        'transform: rotate(' + angle + 'deg);' +
                        'filter: drop-shadow(1px 1px 1px rgba(0,0,0,0.5));' +
                        '"></div>';

                    return L.divIcon({
                        html: html,
                        iconSize: [30, 30],
                        iconAnchor: [15, 15],
                        className: 'ship-icon'
                    });
                }

                // 更新船舶位置
                window.updateShip = function(shipId, lat, lng, angle, color) {
                    // 如果船舶已存在，更新位置
                    if (shipMarkers[shipId]) {
                        shipMarkers[shipId].setLatLng([lat, lng]);
                        shipMarkers[shipId].setIcon(createShipIcon(color, angle));
                        shipMarkers[shipId].setPopupContent(
                            '<b>船舶ID:</b> ' + shipId + '<br>' +
                            '<b>位置:</b> ' + lat.toFixed(4) + ', ' + lng.toFixed(4) + '<br>' +
                            '<b>航向:</b> ' + angle + '°'
                        );
                    } 
                    // 否则创建新标记
                    else {
                        var marker = L.marker([lat, lng], {
                            icon: createShipIcon(color, angle)
                        }).addTo(map);

                        marker.bindPopup(
                            '<b>船舶ID:</b> ' + shipId + '<br>' +
                            '<b>位置:</b> ' + lat.toFixed(4) + ', ' + lng.toFixed(4) + '<br>' +
                            '<b>航向:</b> ' + angle + '°'
                        );

                        shipMarkers[shipId] = marker;
                    }
                }

                // 移除船舶
                window.removeShip = function(shipId) {
                    if (shipMarkers[shipId]) {
                        map.removeLayer(shipMarkers[shipId]);
                        delete shipMarkers[shipId];
                    }
                }

                // 清除所有船舶
                window.clearAllShips = function() {
                    for (var id in shipMarkers) {
                        map.removeLayer(shipMarkers[id]);
                    }
                    shipMarkers = {};
                }
            </script>
        </body>
        </html>
        '''

        self.webview.setHtml(html, QUrl("https://unpkg.com/"))

        # 连接JavaScript控制台
        self.webview.page().javaScriptConsoleMessage = self.on_js_console

    def on_js_console(self, level, message, line, source):
        """JavaScript控制台消息"""
        if 'error' in level:
            print(f"JS错误: {message}")

    def update_ship(self, ship_id, lat, lng, angle, color='#FF0000'):
        """更新船舶位置"""
        js_code = f'''
        if (typeof updateShip === 'function') {{
            updateShip("{ship_id}", {lat}, {lng}, {angle}, "{color}");
        }}
        '''
        self.webview.page().runJavaScript(js_code)

    def remove_ship(self, ship_id):
        """移除船舶"""
        js_code = f'''
        if (typeof removeShip === 'function') {{
            removeShip("{ship_id}");
        }}
        '''
        self.webview.page().runJavaScript(js_code)

    def clear_all_ships(self):
        """清除所有船舶"""
        js_code = '''
        if (typeof clearAllShips === 'function') {
            clearAllShips();
        }
        '''
        self.webview.page().runJavaScript(js_code)


# 使用示例
class TestApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.ship_map = OptimizedShipMap()
        self.setCentralWidget(self.ship_map)
        self.setWindowTitle('船舶位置测试')
        self.setGeometry(100, 100, 1000, 600)

        # 测试数据
        QTimer.singleShot(1000, self.test_updates)

    def test_updates(self):
        """测试船舶更新"""
        # 添加船舶
        self.ship_map.update_ship("SHIP001", 23.1291, 113.2644, 45, '#FF0000')

        # 5秒后更新位置
        QTimer.singleShot(5000, lambda:
        self.ship_map.update_ship("SHIP001", 23.1300, 113.2650, 90, '#FF0000')
                          )

        # 添加第二艘船
        QTimer.singleShot(2000, lambda:
        self.ship_map.update_ship("SHIP002", 23.1200, 113.2700, 180, '#0000FF')
                          )

        # 添加第三艘船
        QTimer.singleShot(3000, lambda:
        self.ship_map.update_ship("SHIP003", 23.1400, 113.2500, 270, '#00FF00')
                          )

        # 10秒后移除一艘船
        QTimer.singleShot(10000, lambda:
        self.ship_map.remove_ship("SHIP002")
                          )


if __name__ == '__main__':
    app = QApplication(sys.argv)
    window = TestApp()
    window.show()
    sys.exit(app.exec_())