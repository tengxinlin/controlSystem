# led_widget.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QComboBox
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap
import os


class LEDWidget(QWidget):
    """单个LED灯控制控件"""

    # 状态图片映射
    STATUS_IMAGES = {
        0: "led_forbidden.png",  # 禁航
        1: "led_up.png",  # 上水
        2: "led_down.png",  # 下水
        3: "led_half.gif",  # 半杆
        4: "led_off.png"  # 关闭
    }

    def __init__(self, led_info, led_manager, parent=None):
        super().__init__(parent)
        self.led_info = led_info
        self.led_manager = led_manager
        self.setFixedSize(120, 150)
        self.setVisible(True)  # 确保可见
        self.init_ui()
        print(f"LEDWidget 创建: {led_info.led_name}, 可见: {self.isVisible()}")

    def init_ui(self):
        """初始化UI"""
        layout = QVBoxLayout(self)
        layout.setAlignment(Qt.AlignCenter)
        layout.setSpacing(5)

        # LED名称
        self.name_label = QLabel(self.led_info.led_name)
        self.name_label.setAlignment(Qt.AlignCenter)
        self.name_label.setStyleSheet("font-size: 14px; font-weight: bold; color: #333;")
        layout.addWidget(self.name_label)

        # LED状态图片
        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setFixedSize(50, 50)
        layout.addWidget(self.status_label)

        # 状态文字
        self.status_text = QLabel("关闭")
        self.status_text.setAlignment(Qt.AlignCenter)
        self.status_text.setStyleSheet("font-size: 12px; color: #666;")
        layout.addWidget(self.status_text)

        # 控制按钮
        control_layout = QHBoxLayout()

        self.status_combo = QComboBox()
        self.status_combo.addItems(["禁航", "上水", "下水", "半杆", "关闭"])
        self.status_combo.setCurrentIndex(4)  # 默认关闭
        control_layout.addWidget(self.status_combo)

        self.send_btn = QPushButton("发送")
        self.send_btn.clicked.connect(self.send_control)
        control_layout.addWidget(self.send_btn)

        layout.addLayout(control_layout)

        # 设置边距
        layout.setContentsMargins(10, 10, 10, 10)
        self.setStyleSheet("""
            LEDWidget {
                background-color: #f8f9fa;
                border-radius: 8px;
                border: 1px solid #dee2e6;
            }
            LEDWidget:hover {
                background-color: #e9ecef;
            }
        """)

        # 更新显示
        self.update_status_display(self.led_info.status)

    def update_status_display(self, status: int):
        """更新状态显示"""
        # 更新图片
        image_name = self.STATUS_IMAGES.get(status, "led_off.png")
        image_path = self.get_image_path(image_name)

        if os.path.exists(image_path):
            pixmap = QPixmap(image_path)
            scaled_pixmap = pixmap.scaled(40, 40, Qt.KeepAspectRatio, Qt.SmoothTransformation)
            self.status_label.setPixmap(scaled_pixmap)
        else:
            # 如果没有图片，用颜色块代替
            colors = {0: "#ff0000", 1: "#00ff00", 2: "#0000ff", 3: "#ffff00", 4: "#cccccc"}
            color = colors.get(status, "#cccccc")
            self.status_label.setStyleSheet(f"""
                background-color: {color};
                border-radius: 20px;
                min-width: 40px;
                min-height: 40px;
            """)

        # 更新状态文字
        status_texts = {0: "禁航", 1: "上水", 2: "下水", 3: "半杆", 4: "关闭"}
        self.status_text.setText(status_texts.get(status, "未知"))
        self.status_combo.setCurrentIndex(status)

    def send_control(self):
        """发送控制命令"""
        status = self.status_combo.currentIndex()
        self.led_manager.control_led(self.led_info.led_id, status)

    def get_image_path(self, image_name: str) -> str:
        """获取图片路径"""
        # 可以修改为你的图片存放路径
        return os.path.join("", "", image_name)