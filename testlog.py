# test_pyqt.py
import sys
from PyQt5.QtWidgets import QApplication, QMainWindow, QLabel, QPushButton, QVBoxLayout, QWidget
from PyQt5.QtCore import Qt, QTimer


def test_basic_window():
    """测试最基本的窗口显示"""
    print("=" * 50)
    print("测试最基本的窗口显示")
    print("=" * 50)

    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)

    window = QMainWindow()
    window.setWindowTitle("基本测试窗口")
    window.resize(300, 200)

    # 设置背景色
    window.setStyleSheet("background-color: green;")

    central = QWidget()
    window.setCentralWidget(central)

    layout = QVBoxLayout(central)
    label = QLabel("这是一个基本测试窗口")
    label.setAlignment(Qt.AlignCenter)
    layout.addWidget(label)

    print(f"显示前 - 可见: {window.isVisible()}")
    window.show()
    print(f"显示后 - 可见: {window.isVisible()}")
    print(f"窗口几何: {window.geometry()}")

    return window


def test_with_event_loop():
    """在事件循环中测试"""
    app = QApplication(sys.argv)

    print("创建窗口...")
    window = test_basic_window()

    print("进入事件循环...")
    # 使用定时器延迟退出，让我们能看到窗口
    QTimer.singleShot(3000, app.quit)

    return app.exec_()


if __name__ == '__main__':
    print("开始测试...")

    # 方法1: 直接测试（可能看不到窗口，因为程序立即结束）
    # window = test_basic_window()

    # 方法2: 带事件循环测试
    exit_code = test_with_event_loop()
    print(f"测试结束，退出代码: {exit_code}")