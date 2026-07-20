# led_widget.py
from PyQt5.QtWidgets import QWidget, QVBoxLayout, QLabel, QPushButton, QHBoxLayout, QComboBox, QSizePolicy
from PyQt5.QtCore import Qt, QSize
from PyQt5.QtGui import QPixmap
import os

from PyQt5.QtGui import QMovie

from led_manager import LEDInfo


class LEDWidget(QWidget):
    """单个LED灯控制控件"""

    # 状态图片映射
    STATUS_IMAGES = {
        0: "led_forbidden.png",  # 禁航
        1: "led_up.png",  # 上水
        2: "led_down.png",  # 下水
        3: "led_half.gif",  # 半杆（GIF动图）
        4: "led_off.png"  # 关闭
    }

    def __init__(self, led_info, led_manager, parent=None):
        super().__init__(parent)
        # 存储动画对象
        self.movie = None
        self.led_info = led_info
        self.led_manager = led_manager
        self.setFixedHeight(100)
        self.setMinimumWidth(280)
        self.setVisible(True)



        self.init_ui()
        # 保存初始状态，等显示后再更新
        self.initial_status = self.led_info.status

        # 连接信号
        self.led_manager.led_connection_changed.connect(self.on_connection_changed)
        self.led_manager.led_status_changed.connect(self.on_status_changed)

        print(f"LEDWidget 创建: {led_info.led_name}, 可见: {self.isVisible()}")

    def init_ui(self):
        """初始化UI - 两列布局"""
        # 主布局使用水平布局
        main_layout = QHBoxLayout(self)
        main_layout.setContentsMargins(10, 5, 10, 5)
        main_layout.setSpacing(15)

        # ========== 第一列：LED状态图标（充满整个列空间）==========
        icon_container = QWidget()
        icon_layout = QVBoxLayout(icon_container)
        icon_layout.setAlignment(Qt.AlignCenter)
        icon_layout.setContentsMargins(0, 0, 0, 0)

        self.status_label = QLabel()
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setMinimumSize(70, 70)
        self.status_label.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)

        icon_layout.addWidget(self.status_label)

        # 设置第一列的固定宽度
        icon_container.setFixedWidth(90)
        icon_container.setStyleSheet("background-color: transparent;")

        # ========== 第二列：LED名称、控制下拉框、发送按钮（垂直排列）==========
        control_container = QWidget()
        control_layout = QVBoxLayout(control_container)
        control_layout.setAlignment(Qt.AlignVCenter)
        control_layout.setContentsMargins(0, 0, 0, 0)
        control_layout.setSpacing(8)

        # 1. LED名称
        self.name_label = QLabel(self.led_info.led_name)
        self.name_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.name_label.setStyleSheet("""
            font-size: 14px; 
            font-weight: bold; 
            color: #2c3e50;
        """)

        # 更新名称颜色（根据当前连接状态）
        self.update_name_color()

        self.name_label.setMinimumHeight(25)
        control_layout.addWidget(self.name_label)

        # 连接状态显示（小标签）
        self.connection_label = QLabel()
        self.connection_label.setAlignment(Qt.AlignLeft | Qt.AlignVCenter)
        self.connection_label.setStyleSheet("font-size: 10px; color: #7f8c8d;")
        self.update_connection_label()
        control_layout.addWidget(self.connection_label)

        # 2. 控制下拉框
        self.status_combo = QComboBox()
        self.status_combo.addItems(["禁航", "上水", "下水", "半杆", "关闭"])
        self.status_combo.setCurrentIndex(4)
        self.status_combo.setFixedHeight(32)
        self.status_combo.setMinimumWidth(100)
        self.status_combo.setStyleSheet("""
            QComboBox {
                padding: 5px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                font-size: 13px;
                background-color: white;
            }
            QComboBox:hover {
                border-color: #3498db;
            }
            QComboBox::drop-down {
                border: none;
            }
        """)
        control_layout.addWidget(self.status_combo)

        # 3. 发送按钮
        self.send_btn = QPushButton("发送")
        self.send_btn.setFixedHeight(32)
        self.send_btn.setFixedWidth(60)
        self.send_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                font-size: 13px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
            QPushButton:pressed {
                background-color: #1c6ea4;
            }
        """)
        self.send_btn.clicked.connect(self.send_control)
        control_layout.addWidget(self.send_btn)

        # 添加弹性空间，让控件在垂直方向上居中
        control_layout.addStretch()

        self.status_combo.setVisible(False)
        self.send_btn.setVisible(False)
        
        # 添加到主布局
        main_layout.addWidget(icon_container)
        main_layout.addWidget(control_container, 1)

        # 设置整体样式
        self.setStyleSheet("""
            LEDWidget {
                background-color: #f8f9fa;
                border-radius: 8px;
                border: 1px solid #dee2e6;
            }
            LEDWidget:hover {
                background-color: #e9ecef;
                border-color: #3498db;
            }
        """)

        # 更新显示
        self.update_status_display(self.led_info.status)
        # self.update_connection_display(self.led_info)

    def update_name_color(self):
        """根据连接状态更新名称颜色"""
        color = self.led_info.get_connection_color()
        # 根据颜色选择文字颜色
        self.name_label.setStyleSheet(f"""
            font-size: 14px; 
            font-weight: bold; 
            color: {color};
        """)

    def update_connection_label(self):
        """更新连接状态标签"""
        status = self.led_info.get_connection_status()
        color = self.led_info.get_connection_color()
        self.connection_label.setText(f"连接: {status}")
        self.connection_label.setStyleSheet(f"""
            font-size: 10px; 
            color: {color};
            font-weight: bold;
        """)

    def update_connection_display(self, led_info: LEDInfo):
        """更新连接状态显示"""
        status_text = led_info.get_connection_status()
        color = led_info.get_connection_color()

        # 更新名称颜色
        if led_info.mqtt_connected and led_info.lora_connected:
            self.name_label.setStyleSheet("""
                font-size: 14px; 
                font-weight: bold; 
                color: #27ae60;
            """)
            #self.status_text.setText(f"{status_text} - {led_info.get_status_text()}")
        elif led_info.mqtt_connected:
            self.name_label.setStyleSheet("""
                font-size: 14px; 
                font-weight: bold; 
                color: #3498db;
            """)
            #self.status_text.setText(f"MQTT - {led_info.get_status_text()}")
        elif led_info.lora_connected:
            self.name_label.setStyleSheet("""
                font-size: 14px; 
                font-weight: bold; 
                color: #2ecc71;
            """)
            #self.status_text.setText(f"LoRa - {led_info.get_status_text()}")
        else:
            self.name_label.setStyleSheet("""
                font-size: 14px; 
                font-weight: bold; 
                color: #e74c3c;
                background-color: #ffebee;
                border-radius: 4px;
                padding: 2px 5px;
            """)
            #self.status_text.setText("断开连接")
            #self.status_text.setStyleSheet("font-size: 12px; color: #e74c3c; font-weight: bold;")

    def update_connection_status(self, connected: bool):
        """更新LED连接状态显示"""
        if connected:
            # 恢复正常样式
            self.name_label.setStyleSheet("""
                   font-size: 14px; 
                   font-weight: bold; 
                   color: #2c3e50;
               """)
            self.setStyleSheet("""
                   LEDWidget {
                       background-color: #f8f9fa;
                       border-radius: 8px;
                       border: 1px solid #dee2e6;
                   }
               """)
        else:
            # 断开连接：红色凸显
            self.name_label.setStyleSheet("""
                   font-size: 14px; 
                   font-weight: bold; 
                   color: #e74c3c;
                   background-color: #ffebee;
                   border-radius: 4px;
                   padding: 2px 5px;
               """)
            # 状态显示为"断开"
            self.status_label.setText("断开")
            self.status_label.setStyleSheet("font-size: 12px; color: #e74c3c; font-weight: bold;")

    def on_connection_changed(self, led_id: str, connection_status: str):
        """连接状态变化回调"""
        if led_id == self.led_info.led_id:
            self.update_name_color()
            self.update_connection_label()
            print(f"🔗 LED {self.led_info.led_name} 连接状态: {connection_status}")

    def on_status_changed(self, led_id: str, status: int):
        """状态变化回调"""
        if led_id == self.led_info.led_id:
            self.update_status_display(status)

    def update_status_display(self, status: int):
        """更新状态显示"""
        # 停止当前正在播放的动画
        if self.movie:
            self.movie.stop()
            self.movie.deleteLater()
            self.movie = None

        # 获取状态对应的图片文件名
        image_name = self.STATUS_IMAGES.get(status, "led_off.png")
        image_path = self.get_image_path(image_name)

        # 清除样式和内容
        self.status_label.setStyleSheet("")
        self.status_label.setText("")
        self.status_label.setPixmap(QPixmap())  # 清除之前的图片

        if os.path.exists(image_path):
            # 判断是否为 GIF 文件
            if image_name.lower().endswith('.gif'):
                # 使用 QMovie 播放 GIF 动画
                self.movie = QMovie(image_path)

                # 获取标签的实际大小
                label_width = self.status_label.width()
                label_height = self.status_label.height()

                # 如果标签大小为0，使用默认大小
                if label_width <= 0:
                    label_width = 70
                if label_height <= 0:
                    label_height = 70

                # 设置缩放大小，使 GIF 完全填充标签
                self.movie.setScaledSize(QSize(label_width, label_height))

                # 设置缓存模式，使动画更流畅
                self.movie.setCacheMode(QMovie.CacheAll)

                # 设置到 QLabel
                self.status_label.setMovie(self.movie)

                # 开始播放
                self.movie.start()

                print(f"GIF动画已启动: {image_name}, 大小: {label_width}x{label_height}")
            else:
                # 普通图片，使用 QPixmap
                pixmap = QPixmap(image_path)
                # 缩放图片以适应标签，保持比例并完全填充
                scaled_pixmap = pixmap.scaled(
                    self.status_label.width(),
                    self.status_label.height(),
                    Qt.KeepAspectRatio,
                    Qt.SmoothTransformation
                )
                self.status_label.setPixmap(scaled_pixmap)
        else:
            # 如果没有图片，用颜色块代替
            colors = {0: "#ff0000", 1: "#00ff00", 2: "#0000ff", 3: "#ffff00", 4: "#95a5a6"}
            color = colors.get(status, "#95a5a6")
            status_texts = {0: "禁航", 1: "上水", 2: "下水", 3: "半杆", 4: "关闭"}

            self.status_label.setStyleSheet(f"""
                background-color: {color};
                border-radius: 8px;
                min-width: 70px;
                min-height: 70px;
                font-size: 12px;
                color: white;
            """)
            self.status_label.setAlignment(Qt.AlignCenter)
            self.status_label.setText(status_texts.get(status, "关闭"))

        self.status_combo.setCurrentIndex(status)

    def showEvent(self, event):
        """窗口显示时调用，确保布局已稳定"""
        super().showEvent(event)
        # 延迟更新，确保布局已完成
        from PyQt5.QtCore import QTimer
        QTimer.singleShot(100, self.update_after_show)

    def update_after_show(self):
        """显示后更新状态（此时布局已稳定）"""
        if self.initial_status is not None:
            self.update_status_display(self.initial_status)
            self.initial_status = None

    def resizeEvent(self, event):
        """窗口大小改变时重新调整动画大小"""
        super().resizeEvent(event)

        # 如果有动画正在播放，重新设置缩放大小
        if self.movie and self.movie.isValid():
            label_width = self.status_label.width()
            label_height = self.status_label.height()

            if label_width > 0 and label_height > 0:
                self.movie.setScaledSize(QSize(label_width, label_height))
                print(f"GIF动画大小已调整: {label_width}x{label_height}")

    def send_control(self):
        """发送控制命令"""
        status = self.status_combo.currentIndex()
        self.led_manager.control_led(self.led_info.led_id, status)

    def get_image_path(self, image_name: str) -> str:
        """获取图片路径"""
        # 尝试多个可能的路径
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "images", "led", image_name),
            os.path.join("images", "led", image_name),
            os.path.join("", "", image_name),
        ]

        for path in possible_paths:
            if os.path.exists(path):
                return path

        return ""