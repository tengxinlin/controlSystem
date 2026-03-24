import sys
import random
from PyQt5.QtWidgets import *
from PyQt5.QtWebEngineWidgets import QWebEngineView
import folium
from folium.features import DivIcon


class SVGTriangleApp(QMainWindow):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        self.setWindowTitle('SVG三角形标记')
        self.setGeometry(100, 100, 1000, 700)

        central_widget = QWidget()
        self.setCentralWidget(central_widget)
        layout = QVBoxLayout(central_widget)

        self.webview = QWebEngineView()
        layout.addWidget(self.webview)

        self.load_svg_triangle_map()

    def create_svg_triangle(self, fill_color, stroke_color, stroke_width, rotation):
        """创建SVG三角形"""
        svg = f'''
        <svg width="40" height="40" viewBox="0 0 40 40">
            <defs>
                <linearGradient id="grad1" x1="0%" y1="0%" x2="100%" y2="100%">
                    <stop offset="0%" style="stop-color:{fill_color};stop-opacity:1" />
                    <stop offset="100%" style="stop-color:{self.darken_color(fill_color)};stop-opacity:1" />
                </linearGradient>
            </defs>
            <g transform="rotate({rotation}, 20, 20)">
                <polygon 
                    points="20,5 35,35 5,35" 
                    fill="url(#grad1)" 
                    stroke="{stroke_color}" 
                    stroke-width="{stroke_width}"
                    style="filter: drop-shadow(2px 2px 4px rgba(0,0,0,0.3));"
                />
                <polygon 
                    points="20,10 32,33 8,33" 
                    fill="{fill_color}" 
                    opacity="0.7"
                />
            </g>
        </svg>
        '''
        return svg

    def darken_color(self, hex_color, factor=0.7):
        """使颜色变暗"""
        hex_color = hex_color.lstrip('#')
        r, g, b = tuple(int(hex_color[i:i + 2], 16) for i in (0, 2, 4))
        r = int(r * factor)
        g = int(g * factor)
        b = int(b * factor)
        return f'#{r:02x}{g:02x}{b:02x}'

    def load_svg_triangle_map(self):
        """加载带有SVG三角形的地图"""
        m = folium.Map(
            location=[31.2304, 121.4737],  # 上海
            zoom_start=12,
            tiles='OpenStreetMap',
            control_scale=True
        )

        # 添加不同类型的三角形标记
        triangle_styles = [
            {
                'location': [31.2304, 121.4737],
                'title': '红色三角形',
                'fill': '#FF0000',
                'stroke': '#8B0000',
                'width': 2,
                'rotation': 0
            },
            {
                'location': [31.2359, 121.5067],
                'title': '蓝色三角形',
                'fill': '#0000FF',
                'stroke': '#00008B',
                'width': 3,
                'rotation': 60
            },
            {
                'location': [31.2215, 121.4405],
                'title': '绿色三角形',
                'fill': '#00FF00',
                'stroke': '#006400',
                'width': 1,
                'rotation': 120
            },
            {
                'location': [31.2156, 121.4928],
                'title': '紫色三角形',
                'fill': '#800080',
                'stroke': '#4B0082',
                'width': 4,
                'rotation': 180
            },
            {
                'location': [31.2250, 121.5250],
                'title': '橙色三角形',
                'fill': '#FFA500',
                'stroke': '#FF8C00',
                'width': 2,
                'rotation': 240
            },
            {
                'location': [31.2050, 121.4750],
                'title': '青色三角形',
                'fill': '#00FFFF',
                'stroke': '#008B8B',
                'width': 3,
                'rotation': 300
            }
        ]

        for style in triangle_styles:
            svg_html = self.create_svg_triangle(
                style['fill'],
                style['stroke'],
                style['width'],
                style['rotation']
            )

            svg_icon = DivIcon(
                icon_size=(40, 40),
                icon_anchor=(20, 20),
                html=svg_html
            )

            folium.Marker(
                location=style['location'],
                popup=f'''
                <b>{style['title']}</b><br>
                颜色: {style['fill']}<br>
                旋转: {style['rotation']}°
                ''',
                icon=svg_icon
            ).add_to(m)

        # 添加说明标记
        folium.Marker(
            [31.2400, 121.4900],
            popup='''
            <div style="width:200px">
                <h4>三角形标记说明</h4>
                <ul>
                    <li>不同颜色代表不同类型</li>
                    <li>旋转角度指示方向</li>
                    <li>边框粗细表示重要程度</li>
                    <li>支持渐变填充效果</li>
                </ul>
            </div>
            ''',
            icon=folium.Icon(color='black', icon='info-sign')
        ).add_to(m)

        # 获取HTML
        html = m.get_root().render()

        # 添加自定义样式
        css = '''
        <style>
        .leaflet-control-attribution {
            display: none !important;
        }
        .leaflet-popup-content {
            font-family: Arial, sans-serif;
        }
        </style>
        '''

        html = html.replace('</head>', css + '</head>')
        self.webview.setHtml(html)


def main():
    app = QApplication(sys.argv)
    window = SVGTriangleApp()
    window.show()
    sys.exit(app.exec_())


if __name__ == '__main__':
    main()