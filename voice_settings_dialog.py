# voice_settings_dialog.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QGroupBox,
                             QLabel, QLineEdit, QSpinBox, QComboBox, QSlider,
                             QPushButton, QCheckBox, QTextEdit, QMessageBox,
                             QRadioButton, QButtonGroup, QFormLayout, QTabWidget)
from PyQt5.QtCore import Qt, pyqtSignal
from PyQt5.QtGui import QFont


class VoiceSettingsDialog(QDialog):
    """语音播报设置界面"""

    config_changed = pyqtSignal(dict)  # 配置变化信号

    def __init__(self, voice_manager, db_manager, reachcode: str, parent=None):
        super().__init__(parent)
        self.voice_manager = voice_manager
        self.db_manager = db_manager
        self.reachcode = reachcode

        self.setWindowTitle("语音播报设置")
        self.setFixedSize(550, 650)

        # 加载配置
        self.load_vhf_config()

        self.init_ui()
        self.load_current_settings()

    def load_vhf_config(self):
        """从数据库加载高频语音配置"""
        try:
            conditions = {"reachCode": self.reachcode}
            results = self.db_manager.search_records("VHFip", conditions)
            if results:
                row = results[0]
                self.vhf_ip = row.get('VHFIP', '')
                self.vhf_port = row.get('vhfPort', 0)
                self.vhf_send_type = row.get('sendType', 'web')
            else:
                self.vhf_ip = ''
                self.vhf_port = 0
                self.vhf_send_type = 'web'
        except Exception as e:
            print(f"加载高频语音配置失败: {e}")
            self.vhf_ip = ''
            self.vhf_port = 0
            self.vhf_send_type = 'web'

    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)
        layout.setSpacing(15)
        layout.setContentsMargins(20, 20, 20, 20)

        # ========== 语音源选择 ==========
        source_group = QGroupBox("语音源选择")
        source_layout = QVBoxLayout(source_group)

        source_hint_label = QLabel("请选择语音播报方式（可多选）")
        source_hint_label.setStyleSheet("color: #7f8c8d; font-size: 12px;")
        source_layout.addWidget(source_hint_label)

        source_check_layout = QHBoxLayout()

        self.local_check = QCheckBox("本地语音")
        self.local_check.setChecked(True)
        self.local_check.toggled.connect(self.on_source_changed)
        source_check_layout.addWidget(self.local_check)

        self.vhf_check = QCheckBox("高频语音")
        self.vhf_check.setChecked(False)
        self.vhf_check.toggled.connect(self.on_source_changed)
        source_check_layout.addWidget(self.vhf_check)

        source_check_layout.addStretch()
        source_layout.addLayout(source_check_layout)

        layout.addWidget(source_group)

        # ========== 高频语音配置 ==========
        vhf_group = QGroupBox("高频语音配置")
        vhf_layout = QFormLayout(vhf_group)

        # IP地址
        self.ip_edit = QLineEdit()
        self.ip_edit.setPlaceholderText("请输入高频语音IP地址")
        self.ip_edit.setText(self.vhf_ip)
        vhf_layout.addRow("IP地址:", self.ip_edit)

        # 端口
        self.port_spin = QSpinBox()
        self.port_spin.setRange(1, 65535)
        self.port_spin.setValue(int(self.vhf_port))
        vhf_layout.addRow("端口:", self.port_spin)

        # 发送方式
        self.send_type_combo = QComboBox()
        self.send_type_combo.addItems(["web接口", "PTT接口"])
        self.send_type_combo.setCurrentText("web接口" if self.vhf_send_type == "web" else "PTT接口")
        vhf_layout.addRow("发送方式:", self.send_type_combo)

        # 保存按钮
        save_vhf_btn = QPushButton("保存高频语音配置")
        save_vhf_btn.clicked.connect(self.save_vhf_config)
        vhf_layout.addRow("", save_vhf_btn)

        layout.addWidget(vhf_group)

        # ========== 语音参数设置 ==========
        param_group = QGroupBox("语音参数设置")
        param_layout = QFormLayout(param_group)

        # 语速
        rate_layout = QHBoxLayout()
        self.rate_slider = QSlider(Qt.Horizontal)
        self.rate_slider.setRange(-10, 10)
        self.rate_slider.setValue(0)
        self.rate_slider.valueChanged.connect(self.on_rate_changed)
        self.rate_label = QLabel("0.0")
        self.rate_label.setFixedWidth(40)
        rate_layout.addWidget(self.rate_slider)
        rate_layout.addWidget(self.rate_label)
        param_layout.addRow("语速:", rate_layout)

        layout.addWidget(param_group)

        # ========== 测试区域 ==========
        test_group = QGroupBox("语音测试")
        test_layout = QVBoxLayout(test_group)

        self.test_text = QTextEdit()
        self.test_text.setPlaceholderText("请输入要测试的播报文字...")
        self.test_text.setMaximumHeight(80)
        test_layout.addWidget(self.test_text)

        test_btn_layout = QHBoxLayout()
        test_local_btn = QPushButton("测试本地语音")
        test_local_btn.clicked.connect(lambda: self.test_voice("local"))
        test_btn_layout.addWidget(test_local_btn)

        test_vhf_btn = QPushButton("测试高频语音")
        test_vhf_btn.clicked.connect(lambda: self.test_voice("vhf"))
        test_btn_layout.addWidget(test_vhf_btn)

        test_both_btn = QPushButton("同时测试")
        test_both_btn.clicked.connect(lambda: self.test_voice("both"))
        test_btn_layout.addWidget(test_both_btn)

        test_btn_layout.addStretch()
        test_layout.addLayout(test_btn_layout)

        layout.addWidget(test_group)

        # ========== 底部按钮 ==========
        btn_layout = QHBoxLayout()

        apply_btn = QPushButton("应用设置")
        apply_btn.clicked.connect(self.apply_settings)
        apply_btn.setStyleSheet("background-color: #3498db; color: white;")

        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)

        btn_layout.addStretch()
        btn_layout.addWidget(apply_btn)
        btn_layout.addWidget(close_btn)

        layout.addLayout(btn_layout)

    def load_current_settings(self):
        """加载当前设置到界面"""
        self.local_check.setChecked(self.voice_manager.local_enabled)
        self.vhf_check.setChecked(self.voice_manager.vhf_enabled)
        self.rate_slider.setValue(int(self.voice_manager.rate * 10))
        self.rate_label.setText(f"{self.voice_manager.rate:.1f}")

    def on_source_changed(self):
        """语音源选择变化"""
        self.vhf_check.setEnabled(True)

    def on_rate_changed(self, value):
        """语速变化"""
        rate = value / 10.0
        self.rate_label.setText(f"{rate:.1f}")

    def save_vhf_config(self):
        """保存高频语音配置到数据库"""
        ip = self.ip_edit.text().strip()
        port = self.port_spin.value()
        send_type = "web" if self.send_type_combo.currentText() == "web接口" else "ptt"

        if not ip:
            QMessageBox.warning(self, "提示", "请输入IP地址")
            return

        try:
            # 检查是否已存在记录
            conditions = {"reachCode": self.reachcode}
            results = self.db_manager.search_records("VHFip", conditions)

            if results:
                # 更新
                self.db_manager.update_by_single_condition(
                    "VHFip",
                    {"VHFIP": ip, "vhfPort": port, "sendType": send_type},
                    "reachCode",
                    self.reachcode
                )
            else:
                # 插入
                self.db_manager.insert_record("VHFip", {
                    "reachCode": self.reachcode,
                    "VHFIP": ip,
                    "vhfPort": port,
                    "sendType": send_type
                })

            QMessageBox.information(self, "成功", "高频语音配置已保存")

        except Exception as e:
            QMessageBox.warning(self, "错误", f"保存失败: {e}")

    def apply_settings(self):
        """应用设置"""
        # 更新语音管理器配置
        self.voice_manager.set_local_enabled(self.local_check.isChecked())
        self.voice_manager.set_vhf_enabled(self.vhf_check.isChecked())
        self.voice_manager.set_rate(self.rate_slider.value() / 10.0)

        # 如果高频语音启用，更新配置
        if self.vhf_check.isChecked():
            ip = self.ip_edit.text().strip()
            port = self.port_spin.value()
            send_type = "web" if self.send_type_combo.currentText() == "web接口" else "ptt"
            self.voice_manager.set_vhf_config(ip, port, send_type)

        # 发送配置变化信号
        config = {
            'local_enabled': self.local_check.isChecked(),
            'vhf_enabled': self.vhf_check.isChecked(),
            'rate': self.rate_slider.value() / 10.0,
            'vhf_ip': self.ip_edit.text().strip(),
            'vhf_port': self.port_spin.value(),
            'vhf_send_type': 'web' if self.send_type_combo.currentText() == 'web接口' else 'ptt'
        }
        self.config_changed.emit(config)

        QMessageBox.information(self, "提示", "语音设置已应用")

    def test_voice(self, source: str):
        """测试语音播报"""
        text = self.test_text.toPlainText().strip()
        if not text:
            QMessageBox.warning(self, "提示", "请输入要测试的播报文字")
            return

        # 根据选择的源测试
        if source == "local":
            if not self.local_check.isChecked():
                QMessageBox.warning(self, "提示", "本地语音未启用")
                return
            self.voice_manager.speak(text, priority=10, source="local")
        elif source == "vhf":
            if not self.vhf_check.isChecked():
                QMessageBox.warning(self, "提示", "高频语音未启用")
                return
            self.voice_manager.speak(text, priority=10, source="vhf")
        else:
            # both
            self.voice_manager.speak(text, priority=10, source="both")

        QMessageBox.information(self, "提示", "语音播报已发送")