import sys
import folium
from PyQt5.QtWebEngineWidgets import QWebEngineView
from folium.features import DivIcon
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget


class FontAwesomeMap(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('Font Awesome 三角形标记')
        self.setGeometry(100, 100, 800, 600)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.webview = QWebEngineView()
        layout.addWidget(self.webview)

        self.load_fontawesome_map()

    def load_fontawesome_map(self):
        """加载使用Font Awesome图标的地图"""
        m = folium.Map(
            location=[23.1291, 113.2644],  # 广州
            zoom_start=12,
            # tiles='OpenStreetMap'
        )

        # Font Awesome 三角形图标
        fa_triangles = [
            ('play', '#FF0000', '播放三角形'),
            ('caret-up', '#00FF00', '向上三角形'),
            ('caret-down', '#0000FF', '向下三角形'),
            ('caret-left', '#FFA500', '向左三角形'),
            ('caret-right', '#800080', '向右三角形'),
            ('exclamation-triangle', '#FF1493', '警告三角形'),
            ('location-arrow', '#00FFFF', '方向三角形')
        ]

        # 广州的坐标
        base_lat, base_lng = 23.1291, 113.2644

        for i, (icon_name, color, title) in enumerate(fa_triangles):
            lat = base_lat + (i - 3) * 0.03
            lng = base_lng + (i - 3) * 0.03

            # 创建Font Awesome图标
            fa_html = f'''
            <div style="
                font-size: 24px;
                color: {color};
                text-shadow: 2px 2px 4px rgba(0,0,0,0.3);
                background: white;
                border-radius: 50%;
                width: 30px;
                height: 30px;
                display: flex;
                align-items: center;
                justify-content: center;
            ">
                <i class="fas fa-{icon_name}"></i>
            </div>
            '''

            icon = DivIcon(
                icon_size=(30, 30),
                icon_anchor=(15, 15),
                html=fa_html,

            )

            folium.Marker(
                location=[lat, lng],
                popup=f'<b>{title}</b><br>图标: fa-{icon_name}',
                icon=icon
            ).add_to(m)

        # 获取HTML并添加Font Awesome链接
        html = m.get_root().render()

        # 添加Font Awesome和自定义样式
        head_content = '''
        <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.3/css/all.min.css">
        <style>
        .leaflet-control-attribution {
            display: none !important;
        }

        .fa-marker {
            background: transparent;
            border: none;
        }
        </style>
        '''

        html = html.replace('</head>', head_content + '</head>')
        self.webview.setHtml(html)


def main():
    app = QApplication(sys.argv)
    window = FontAwesomeMap()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()