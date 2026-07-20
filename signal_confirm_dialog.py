# signal_confirm_dialog.py
from PyQt5.QtWidgets import QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton, QProgressBar
from PyQt5.QtCore import Qt, QTimer, pyqtSignal
from PyQt5.QtGui import QFont


class SignalConfirmDialog(QDialog):
    """信号揭示确认对话框（带自动倒数计时）"""

    # 信号
    confirmed = pyqtSignal(str,str)  # 用户确认,带着mmsi信息，以及信号类型
    cancelled = pyqtSignal()  # 用户取消
    timeout = pyqtSignal(str)  # 倒计时结束

    def __init__(self,mmsi:str, ship_name: str, signal_type: str, timeout_seconds: int = 10, parent=None):
        """
        初始化对话框

        Args:
            mmsi:船舶mmsi
            ship_name: 船舶名称
            signal_type: 信号类型 ('上水', '下水', '半杆','关闭'，'禁航')
            timeout_seconds: 倒计时秒数
            parent: 父窗口
        """
        super().__init__(parent)
        self.mmsi = mmsi
        self.ship_name = ship_name
        self.signal_type = signal_type
        self.timeout_seconds = timeout_seconds
        self.remaining_seconds = timeout_seconds
        self.auto_confirm = True  # 倒计时结束后自动确认

        self.setWindowTitle("信号揭示确认")
        self.setFixedSize(400, 500)
        self.setWindowFlags(Qt.WindowStaysOnTopHint | Qt.Dialog)

        self.init_ui()
        self.start_timer()

    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)

        # 信号类型对应的显示文字和颜色
        signal_info = {
            '上水': {'text': '上水信号', 'color': '#3498db'},
            '下水': {'text': '下水信号', 'color': '#e74c3c'},
            '半杆': {'text': '半杆信号', 'color': '#f39c12'},
            '关闭': {'text': '关闭信号', 'color': '#f39c12'},
            '禁航': {'text': '禁航信号', 'color': '#f39c12'},
        }
        info = signal_info.get(self.signal_type, {'text': '未知信号', 'color': '#95a5a6'})

        # 标题
        title_label = QLabel("⚠️ 信号揭示确认")
        title_font = QFont()
        title_font.setPointSize(16)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setAlignment(Qt.AlignCenter)
        layout.addWidget(title_label)

        # 船舶名称
        ship_label = QLabel(f"船舶: {self.ship_name}")
        ship_label.setAlignment(Qt.AlignCenter)
        ship_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #2c3e50;")
        layout.addWidget(ship_label)

        # 信号类型
        signal_label = QLabel(f"揭示信号: {info['text']}")
        signal_label.setAlignment(Qt.AlignCenter)
        signal_label.setStyleSheet(f"font-size: 14px; color: {info['color']}; font-weight: bold;")
        layout.addWidget(signal_label)

        # 倒计时显示
        self.countdown_label = QLabel(f"倒计时: {self.remaining_seconds} 秒后自动确认")
        self.countdown_label.setAlignment(Qt.AlignCenter)
        self.countdown_label.setStyleSheet("font-size: 12px; color: #7f8c8d;")
        layout.addWidget(self.countdown_label)

        # 进度条
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, self.timeout_seconds)
        self.progress_bar.setValue(self.timeout_seconds)
        self.progress_bar.setTextVisible(False)
        self.progress_bar.setStyleSheet("""
            QProgressBar {
                border: 1px solid #bdc3c7;
                border-radius: 5px;
                height: 8px;
            }
            QProgressBar::chunk {
                background-color: #3498db;
                border-radius: 5px;
            }
        """)
        layout.addWidget(self.progress_bar)

        # 按钮区域
        button_layout = QHBoxLayout()

        self.confirm_btn = QPushButton("确定揭示")
        self.confirm_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
                font-size: 14px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #219a52;
            }
        """)
        self.confirm_btn.clicked.connect(self.on_confirm)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 5px;
                padding: 8px 20px;
                font-size: 14px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        self.cancel_btn.clicked.connect(self.on_cancel)

        button_layout.addWidget(self.confirm_btn)
        button_layout.addWidget(self.cancel_btn)
        layout.addLayout(button_layout)

        # 提示信息
        tip_label = QLabel("提示: 倒计时结束后将自动确认揭示信号")
        tip_label.setAlignment(Qt.AlignCenter)
        tip_label.setStyleSheet("font-size: 11px; color: #95a5a6;")
        layout.addWidget(tip_label)

    def start_timer(self):
        """启动倒计时定时器"""
        self.timer = QTimer(self)
        self.timer.timeout.connect(self.update_countdown)
        self.timer.start(1000)  # 每秒更新一次

    def update_countdown(self):
        """更新倒计时"""
        self.remaining_seconds -= 1
        self.countdown_label.setText(f"倒计时: {self.remaining_seconds} 秒后自动确认")
        self.progress_bar.setValue(self.remaining_seconds)

        if self.remaining_seconds <= 0:
            self.on_timeout(self.mmsi)

    def on_confirm(self):
        """确认按钮点击"""
        self.timer.stop()
        self.confirmed.emit(self.mmsi,self.signal_type)
        self.accept()

    def on_cancel(self):
        """取消按钮点击"""
        self.timer.stop()
        self.cancelled.emit()
        self.reject()

    def on_timeout(self,mmsi):
        """倒计时结束"""
        self.timer.stop()
        if self.auto_confirm:
            self.confirmed.emit(mmsi,self.signal_type)
            self.accept()
        else:
            self.cancelled.emit()
            self.reject()