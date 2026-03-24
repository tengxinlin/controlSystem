import sys
import random
import folium
from folium.features import DivIcon
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QWidget, QComboBox, QLabel
from PyQt5.QtWebEngineWidgets import QWebEngineView


class SVGMarkerMap(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('SVG三角形标记')
        self.setGeometry(100, 100, 1000, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        # 控制面板
        control_panel = QWidget()
        control_layout = QVBoxLayout(control_panel)

        # 三角形类型选择
        self.triangle_type = QComboBox()
        self.triangle_type.addItems([
            '实心三角形',
            '空心三角形',
            '带边框三角形',
            '渐变三角形',
            '3D三角形',
            '箭头三角形'
        ])

        control_layout.addWidget(QLabel('选择三角形类型:'))
        control_layout.addWidget(self.triangle_type)

        layout.addWidget(control_panel)

        # 地图
        self.webview = QWebEngineView()
        layout.addWidget(self.webview, 1)

        # 加载地图
        self.load_svg_markers()

    def create_svg_triangle(self, color='red', style='solid'):
        """创建SVG三角形

        参数:
            color: 颜色
            style: 样式 ('solid', 'hollow', 'border', 'gradient', '3d', 'arrow')
        """
        if style == 'solid':
            svg = f'''
            <svg width="30" height="30" viewBox="0 0 30 30">
                <polygon points="15,5 25,25 5,25" fill="{color}" stroke="white" stroke-width="2"/>
            </svg>
            '''
        elif style == 'hollow':
            svg = f'''
            <svg width="30" height="30" viewBox="0 0 30 30">
                <polygon points="15,5 25,25 5,25" fill="transparent" stroke="{color}" stroke-width="3"/>
            </svg>
            '''
        elif style == 'border':
            svg = f'''
            <svg width="30" height="30" viewBox="0 0 30 30">
                <polygon points="15,5 25,25 5,25" fill="{color}" stroke="#333" stroke-width="2"/>
                <polygon points="15,8 22,23 8,23" fill="white" fill-opacity="0.3"/>
            </svg>
            '''
        elif style == 'gradient':
            svg = f'''
            <svg width="30" height="30" viewBox="0 0 30 30">
                <defs>
                    <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="100%">
                        <stop offset="0%" style="stop-color:{color};stop-opacity:1" />
                        <stop offset="100%" style="stop-color:#000000;stop-opacity:0.7" />
                    </linearGradient>
                </defs>
                <polygon points="15,5 25,25 5,25" fill="url(#grad1)" stroke="white" stroke-width="1.5"/>
            </svg>
            '''
        elif style == '3d':
            svg = f'''
            <svg width="30" height="30" viewBox="0 0 30 30">
                <!-- 3D效果 -->
                <polygon points="15,5 25,25 5,25" fill="{color}" stroke="#333" stroke-width="1"/>
                <polygon points="15,7 23,23 7,23" fill="{color}" fill-opacity="0.7"/>
                <polygon points="15,9 21,21 9,21" fill="{color}" fill-opacity="0.5"/>
            </svg>
            '''
        elif style == 'arrow':
            svg = f'''
            <svg width="30" height="30" viewBox="0 0 30 30">
                <!-- 箭头三角形 -->
                <polygon points="15,5 25,15 20,25 10,25 5,15" fill="{color}" stroke="white" stroke-width="2"/>
                <line x1="15" y1="10" x2="15" y2="20" stroke="white" stroke-width="2"/>
                <line x1="12" y1="17" x2="15" y2="20" stroke="white" stroke-width="2"/>
                <line x1="18" y1="17" x2="15" y2="20" stroke="white" stroke-width="2"/>
            </svg>
            '''

        return svg

    def load_svg_markers(self):
        """加载带SVG三角形标记的地图"""
        m = folium.Map(
            location=[39.9042, 116.4074],  # 北京
            zoom_start=11,
            tiles='OpenStreetMap'
        )

        # 添加不同类型的三角形标记
        locations = [
            (39.9042, 116.4074, '实心三角形', 'solid', '#FF0000'),
            (39.9169, 116.3907, '空心三角形', 'hollow', '#00FF00'),
            (39.9621, 116.3660, '带边框三角形', 'border', '#0000FF'),
            (39.9998, 116.3264, '渐变三角形', 'gradient', '#FFA500'),
            (40.0021, 116.4684, '3D三角形', '3d', '#800080'),
            (39.8621, 116.4534, '箭头三角形', 'arrow', '#FF1493')
        ]

        for lat, lng, title, style, color in locations:
            svg_html = self.create_svg_triangle(color, style)

            icon = DivIcon(
                icon_size=(30, 30),
                icon_anchor=(15, 15),
                html=svg_html,

            )

            folium.Marker(
                location=[lat, lng],
                popup=title,
                icon=icon
            ).add_to(m)

            # 添加说明标签
            folium.map.Marker(
                [lat + 0.005, lng],
                icon=DivIcon(
                    icon_size=(150, 20),
                    icon_anchor=(75, 0),
                    html=f'<div style="font-size: 12px; color: #333;">{title}</div>'
                )
            ).add_to(m)

        # 获取HTML
        html = m.get_root().render()

        # 添加CSS
        css = '''
        <style>
        .leaflet-control-attribution {
            display: none !important;
        }

        /* SVG标记样式 */
        .svg-marker {
            background: transparent;
            border: none;
        }
        </style>
        '''

        html = html.replace('</head>', css + '</head>')
        self.webview.setHtml(html)


def main():
    app = QApplication(sys.argv)
    window = SVGMarkerMap()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()