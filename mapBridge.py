from PyQt5.QtCore import QObject, pyqtSlot, pyqtSignal
from PyQt5.QtWebChannel import QWebChannel
from PyQt5.QtWebEngineWidgets import QWebEngineView


class MapBridge(QObject):
    """地图与Python的桥接类"""
    shipDataChanged = pyqtSignal(str)  # 船舶数据变化信号

    @pyqtSlot(str)
    def onShipDataChanged(self, data_str):
        """接收船舶数据变化"""
        try:

            # 这里可以发射信号让其他模块处理
            self.shipDataChanged.emit(data_str)


        except Exception as e:
            print(f"处理失败: {e}")

    @pyqtSlot(str)
    def log(self, message):
        """接收日志消息"""
        print(f"[JS] {message}")