# login_dialog.py
import sys
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QCheckBox, QPushButton, QMessageBox,
                             QApplication, QFrame, QWidget)
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
    login_success = pyqtSignal(object, str)  # 传递APIService实例和用户名

    def __init__(self, parent=None):
        super().__init__(parent)
        # 设置为模态对话框
        self.setModal(True)
        self.config_mgr = ConfigManager()
        ipaddress=self.config_mgr.get('login', 'IP_address', default='')
        # 如果外部传入了APIService实例则使用，否则创建新的
        self.api_service =  APIService(ipaddress)

        self.init_ui()
        self.load_saved_credentials()

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

        # 添加Logo区域（可选）
        logo_label = QLabel()
        logo_label.setAlignment(Qt.AlignCenter)
        logo_label.setText("🚢")  # 可以用图标或图片
        logo_label.setStyleSheet("font-size: 80px; color: #2c3e50;")
        main_layout.addWidget(logo_label)

        # 标题
        title_label = QLabel("船舶监控系统")
        title_label.setAlignment(Qt.AlignCenter)
        title_font = QFont()
        title_font.setPointSize(24)
        title_font.setBold(True)
        title_label.setFont(title_font)
        title_label.setStyleSheet("color: #34495e; margin-bottom: 20px;")
        main_layout.addWidget(title_label)

        # 表单区域
        form_frame = QFrame()
        form_frame.setStyleSheet("""
            QFrame {
                background-color: #f8f9fa;
                border-radius: 10px;
                padding: 30px;
            }
            QLineEdit {
                padding: 10px;
                border: 1px solid #ced4da;
                border-radius: 5px;
                font-size: 14px;
                min-height: 20px;
            }
            QLineEdit:focus {
                border: 2px solid #3498db;
            }
            QCheckBox {
                font-size: 14px;
                spacing: 8px;
            }
            QPushButton {
                padding: 12px;
                border-radius: 5px;
                font-size: 16px;
                font-weight: bold;
                min-height: 30px;
            }
            QPushButton#loginBtn {
                background-color: #3498db;
                color: white;
                border: none;
            }
            QPushButton#loginBtn:hover {
                background-color: #2980b9;
            }
            QPushButton#cancelBtn {
                background-color: #e74c3c;
                color: white;
                border: none;
            }
            QPushButton#cancelBtn:hover {
                background-color: #c0392b;
            }
        """)

        form_layout = QVBoxLayout(form_frame)
        form_layout.setSpacing(15)

        # 用户名
        username_label = QLabel("用户名:")
        username_label.setFont(QFont("", 12))
        self.username_edit = QLineEdit()
        self.username_edit.setPlaceholderText("请输入用户名")

        # 密码
        password_label = QLabel("密码:")
        password_label.setFont(QFont("", 12))
        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("请输入密码")
        self.password_edit.setEchoMode(QLineEdit.Password)

        # 记住密码复选框
        self.remember_checkbox = QCheckBox("记住密码")
        self.remember_checkbox.setFont(QFont("", 12))

        # 添加控件到表单布局
        form_layout.addWidget(username_label)
        form_layout.addWidget(self.username_edit)
        form_layout.addWidget(password_label)
        form_layout.addWidget(self.password_edit)
        form_layout.addWidget(self.remember_checkbox)

        main_layout.addWidget(form_frame)

        # 按钮区域
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
        self.status_label.setStyleSheet("color: #e74c3c; font-size: 12px;")
        main_layout.addWidget(self.status_label)

        # 添加弹性空间
        main_layout.addStretch()

        self.setLayout(main_layout)

        # 连接信号
        self.login_btn.clicked.connect(self.handle_login)
        self.cancel_btn.clicked.connect(self.reject)
        self.username_edit.returnPressed.connect(self.handle_login)
        self.password_edit.returnPressed.connect(self.handle_login)

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
            # 发出登录成功信号
            self.login_success.emit(self.api_service, self.username_edit.text().strip())
        else:
            error_msg = getattr(self.api_service, 'last_error', '用户名或密码错误')
            self.status_label.setText(error_msg)
            self.password_edit.clear()
            self.password_edit.setFocus()
            # 恢复登录按钮
            self.login_btn.setEnabled(True)

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