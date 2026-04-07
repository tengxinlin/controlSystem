# passage_record_edit_dialog.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QFormLayout,
                             QLineEdit, QComboBox, QSpinBox, QDoubleSpinBox,
                             QTextEdit, QPushButton, QLabel, QMessageBox,
                             QDateTimeEdit, QGroupBox, QCheckBox)
from PyQt5.QtCore import Qt, QDateTime, pyqtSignal
from datetime import datetime


class PassageRecordEditDialog(QDialog):
    """船舶通行记录编辑对话框（支持编辑/新增模式）"""

    # 信号
    record_saved = pyqtSignal(dict)  # 保存/新增成功时发射

    def __init__(self, mmsi: str, name: str, record_manager, parent=None):
        """
        初始化编辑对话框

        Args:
            mmsi: 船舶MMSI
            name: 船舶名称
            record_manager: 通行记录管理器
            parent: 父窗口
        """
        super().__init__(parent)
        self.mmsi = mmsi
        self.ship_name = name
        self.record_manager = record_manager
        self.existing_record = None  # 已有的活跃记录

        # 检查是否有进行中的记录
        self.check_existing_record()

        # 设置窗口标题
        if self.existing_record:
            self.setWindowTitle(f"编辑通行记录 - {self.existing_record.get('name', name)} ({mmsi})")
        else:
            self.setWindowTitle(f"新增通行记录 - {name} ({mmsi})")

        self.setFixedSize(600, 1000)

        self.init_ui()
        self.load_record_data()

    def check_existing_record(self):
        """检查是否有进行中的记录"""
        active_records = self.record_manager.get_active_records()
        for record in active_records:
            if record.get('mmsi') == self.mmsi:
                self.existing_record = record
                break

    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)

        # 基本信息分组
        basic_group = QGroupBox("基本信息")
        basic_layout = QFormLayout(basic_group)

        # MMSI（只读）
        self.mmsi_label = QLabel(self.mmsi)
        basic_layout.addRow("MMSI:", self.mmsi_label)

        # 船名
        self.name_edit = QLabel(self.ship_name)
        basic_layout.addRow("船名:", self.name_edit)

        # 方向
        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["上行", "下行"])
        basic_layout.addRow("方向:", self.direction_combo)

        # 拖驳数
        self.tug_count_spin = QSpinBox()
        self.tug_count_spin.setRange(0, 50)
        self.tug_count_spin.setSuffix(" 艘")
        basic_layout.addRow("拖驳数:", self.tug_count_spin)

        # 货物类型
        self.cargo_edit = QLineEdit()
        self.cargo_edit.setPlaceholderText("请输入货物类型")
        basic_layout.addRow("货物:", self.cargo_edit)

        # 载重信息
        load_layout = QHBoxLayout()
        self.actual_load_spin = QDoubleSpinBox()
        self.actual_load_spin.setRange(0, 100000)
        self.actual_load_spin.setSuffix(" 吨")
        self.actual_load_spin.setSingleStep(100)
        load_layout.addWidget(self.actual_load_spin)

        self.rated_load_spin = QDoubleSpinBox()
        self.rated_load_spin.setRange(0, 100000)
        self.rated_load_spin.setSuffix(" 吨")
        self.rated_load_spin.setSingleStep(100)
        load_layout.addWidget(self.rated_load_spin)

        basic_layout.addRow("实际/额定载重:", load_layout)

        layout.addWidget(basic_group)

        # 环境信息分组
        env_group = QGroupBox("环境信息")
        env_layout = QFormLayout(env_group)

        # 水位
        self.water_level_spin = QDoubleSpinBox()
        self.water_level_spin.setRange(0, 50)
        self.water_level_spin.setSuffix(" 米")
        self.water_level_spin.setSingleStep(0.1)
        env_layout.addRow("水位:", self.water_level_spin)

        # 天气
        self.weather_combo = QComboBox()
        self.weather_combo.addItems(["晴", "雨", "阴", "霾", "雾"])
        env_layout.addRow("天气:", self.weather_combo)

        # 值班人
        self.duty_person_edit = QLineEdit()
        self.duty_person_edit.setPlaceholderText("请输入值班人姓名")
        env_layout.addRow("值班人:", self.duty_person_edit)

        # 顶推情况
        self.pushing_combo = QComboBox()
        self.pushing_combo.addItems(["无", "顶推", "调头等待"])
        env_layout.addRow("顶推情况:", self.pushing_combo)

        layout.addWidget(env_group)

        # 时间信息分组
        self.time_group = QGroupBox("时间信息")
        self.time_layout = QFormLayout(self.time_group)

        # 获取当前时间
        current_datetime = QDateTime.currentDateTime()

        # 预告时间
        self.forecast_time_check = QCheckBox("设置预告时间")
        self.forecast_time_check.setChecked(False)
        self.forecast_time_edit = QDateTimeEdit()
        self.forecast_time_edit.setCalendarPopup(True)
        self.forecast_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.forecast_time_edit.setDateTime(current_datetime)  # 设置为当前时间
        self.forecast_time_edit.setEnabled(False)
        self.forecast_time_check.toggled.connect(self.forecast_time_edit.setEnabled)
        forecast_layout = QHBoxLayout()
        forecast_layout.addWidget(self.forecast_time_check)
        forecast_layout.addWidget(self.forecast_time_edit)
        self.time_layout.addRow("预告时间:", forecast_layout)

        # 补充时间
        self.supplement_time_check = QCheckBox("设置补充时间")
        self.supplement_time_check.setChecked(False)
        self.supplement_time_edit = QDateTimeEdit()
        self.supplement_time_edit.setCalendarPopup(True)
        self.supplement_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.supplement_time_edit.setDateTime(current_datetime)  # 设置为当前时间
        self.supplement_time_edit.setEnabled(False)
        self.supplement_time_check.toggled.connect(self.supplement_time_edit.setEnabled)
        supplement_layout = QHBoxLayout()
        supplement_layout.addWidget(self.supplement_time_check)
        supplement_layout.addWidget(self.supplement_time_edit)
        self.time_layout.addRow("补充时间:", supplement_layout)

        # 起挂时间
        self.start_hang_time_check = QCheckBox("设置起挂时间")
        self.start_hang_time_check.setChecked(False)
        self.start_hang_time_edit = QDateTimeEdit()
        self.start_hang_time_edit.setCalendarPopup(True)
        self.start_hang_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.start_hang_time_edit.setDateTime(current_datetime)  # 设置为当前时间
        self.start_hang_time_edit.setEnabled(False)
        self.start_hang_time_check.toggled.connect(self.start_hang_time_edit.setEnabled)
        start_hang_layout = QHBoxLayout()
        start_hang_layout.addWidget(self.start_hang_time_check)
        start_hang_layout.addWidget(self.start_hang_time_edit)
        self.time_layout.addRow("起挂时间:", start_hang_layout)

        # 半杆时间
        self.half_pole_time_check = QCheckBox("设置半杆时间")
        self.half_pole_time_check.setChecked(False)
        self.half_pole_time_edit = QDateTimeEdit()
        self.half_pole_time_edit.setCalendarPopup(True)
        self.half_pole_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.half_pole_time_edit.setDateTime(current_datetime)  # 设置为当前时间
        self.half_pole_time_edit.setEnabled(False)
        self.half_pole_time_check.toggled.connect(self.half_pole_time_edit.setEnabled)
        half_pole_layout = QHBoxLayout()
        half_pole_layout.addWidget(self.half_pole_time_check)
        half_pole_layout.addWidget(self.half_pole_time_edit)
        self.time_layout.addRow("半杆时间:", half_pole_layout)

        # 进漕时间
        self.enter_channel_time_check = QCheckBox("设置进漕时间")
        self.enter_channel_time_check.setChecked(False)
        self.enter_channel_time_edit = QDateTimeEdit()
        self.enter_channel_time_edit.setCalendarPopup(True)
        self.enter_channel_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.enter_channel_time_edit.setDateTime(current_datetime)  # 设置为当前时间
        self.enter_channel_time_edit.setEnabled(False)
        self.enter_channel_time_check.toggled.connect(self.enter_channel_time_edit.setEnabled)
        enter_layout = QHBoxLayout()
        enter_layout.addWidget(self.enter_channel_time_check)
        enter_layout.addWidget(self.enter_channel_time_edit)
        self.time_layout.addRow("进漕时间:", enter_layout)

        # 出漕时间
        self.exit_channel_time_check = QCheckBox("设置出漕时间")
        self.exit_channel_time_check.setChecked(False)
        self.exit_channel_time_edit = QDateTimeEdit()
        self.exit_channel_time_edit.setCalendarPopup(True)
        self.exit_channel_time_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.exit_channel_time_edit.setDateTime(current_datetime)  # 设置为当前时间
        self.exit_channel_time_edit.setEnabled(False)
        self.exit_channel_time_check.toggled.connect(self.exit_channel_time_edit.setEnabled)
        exit_layout = QHBoxLayout()
        exit_layout.addWidget(self.exit_channel_time_check)
        exit_layout.addWidget(self.exit_channel_time_edit)
        self.time_layout.addRow("出漕时间:", exit_layout)

        layout.addWidget(self.time_group)

        # 备注
        self.remark_edit = QTextEdit()
        self.remark_edit.setMaximumHeight(80)
        self.remark_edit.setPlaceholderText("请输入备注信息...")
        layout.addWidget(QLabel("备注:"))
        layout.addWidget(self.remark_edit)

        # 按钮区域
        btn_layout = QHBoxLayout()

        if self.existing_record:
            # 编辑模式：保存和取消按钮
            self.save_btn = QPushButton("保存修改")
            self.save_btn.clicked.connect(self.save_record)
            self.save_btn.setStyleSheet("background-color: #27ae60; color: white;")
        else:
            # 新增模式：新增和取消按钮
            self.save_btn = QPushButton("新增记录")
            self.save_btn.clicked.connect(self.add_record)
            self.save_btn.setStyleSheet("background-color: #3498db; color: white;")

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.save_btn)
        btn_layout.addWidget(self.cancel_btn)
        layout.addLayout(btn_layout)

        # 如果是编辑模式，加载现有时间数据并显示复选框状态
        if self.existing_record:
            self.time_group.setVisible(True)

    def load_record_data(self):
        """加载记录数据到界面"""
        if self.existing_record:
            # 编辑模式：加载现有数据
            self.name_edit.setText(self.existing_record.get('name', self.ship_name))
            direction = self.existing_record.get('direction', 'up')
            self.direction_combo.setCurrentText("上行" if direction == 'up' else "下行")
            self.tug_count_spin.setValue(self.existing_record.get('tug_count', 0))
            self.cargo_edit.setText(self.existing_record.get('cargo', ''))
            self.actual_load_spin.setValue(self.existing_record.get('actual_load', 0))
            self.rated_load_spin.setValue(self.existing_record.get('rated_load', 0))
            self.water_level_spin.setValue(self.existing_record.get('water_level', 0))
            self.weather_combo.setCurrentText(self.existing_record.get('weather', '晴'))
            self.duty_person_edit.setText(self.existing_record.get('duty_person', ''))
            self.pushing_combo.setCurrentText(self.existing_record.get('pushing_status', '无'))
            self.remark_edit.setPlainText(self.existing_record.get('remark', ''))

            # 加载时间信息（有数据则选中复选框）
            self.load_time_field_with_check(self.forecast_time_check, self.forecast_time_edit,
                                            self.existing_record.get('forecast_time', 0))
            self.load_time_field_with_check(self.supplement_time_check, self.supplement_time_edit,
                                            self.existing_record.get('supplement_time', 0))
            self.load_time_field_with_check(self.start_hang_time_check, self.start_hang_time_edit,
                                            self.existing_record.get('start_hang_time', 0))
            self.load_time_field_with_check(self.half_pole_time_check, self.half_pole_time_edit,
                                            self.existing_record.get('half_pole_time', 0))
            self.load_time_field_with_check(self.enter_channel_time_check, self.enter_channel_time_edit,
                                            self.existing_record.get('enter_channel_time', 0))
            self.load_time_field_with_check(self.exit_channel_time_check, self.exit_channel_time_edit,
                                            self.existing_record.get('exit_channel_time', 0))
        else:
            # 新增模式：使用传入的船名，时间字段为空
            self.name_edit.setText(self.ship_name)
            # 新增模式时间字段全部为空，复选框未选中

    def load_time_field_with_check(self, check_box, time_edit, timestamp):
        """加载时间字段（带复选框）"""
        if timestamp and timestamp > 0:
            check_box.setChecked(True)
            time_edit.setEnabled(True)
            time_edit.setDateTime(QDateTime.fromSecsSinceEpoch(timestamp))

    def get_time_timestamp(self, check_box, time_edit) -> int:
        """获取时间戳（根据复选框状态）"""
        if check_box.isChecked():
            dt = time_edit.dateTime()
            return dt.toSecsSinceEpoch() if dt.isValid() else 0
        return 0

    def get_record_data(self) -> dict:
        """获取界面数据"""
        direction = "up" if self.direction_combo.currentText() == "上行" else "down"

        data = {
            'mmsi': self.mmsi,
            'name': self.name_edit.text().strip(),
            'direction': direction,
            'tug_count': self.tug_count_spin.value(),
            'cargo': self.cargo_edit.text().strip(),
            'actual_load': self.actual_load_spin.value(),
            'rated_load': self.rated_load_spin.value(),
            'water_level': self.water_level_spin.value(),
            'weather': self.weather_combo.currentText(),
            'duty_person': self.duty_person_edit.text().strip(),
            'pushing_status': self.pushing_combo.currentText(),
            'remark': self.remark_edit.toPlainText().strip()
        }

        # 获取时间信息（根据复选框状态决定是否保存）
        data['forecast_time'] = self.get_time_timestamp(self.forecast_time_check, self.forecast_time_edit)
        data['supplement_time'] = self.get_time_timestamp(self.supplement_time_check, self.supplement_time_edit)
        data['start_hang_time'] = self.get_time_timestamp(self.start_hang_time_check, self.start_hang_time_edit)
        data['half_pole_time'] = self.get_time_timestamp(self.half_pole_time_check, self.half_pole_time_edit)
        data['enter_channel_time'] = self.get_time_timestamp(self.enter_channel_time_check,
                                                             self.enter_channel_time_edit)
        data['exit_channel_time'] = self.get_time_timestamp(self.exit_channel_time_check, self.exit_channel_time_edit)

        return data

    def validate_data(self, data: dict) -> bool:
        """验证数据"""
        if not data['name']:
            QMessageBox.warning(self, "提示", "请输入船舶名称")
            return False

        if not data['cargo']:
            QMessageBox.warning(self, "提示", "请输入货物类型")
            return False

        if not data['duty_person']:
            QMessageBox.warning(self, "提示", "请输入值班人")
            return False

        return True

    def save_record(self):
        """保存记录（编辑模式）"""
        data = self.get_record_data()

        if not self.validate_data(data):
            return

        # 更新记录（只更新有值的字段，时间字段0值表示不更新）
        update_fields = {}
        for key, value in data.items():
            if key != 'mmsi':
                update_fields[key] = value

        success = self.record_manager.update_record(self.mmsi, **update_fields)

        if success:
            QMessageBox.information(self, "成功", "通行记录已更新")
            self.record_saved.emit(data)
            self.accept()
        else:
            QMessageBox.warning(self, "失败", "更新通行记录失败")

    def add_record(self):
        """新增记录（新增模式）"""
        data = self.get_record_data()

        if not self.validate_data(data):
            return

        # 创建新记录
        record = self.record_manager.create_record(
            mmsi=self.mmsi,
            name=data['name'],
            direction=data['direction']
        )

        if record:
            # 更新其他字段（包括时间字段）
            update_fields = {k: v for k, v in data.items()
                             if k not in ['mmsi', 'name', 'direction']}
            if update_fields:
                self.record_manager.update_record(self.mmsi, **update_fields)

            QMessageBox.information(self, "成功", "通行记录已创建")
            self.record_saved.emit(data)
            self.accept()
        else:
            QMessageBox.warning(self, "失败", "创建通行记录失败，可能已有进行中的记录")