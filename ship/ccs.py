import folium
from folium.features import DivIcon


def create_css_triangle_marker():
    """创建使用纯CSS的三角形标记"""

    m = folium.Map(
        location=[40.7128, -74.0060],  # 纽约
        zoom_start=12,
        tiles='OpenStreetMap'
    )

    # CSS三角形样式
    triangle_styles = [
        {
            'name': '普通三角形',
            'css': '''
            width: 0;
            height: 0;
            border-left: 15px solid transparent;
            border-right: 15px solid transparent;
            border-bottom: 30px solid #FF0000;
            '''
        },
        {
            'name': '圆角三角形',
            'css': '''
            width: 30px;
            height: 30px;
            background: #00FF00;
            clip-path: polygon(50% 0%, 0% 100%, 100% 100%);
            border-radius: 5px;
            '''
        },
        {
            'name': '等腰三角形',
            'css': '''
            width: 30px;
            height: 30px;
            background: #0000FF;
            clip-path: polygon(50% 0%, 0% 100%, 100% 100%);
            transform: rotate(45deg);
            '''
        },
        {
            'name': '直角三角形',
            'css': '''
            width: 0;
            height: 0;
            border-bottom: 30px solid #FFA500;
            border-left: 30px solid transparent;
            '''
        },
        {
            'name': '双层三角形',
            'css': '''
            position: relative;
            width: 30px;
            height: 30px;
            background: #800080;
            clip-path: polygon(50% 0%, 0% 100%, 100% 100%);
            '''
                   + '''
            ::after {
                content: '';
                position: absolute;
                top: 5px;
                left: 5px;
                width: 20px;
                height: 20px;
                background: white;
                clip-path: polygon(50% 0%, 0% 100%, 100% 100%);
            }
            '''
        }
    ]

    # 纽约的坐标
    base_lat, base_lng = 40.7128, -74.0060

    for i, style in enumerate(triangle_styles):
        lat = base_lat + (i - 2) * 0.02
        lng = base_lng + (i - 2) * 0.02

        html = f'''
        <div style="
            {style['css']}
            filter: drop-shadow(0 3px 6px rgba(0,0,0,0.2));
        "></div>
        '''

        icon = DivIcon(
            icon_size=(30, 30),
            icon_anchor=(15, 15),
            html=html
        )

        folium.Marker(
            location=[lat, lng],
            popup=style['name'],
            icon=icon
        ).add_to(m)

    return m


# 使用示例
if __name__ == '__main__':
    from PyQt5.QtWidgets import QApplication, QMainWindow
    from PyQt5.QtWebEngineWidgets import QWebEngineView

    app = QApplication([])

    # 创建地图
    m = create_css_triangle_marker()

    # 显示在PyQt中
    html = m.get_root().render()
    html = html.replace('</head>', '<style>.leaflet-control-attribution {display:none;}</style></head>')

    window = QMainWindow()
    webview = QWebEngineView()
    webview.setHtml(html)

    window.setCentralWidget(webview)
    window.setWindowTitle('CSS三角形标记')
    window.setGeometry(100, 100, 800, 600)
    window.show()

    app.exec_()