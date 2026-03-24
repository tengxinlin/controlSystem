import os
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QVBoxLayout, QSizePolicy
from mainwindow import Ui_MainWindow  # 导入转换后的UI类
from FoliumMapWidget import FoliumMapWidget
class MainWindow(QMainWindow, Ui_MainWindow):
    def __init__(self):
        super().__init__()
        self.setupUi(self)  # 加载 UI 界面
        # 获取屏幕尺寸
        screen = QApplication.primaryScreen()
        screen_size = screen.availableGeometry()  # 或 screen.size()
        width = int(screen_size.width() * 0.95)
        height = int(screen_size.height() *0.95)
        self.resize(width, height)
        # 可选：将窗口移动到屏幕中央
        # self.move(
        #     (screen_size.width() - width) // 2,
        #     (screen_size.height() - height) // 2
        # )
        # 你可以通过 self.map_frame 访问它
        frame = self.frame_map

        # 检查 frame 是否已有布局，若无则创建一个垂直布局
        if frame.layout() is None:
            layout = QVBoxLayout(frame)
        else:
            layout = frame.layout()

        # 创建自定义地图控件
        self.map_widget = FoliumMapWidget()

        # 将地图控件添加到 frame 的布局中
        layout.addWidget(self.map_widget)

        # 可选：设置地图控件的尺寸策略，使其随 frame 自动调整
        self.map_widget.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)


if __name__ == "__main__":
    app = QApplication(sys.argv)
    # 在程序入口（创建 QApplication 后）添加：
    os.environ['QTWEBENGINE_REMOTE_DEBUGGING'] = '9222'
    window = MainWindow()
    window.show()          # 显示窗口
    sys.exit(app.exec_())  # 进入事件循环