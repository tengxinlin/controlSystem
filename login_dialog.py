# login_dialog.py
import os
import sys
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QCheckBox, QPushButton, QMessageBox,
                             QApplication, QFrame, QWidget, QRadioButton)
from PyQt5.QtCore import Qt, pyqtSignal, QThread
from PyQt5.QtGui import QFont, QPixmap, QPalette, QColor, QIcon
from config import ConfigManager
from APIManager import APIService


class LoginThread(QThread):
    """登录线程"""
    # 定义信号
    login_finished = pyqtSignal(bool)  # 登录完成信号
    login_error = pyqtSignal(str)  # 错误信号

    def __init__(self, api_service, username, password):
        super().__init__()
        self.api_service = api_service
        self.username = username
        self.password = password

    def run(self):
        """线程运行函数"""
        try:
            # 在子线程中执行耗时操作
            success = self.api_service.login(self.username, self.password)
            # 通过信号返回结果
            self.login_finished.emit(success)
        except Exception as e:
            self.login_error.emit(str(e))

class LoginDialog(QDialog):
    # 定义登录成功信号，可以传递用户名
    login_success = pyqtSignal(object, str,str)  # 传递APIService实例和用户名和网络类型

    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置为模态对话框
        self.setModal(True)
        self.config_mgr = ConfigManager()

        # 从配置文件读取网络配置
        self.network_config = self._load_network_config()

        # 默认使用内网IP
        default_ip = self.network_config.get('external', {}).get('ip', '')
        self.api_service = APIService(default_ip)

        self.selected_network = 'external'  # 默认外网
        self.password_visible = False  # 密码是否可见

        self.init_ui()
        self.load_saved_credentials()

    def _load_network_config(self):
        """从配置文件加载网络配置"""
        # 从配置文件读取内网和外网IP
        # 配置格式：
        # {
        #     "network": {
        #         "internal": {"ip": "http://172.18.17.149:2504", "name": "内网"},
        #         "external": {"ip": "http://isc.cqu.edu.cn:2504", "name": "外网"}
        #     }
        # }
        network_config = self.config_mgr.get('network', default={})
        if not network_config:
            # 如果配置不存在，使用默认值
            network_config = {
                "internal": {"ip": "http://172.18.17.149:2504", "name": "内网"},
                "external": {"ip": "http://isc.cqu.edu.cn:2504", "name": "外网"}
            }
        return network_config

    def init_ui(self):
        """初始化UI"""
        # 设置窗口属性
        self.setWindowTitle("用户登录")
        self.setFixedSize(600, 800)  # 固定大小600*800
        self.setWindowFlags(Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint)

        # 主布局
        main_layout = QVBoxLayout()
        main_layout.setSpacing(20)
        main_layout.setContentsMargins(40, 40, 40, 40)

        # ========== Logo区域（使用本地图片）==========
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setFixedSize(150, 150)

        # 加载本地图片（请将 logo.png 放在项目目录下）
        logo_path = self._get_logo_path()
        if os.path.exists(logo_path):
            pixmap = QPixmap(logo_path)
            if not pixmap.isNull():
                scaled_pixmap = pixmap.scaled(150, 150, Qt.KeepAspectRatio, Qt.SmoothTransformation)
                logo_label.setPixmap(scaled_pixmap)
            else:
                # 如果图片加载失败，使用文字替代
                logo_label.setText("🚢")
                logo_label.setStyleSheet("font-size: 80px; color: #2c3e50;")
        else:
            # 如果图片不存在，使用文字替代
            logo_label.setText("🚢")
            logo_label.setStyleSheet("font-size: 80px; color: #2c3e50;")

        main_layout.addWidget(logo_label, alignment=Qt.AlignCenter)

        # 标题
        title_label = QLabel("指挥船舶系统")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #2c3e50; margin-bottom: 10px;")
        main_layout.addWidget(title_label)

        # ========== 表单区域 ==========
        form_frame = QFrame()
        form_layout = QVBoxLayout(form_frame)
        form_layout.setSpacing(10)

        # ===== 用户名 =====
        username_label = QLabel("用户名")
        username_label.setFont(QFont("", 12))
        username_label.setStyleSheet("color: #2c3e50; font-weight: bold;")
        form_layout.addWidget(username_label)

        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("请输入用户名")
        form_layout.addWidget(self.username_edit)

        # ===== 密码 =====
        password_label = QLabel("密码")
        password_label.setFont(QFont("", 12))
        password_label.setStyleSheet("color: #2c3e50; font-weight: bold;")
        form_layout.addWidget(password_label)

        # 密码输入框 + 显示按钮（水平布局）
        password_layout = QHBoxLayout()
        password_layout.setSpacing(0)

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("请输入密码")
        self.password_edit.setEchoMode(QLineEdit.Password)
        password_layout.addWidget(self.password_edit)

        # 密码显示/隐藏按钮
        self.show_pwd_btn = QPushButton("👁")
        self.show_pwd_btn.setObjectName("showPwdBtn")
        self.show_pwd_btn.setFixedWidth(40)
        self.show_pwd_btn.setToolTip("显示/隐藏密码")
        self.show_pwd_btn.clicked.connect(self.toggle_password_visibility)
        password_layout.addWidget(self.show_pwd_btn)

        form_layout.addLayout(password_layout)

        # ===== 网络选择 =====
        network_label = QLabel("网络选择")
        network_label.setFont(QFont("", 12))
        network_label.setStyleSheet("color: #2c3e50; font-weight: bold; margin-top: 8px;")
        form_layout.addWidget(network_label)

        network_layout = QHBoxLayout()
        network_layout.setSpacing(20)

        self.internal_radio = QRadioButton("内网")
        self.internal_radio.setChecked(True)
        self.internal_radio.toggled.connect(self.on_network_changed)
        network_layout.addWidget(self.internal_radio)

        self.external_radio = QRadioButton("外网")
        self.external_radio.toggled.connect(self.on_network_changed)
        network_layout.addWidget(self.external_radio)

        network_layout.addStretch()
        form_layout.addLayout(network_layout)

        # IP地址显示
        self.network_ip_label = QLabel()
        self.network_ip_label.setStyleSheet("color: #7f8c8d; font-size: 11px; margin-top: -5px;")
        self.update_network_ip_label()
        form_layout.addWidget(self.network_ip_label)

        # 记住密码复选框
        self.remember_checkbox = QCheckBox("记住密码")
        self.remember_checkbox.setFont(QFont("", 12))
        form_layout.addWidget(self.remember_checkbox)

        main_layout.addWidget(form_frame)

        # ========== 按钮区域 ==========
        button_layout = QHBoxLayout()
        button_layout.setSpacing(15)

        self.login_btn = QPushButton("登录")
        self.login_btn.setObjectName("loginBtn")
        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setObjectName("cancelBtn")

        button_layout.addWidget(self.login_btn)
        button_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(button_layout)

        # 状态信息
        self.status_label = QLabel("")
        self.status_label.setAlignment(Qt.AlignCenter)
        self.status_label.setStyleSheet("color: #e74c3c; font-size: 12px; min-height: 20px;")
        main_layout.addWidget(self.status_label)

        # 添加弹性空间
        main_layout.addStretch()

        # 版本信息
        version_label = QLabel("v1.0.0")
        version_label.setAlignment(Qt.AlignCenter)
        version_label.setStyleSheet("color: #bdc3c7; font-size: 11px;")
        main_layout.addWidget(version_label)

        self.setLayout(main_layout)

        # 连接信号
        self.login_btn.clicked.connect(self.handle_login)
        self.cancel_btn.clicked.connect(self.reject)
        self.username_edit.returnPressed.connect(self.handle_login)
        self.password_edit.returnPressed.connect(self.handle_login)

    def toggle_password_visibility(self):
        """切换密码显示/隐藏"""
        self.password_visible = not self.password_visible
        if self.password_visible:
            self.password_edit.setEchoMode(QLineEdit.Normal)
            self.show_pwd_btn.setText("🙈")
            self.show_pwd_btn.setToolTip("隐藏密码")
        else:
            self.password_edit.setEchoMode(QLineEdit.Password)
            self.show_pwd_btn.setText("👁")
            self.show_pwd_btn.setToolTip("显示密码")

    def _get_logo_path(self):
        """获取Logo图片路径"""
        # 尝试多个可能的路径
        possible_paths = [
            os.path.join(os.path.dirname(__file__), "images", "logo.png"),
            os.path.join(os.path.dirname(__file__), "logo.jpg"),
            os.path.join("images", "logo.jpg"),
            "logo.jpg"
        ]
        for path in possible_paths:
            if os.path.exists(path):
                return path
        return ""

    def on_network_changed(self):
        """网络选择变化"""
        self.update_network_ip_label()
        # 更新APIService的IP地址
        self.update_api_service_ip()

    def update_network_ip_label(self):
        """更新网络IP显示标签"""
        if self.internal_radio.isChecked():
            ip = self.network_config.get('internal', {}).get('ip', '')
            self.selected_network = 'internal'
            self.network_ip_label.setText(f"(内网IP: {ip})")
        else:
            ip = self.network_config.get('external', {}).get('ip', '')
            self.selected_network = 'external'
            self.network_ip_label.setText(f"(外网IP: {ip})")

    def update_api_service_ip(self):
        """更新APIService的IP地址"""
        if self.internal_radio.isChecked():
            ip = self.network_config.get('internal', {}).get('ip', '')
        else:
            ip = self.network_config.get('external', {}).get('ip', '')
        # 更新APIService的IP
        self.api_service.set_base_url(ip)
        print(f"切换到: {ip}")

    def load_saved_credentials(self):
        """加载保存的账号密码"""
        remember = self.config_mgr.get('login', 'remember_password', default=False)
        self.remember_checkbox.setChecked(remember)

        if remember:
            username = self.config_mgr.get('login', 'last_username', default='')
            password = self.config_mgr.get('login', 'last_password', default='')
            self.username_edit.setText(username)
            self.password_edit.setText(password)

    def save_credentials(self, username, password):
        """保存账号密码到配置文件"""
        self.config_mgr.set('login', 'remember_password',
                            value=self.remember_checkbox.isChecked())

        if self.remember_checkbox.isChecked():
            # 如果记住密码，保存账号密码
            self.config_mgr.set('login', 'last_username', value=username)
            self.config_mgr.set('login', 'last_password', value=password)
        else:
            # 如果不记住密码，清除保存的账号密码
            self.config_mgr.set('login', 'last_username', value='')
            self.config_mgr.set('login', 'last_password', value='')

        self.config_mgr.save_config()



    def handle_login(self):
        """处理登录逻辑"""
        username = self.username_edit.text().strip()
        password = self.password_edit.text().strip()

        # 输入验证
        if not username:
            self.status_label.setText("请输入用户名")
            self.username_edit.setFocus()
            return

        if not password:
            self.status_label.setText("请输入密码")
            self.password_edit.setFocus()
            return

        # 禁用登录按钮，防止重复点击
        self.login_btn.setEnabled(False)
        self.login_btn.setText("登录中...")
        self.status_label.setText("正在验证，请稍候...")

        # 创建并启动登录线程
        self.login_thread = LoginThread(self.api_service, username,password)
        self.login_thread.login_finished.connect(self.on_login_finished)
        self.login_thread.login_error.connect(self.on_login_error)
        self.login_thread.finished.connect(self.login_thread.deleteLater)  # 线程结束后自动清理
        self.login_thread.start()

    def on_login_finished(self, success):
        """登录完成的回调"""
        if success:
            self.status_label.setText("登录成功")

            # 获取网络类型
            network_type = "内网" if self.internal_radio.isChecked() else "外网"

            # 发出登录成功信号
            self.login_success.emit(self.api_service, self.username_edit.text().strip(),network_type)

            # 关闭登录对话框
            self.accept()

        else:
            error_msg = getattr(self.api_service, 'last_error', '用户名或密码错误')
            self.status_label.setText(error_msg)
            self.password_edit.clear()
            self.password_edit.setFocus()
            # 恢复登录按钮
            self.login_btn.setEnabled(True)
            self.login_btn.setText("登录")
            self.status_label.setText("")


    def on_login_error(self, error_msg):
        """登录错误的回调"""
        self.status_label.setText(f"登录异常: {error_msg}")
        self.login_btn.setEnabled(True)
    def clear_input(self):
        """清空输入"""
        self.username_edit.clear()
        self.password_edit.clear()
        self.status_label.clear()
        self.username_edit.setFocus()

# if __name__ == "__main__":
#     app = QApplication(sys.argv)
#
#     window = LoginDialog()
#     window.show()          # 显示窗口
#     sys.exit(app.exec_())  # 进入事件循环