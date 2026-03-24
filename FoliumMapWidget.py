import os
import sys

from PyQt5.QtCore import QUrl, Qt
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtWidgets import QVBoxLayout, QApplication, QWidget
# 或者禁用硬件加速
os.environ["QT_WEBENGINE_DISABLE_GPU"] = "1"
os.environ["QTWEBENGINE_CHROMIUM_FLAGS"] = "--disable-gpu"

class FoliumMapWidget(QWidget):
    def __init__(self):
        super().__init__()
        self.initUI()

    def initUI(self):
        # 创建布局
        layout = QVBoxLayout()
        # 创建WebEngineView

        self.webView = QWebEngineView()
        layout.addWidget(self.webView)

        # 启用必要的设置
        self.webView.settings().setAttribute(
            self.webView.settings().WebAttribute.LocalContentCanAccessRemoteUrls, True
        )
        self.webView.settings().setAttribute(
            self.webView.settings().WebAttribute.LocalContentCanAccessFileUrls, True
        )
        self.webView.settings().setAttribute(
            self.webView.settings().WebAttribute.AllowWindowActivationFromJavaScript, True
        )

        # 禁用Web安全限制（仅用于本地开发）
        self.webView.settings().setAttribute(
            self.webView.settings().WebAttribute.LocalContentCanAccessFileUrls, True
        )
        self.webView.settings().setAttribute(
            self.webView.settings().WebAttribute.AllowRunningInsecureContent, True
        )

        # 启用JavaScript
        self.webView.settings().setAttribute(self.webView.settings().WebAttribute.JavascriptEnabled, True)
        self.webView.settings().setAttribute(self.webView.settings().WebAttribute.JavascriptCanOpenWindows, True)

        self.setLayout(layout)
        self.loadMap()

    def loadMap(self):
        """加载HTML文件"""

        # 方法1：添加调试信息，确认路径是否正确
        current_dir = os.path.dirname(os.path.abspath(__file__))
        html_path = os.path.join(current_dir, 'map.html')

        print(f"当前目录: {current_dir}")
        print(f"HTML路径: {html_path}")
        print(f"文件是否存在: {os.path.exists(html_path)}")

        if os.path.exists(html_path):
            with open(html_path, 'r', encoding='utf-8') as f:
                print(f"文件内容（前100字符）: {f.read(100)}")
        else:
            print("文件不存在！")
            # 尝试创建测试文件
            test_html = """<!DOCTYPE html>
        <html>
        <head>
            <title>测试页面</title>
            <style>body { font-size: 20px; color: red; }</style>
        </head>
        <body>
            <h1>如果看到这个，说明HTML加载成功！</h1>
        </body>
        </html>"""
            with open(html_path, 'w', encoding='utf-8') as f:
                f.write(test_html)
            print(f"已创建测试文件: {html_path}")

        # 然后加载
        self.webView.load(QUrl.fromLocalFile(html_path))



        # 添加大小检查
        print(f"webView 尺寸: {self.webView.width()} x {self.webView.height()}")
        # #直接加载
        # self.webView.setHtml(m._repr_html_())

        # # 使用 Data URI 加载
        # # 保存到字符串
        # html_content = m.get_root().render()
        # data_uri = "data:text/html;base64," + base64.b64encode(html_content.encode()).decode()
        # self.webView.load(QUrl(data_uri))

        # 连接JavaScript控制台
        self.webView.page().javaScriptConsoleMessage = self.on_js_console

    def on_load_finished(self, ok):
        print(f"页面加载{'成功' if ok else '失败'}")
        if ok:
            print(f"加载完成后 webView 尺寸: {self.webView.width()} x {self.webView.height()}")

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
        self.webView.page().runJavaScript(js_code)

    def remove_ship(self, ship_id):
        """移除船舶"""
        js_code = f'''
                if (typeof removeShip === 'function') {{
                    removeShip("{ship_id}");
                }}
                '''
        self.webView.page().runJavaScript(js_code)

    def clear_all_ships(self):
        """清除所有船舶"""
        js_code = '''
                if (typeof clearAllShips === 'function') {
                    clearAllShips();
                }
                '''
        self.webView.page().runJavaScript(js_code)

    def closeEvent(self, event):
        # 清理临时文件
        if hasattr(self, 'temp_file_path'):
            try:
                os.unlink(self.temp_file_path)
            except:
                pass
        event.accept()

if __name__ == '__main__':
    app = QApplication(sys.argv)
    # 在程序入口（创建 QApplication 后）添加：
    os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = '9222'
    QApplication.setAttribute(Qt.AA_EnableHighDpiScaling, True)
    window = FoliumMapWidget()
    window.show()
    sys.exit(app.exec())