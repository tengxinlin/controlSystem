# passage_record_dialog.py
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QTableWidget,
                             QTableWidgetItem, QPushButton, QLabel, QComboBox,
                             QDateEdit, QHeaderView, QMessageBox, QLineEdit,
                             QTextEdit, QFormLayout, QSpinBox, QDoubleSpinBox)
from PyQt5.QtCore import Qt, QDate, pyqtSignal
from PyQt5.QtGui import QFont
from datetime import datetime
from command_record_db import CommandRecordDB

class PassageRecordDialog(QDialog):
    """船舶通行记录管理对话框"""

    # 信号
    record_saved = pyqtSignal(dict)  # 记录保存信号

    def __init__(self, record_manager, parent=None):
        super().__init__(parent)
        self.record_manager = record_manager
        self.current_date = QDate.currentDate()

        self.setWindowTitle("船舶通行记录管理")
        self.resize(1200, 600)

        self.init_ui()
        self.load_records()

    def init_ui(self):
        """初始化界面"""
        layout = QVBoxLayout(self)

        # 工具栏
        toolbar = QHBoxLayout()

        # 日期选择
        toolbar.addWidget(QLabel("日期:"))
        self.date_edit = QDateEdit()
        self.date_edit.setDate(self.current_date)
        self.date_edit.setCalendarPopup(True)
        self.date_edit.dateChanged.connect(self.on_date_changed)
        toolbar.addWidget(self.date_edit)

        # 刷新按钮
        refresh_btn = QPushButton("刷新")
        refresh_btn.clicked.connect(self.load_records)
        toolbar.addWidget(refresh_btn)

        # 自动清理按钮
        cleanup_btn = QPushButton("清理过期记录")
        cleanup_btn.clicked.connect(self.cleanup_records)
        toolbar.addWidget(cleanup_btn)

        # 导出按钮
        export_btn = QPushButton("导出")
        export_btn.clicked.connect(self.export_records)
        toolbar.addWidget(export_btn)

        toolbar.addStretch()
        layout.addLayout(toolbar)

        # 状态过滤
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("状态过滤:"))
        self.status_filter = QComboBox()
        self.status_filter.addItems(["全部", "进行中", "已完成"])
        self.status_filter.currentIndexChanged.connect(self.load_records)
        filter_layout.addWidget(self.status_filter)

        filter_layout.addStretch()
        layout.addLayout(filter_layout)

        # 统计信息
        self.stats_label = QLabel()
        self.stats_label.setStyleSheet("background-color: #f0f0f0; padding: 5px; border-radius: 3px;")
        layout.addWidget(self.stats_label)

        # 表格
        self.table = QTableWidget()
        self.table.setColumnCount(20)
        self.table.setHorizontalHeaderLabels([
            "MMSI", "船名", "方向", "拖驳数", "货物", "实际载重",
            "额定载重", "水位", "值班人", "天气", "顶推情况",
            "预告时间", "补充时间", "起挂时间", "半杆时间",
            "进漕时间", "出漕时间", "通过时间(分)", "备注", "操作"
        ])

        # 设置列宽
        header = self.table.horizontalHeader()
        header.setSectionResizeMode(QHeaderView.ResizeToContents)
        header.setStretchLastSection(True)

        # 启用排序
        self.table.setSortingEnabled(True)

        layout.addWidget(self.table)

        # 关闭按钮
        btn_layout = QHBoxLayout()
        close_btn = QPushButton("关闭")
        close_btn.clicked.connect(self.accept)
        btn_layout.addStretch()
        btn_layout.addWidget(close_btn)
        layout.addLayout(btn_layout)

    def load_records(self):
        """加载记录"""
        date_str = self.date_edit.date().toString("yyyy-MM-dd")
        records = self.record_manager.get_records_by_date(date_str)

        # 过滤状态
        filter_status = self.status_filter.currentText()
        if filter_status == "进行中":
            records = [r for r in records if r.get('is_active', 0) == 1]
        elif filter_status == "已完成":
            records = [r for r in records if r.get('is_active', 0) == 0]

        self.table.setRowCount(len(records))

        for i, record in enumerate(records):
            self.add_record_to_table(i, record)

        # 更新统计
        self.update_stats(records)

    def add_record_to_table(self, row, record):
        """添加记录到表格"""
        # 基本字段
        self.table.setItem(row, 0, QTableWidgetItem(record.get('mmsi', '')))
        self.table.setItem(row, 1, QTableWidgetItem(record.get('name', '')))

        direction_item = QTableWidgetItem("上行" if record.get('direction') == 'up' else "下行")
        if record.get('direction') == 'up':
            direction_item.setBackground(Qt.green)
        else:
            direction_item.setBackground(Qt.blue)
        self.table.setItem(row, 2, direction_item)

        self.table.setItem(row, 3, QTableWidgetItem(str(record.get('tug_count', 0))))
        self.table.setItem(row, 4, QTableWidgetItem(record.get('cargo', '')))
        self.table.setItem(row, 5, QTableWidgetItem(str(record.get('actual_load', 0))))
        self.table.setItem(row, 6, QTableWidgetItem(str(record.get('rated_load', 0))))
        self.table.setItem(row, 7, QTableWidgetItem(str(record.get('water_level', 0))))
        self.table.setItem(row, 8, QTableWidgetItem(record.get('duty_person', '')))
        self.table.setItem(row, 9, QTableWidgetItem(record.get('weather', '')))
        self.table.setItem(row, 10, QTableWidgetItem(record.get('pushing_status', '')))

        # 时间字段
        self.table.setItem(row, 11, QTableWidgetItem(record.get('forecast_time_str', '')))
        self.table.setItem(row, 12, QTableWidgetItem(record.get('supplement_time_str', '')))
        self.table.setItem(row, 13, QTableWidgetItem(record.get('start_hang_time_str', '')))
        self.table.setItem(row, 14, QTableWidgetItem(record.get('half_pole_time_str', '')))
        self.table.setItem(row, 15, QTableWidgetItem(record.get('enter_channel_time_str', '')))
        self.table.setItem(row, 16, QTableWidgetItem(record.get('exit_channel_time_str', '')))

        passage_time = record.get('passage_time', 0)
        self.table.setItem(row, 17, QTableWidgetItem(f"{passage_time:.1f}" if passage_time > 0 else ""))

        self.table.setItem(row, 18, QTableWidgetItem(record.get('remark', '')))

        # 编辑按钮
        edit_btn = QPushButton("编辑")
        edit_btn.clicked.connect(lambda checked, r=record: self.edit_record(r))
        self.table.setCellWidget(row, 19, edit_btn)

    def edit_record(self, record):
        """编辑记录"""
        dialog = RecordEditDialog(record, self)
        if dialog.exec_():
            updated_record = dialog.get_updated_record()
            # 更新记录
            self.record_manager.update_record(
                record['mmsi'],
                **updated_record
            )
            self.load_records()
            self.record_saved.emit(updated_record)

    def update_stats(self, records):
        """更新统计信息"""
        total = len(records)
        completed = len([r for r in records if r.get('is_complete')])
        active = total - completed
        avg_time = 0
        completed_records = [r for r in records if r.get('is_complete') and r.get('passage_time', 0) > 0]
        if completed_records:
            avg_time = sum(r.get('passage_time', 0) for r in completed_records) / len(completed_records)

        self.stats_label.setText(
            f"总计: {total} 艘 | 进行中: {active} 艘 | 已完成: {completed} 艘 | 平均通过时间: {avg_time:.1f} 分钟"
        )

    def on_date_changed(self):
        """日期改变"""
        self.load_records()

    def cleanup_records(self):
        """清理过期记录"""
        result = QMessageBox.question(
            self, "确认清理",
            f"将清理超过 {self.record_manager.auto_cleanup_days} 天的历史记录，是否继续？",
            QMessageBox.Yes | QMessageBox.No
        )
        if result == QMessageBox.Yes:
            cleaned = self.record_manager.auto_cleanup()
            QMessageBox.information(self, "清理完成", f"已清理 {cleaned} 条过期记录")
            self.load_records()

    def export_records(self):
        """导出记录"""
        from PyQt5.QtWidgets import QFileDialog
        import csv

        file_path, _ = QFileDialog.getSaveFileName(self, "导出记录", "", "CSV文件 (*.csv)")
        if file_path:
            records = self.record_manager.get_records_by_date(
                self.date_edit.date().toString("yyyy-MM-dd")
            )

            with open(file_path, 'w', newline='', encoding='utf-8-sig') as f:
                writer = csv.writer(f)
                # 写入表头
                headers = ["MMSI", "船名", "方向", "拖驳数", "货物", "实际载重", "额定载重",
                           "水位", "值班人", "天气", "顶推情况", "预告时间", "补充时间",
                           "起挂时间", "半杆时间", "进漕时间", "出漕时间", "通过时间(分)", "备注"]
                writer.writerow(headers)

                for r in records:
                    row = [
                        r.get('mmsi', ''), r.get('name', ''),
                        "上行" if r.get('direction') == 'up' else "下行",
                        r.get('tug_count', 0), r.get('cargo', ''), r.get('actual_load', 0),
                        r.get('rated_load', 0), r.get('water_level', 0), r.get('duty_person', ''),
                        r.get('weather', ''), r.get('pushing_status', ''),
                        r.get('forecast_time_str', ''), r.get('supplement_time_str', ''),
                        r.get('start_hang_time_str', ''), r.get('half_pole_time_str', ''),
                        r.get('enter_channel_time_str', ''), r.get('exit_channel_time_str', ''),
                        f"{r.get('passage_time', 0):.1f}" if r.get('passage_time', 0) > 0 else "",
                        r.get('remark', '')
                    ]
                    writer.writerow(row)

            QMessageBox.information(self, "导出成功", f"已导出到 {file_path}")


class RecordEditDialog(QDialog):
    """记录编辑对话框"""

    def __init__(self, record, parent=None):
        super().__init__(parent)
        self.record = record
        self.init_ui()

    def init_ui(self):
        """初始化界面"""
        self.setWindowTitle(f"编辑通行记录 - {self.record.get('name', '')}")
        self.setFixedSize(500, 600)

        layout = QVBoxLayout(self)

        # 表单布局
        form = QFormLayout()

        # 基本信息
        self.name_edit = QLineEdit(self.record.get('name', ''))
        form.addRow("船名:", self.name_edit)

        self.mmsi_edit = QLineEdit(self.record.get('mmsi', ''))
        self.mmsi_edit.setReadOnly(True)
        form.addRow("MMSI:", self.mmsi_edit)

        self.direction_combo = QComboBox()
        self.direction_combo.addItems(["上行", "下行"])
        self.direction_combo.setCurrentText("上行" if self.record.get('direction') == 'up' else "下行")
        form.addRow("方向:", self.direction_combo)

        self.tug_count_spin = QSpinBox()
        self.tug_count_spin.setRange(0, 100)
        self.tug_count_spin.setValue(self.record.get('tug_count', 0))
        form.addRow("拖驳数:", self.tug_count_spin)

        self.cargo_edit = QLineEdit(self.record.get('cargo', ''))
        form.addRow("货物:", self.cargo_edit)

        self.actual_load_spin = QDoubleSpinBox()
        self.actual_load_spin.setRange(0, 100000)
        self.actual_load_spin.setValue(self.record.get('actual_load', 0))
        form.addRow("实际载重(吨):", self.actual_load_spin)

        self.rated_load_spin = QDoubleSpinBox()
        self.rated_load_spin.setRange(0, 100000)
        self.rated_load_spin.setValue(self.record.get('rated_load', 0))
        form.addRow("额定载重(吨):", self.rated_load_spin)

        self.water_level_spin = QDoubleSpinBox()
        self.water_level_spin.setRange(0, 100)
        self.water_level_spin.setValue(self.record.get('water_level', 0))
        form.addRow("水位(米):", self.water_level_spin)

        self.duty_person_edit = QLineEdit(self.record.get('duty_person', ''))
        form.addRow("值班人:", self.duty_person_edit)

        self.weather_combo = QComboBox()
        self.weather_combo.addItems(["晴", "雨", "阴", "霾", "雾"])
        self.weather_combo.setCurrentText(self.record.get('weather', '晴'))
        form.addRow("天气:", self.weather_combo)

        self.pushing_combo = QComboBox()
        self.pushing_combo.addItems(["", "顶推", "调头等待"])
        self.pushing_combo.setCurrentText(self.record.get('pushing_status', ''))
        form.addRow("顶推情况:", self.pushing_combo)

        self.remark_edit = QTextEdit()
        self.remark_edit.setPlainText(self.record.get('remark', ''))
        self.remark_edit.setMaximumHeight(80)
        form.addRow("备注:", self.remark_edit)

        layout.addLayout(form)

        # 按钮
        btn_layout = QHBoxLayout()
        save_btn = QPushButton("保存")
        save_btn.clicked.connect(self.accept)
        cancel_btn = QPushButton("取消")
        cancel_btn.clicked.connect(self.reject)
        btn_layout.addStretch()
        btn_layout.addWidget(save_btn)
        btn_layout.addWidget(cancel_btn)
        layout.addLayout(btn_layout)

    def get_updated_record(self):
        """获取更新后的记录"""
        return {
            'name': self.name_edit.text(),
            'direction': 'up' if self.direction_combo.currentText() == "上行" else 'down',
            'tug_count': self.tug_count_spin.value(),
            'cargo': self.cargo_edit.text(),
            'actual_load': self.actual_load_spin.value(),
            'rated_load': self.rated_load_spin.value(),
            'water_level': self.water_level_spin.value(),
            'duty_person': self.duty_person_edit.text(),
            'weather': self.weather_combo.currentText(),
            'pushing_status': self.pushing_combo.currentText(),
            'remark': self.remark_edit.toPlainText()
        }