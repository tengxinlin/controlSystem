# shift_dialog.py
import requests
from PyQt5.QtWidgets import (QDialog, QVBoxLayout, QHBoxLayout, QLabel,
                             QLineEdit, QPushButton, QTreeWidget, QTreeWidgetItem,
                             QDateTimeEdit, QTextEdit, QMessageBox, QFormLayout,
                             QGroupBox, QSplitter, QWidget, QFrame, QSizePolicy)
from PyQt5.QtCore import Qt, QDateTime, pyqtSignal
from PyQt5.QtGui import QFont, QIcon, QColor
import json

from flask import session


class ShiftDialog(QDialog):
    """值班交接班对话框"""

    # 信号：交接班成功
    shift_success = pyqtSignal(bool,str)  # session_id

    def __init__(self, api_service, config_mgr, reach_id: int, parent=None):
        """
        初始化值班交接班对话框

        Args:
            api_service: API服务实例
            config_mgr: 配置管理器
            reach_id: 控制河段ID
            parent: 父窗口
        """
        super().__init__(parent)
        self.api_service = api_service
        self.config_mgr = config_mgr
        self.reach_id = reach_id

        # 数据
        self.department_list = []
        self.user_list = []
        self.mast_worker = None  # 主接班人
        self.vice_worker = None  # 副接班人
        self.password_visible = False

        self.setWindowTitle("值班交接班")
        self.setFixedSize(1000, 600)
        # self.setWindowFlags(Qt.WindowCloseButtonHint | Qt.WindowMinimizeButtonHint)
        # 修改窗口标志：保持在最前面 + 独立窗口
        self.setWindowFlags(
            Qt.Window |  # 独立窗口
            Qt.WindowCloseButtonHint |
            Qt.WindowMinimizeButtonHint |
            Qt.WindowStaysOnTopHint  # 保持在最前面
        )

        # 设置模态（阻塞父窗口）
        self.setModal(True)

        self.init_ui()
        self.load_data()

    def init_ui(self):
        """初始化界面"""
        main_layout = QVBoxLayout(self)
        main_layout.setSpacing(2)
        main_layout.setContentsMargins(2, 1, 1, 1)

        # ========== 人员选择区域（左右分栏）==========
        personnel_layout = QHBoxLayout()
        personnel_layout.setSpacing(15)

        # 左侧：主接班人
        mast_group = QGroupBox("主接班人")
        mast_group.setStyleSheet(self.get_group_style("#3498db"))
        mast_layout = QVBoxLayout(mast_group)
        mast_layout.setContentsMargins(8, 8, 8, 8)

        # 选中的主接班人显示
        self.mast_display = QLabel("未选择")

        # self.mast_display.setAlignment(Qt.AlignCenter)
        mast_layout.addWidget(self.mast_display)

        # 树状结构（主接班人）
        self.mast_tree = QTreeWidget()
        self.mast_tree.setHeaderLabel("部门/人员")
        self.mast_tree.setStyleSheet(self.get_tree_style())
        self.mast_tree.setMinimumHeight(150)  # 关键：设置最小高度
        # self.mast_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)  # 关键：可扩展
        self.mast_tree.itemClicked.connect(lambda item, col: self.on_tree_item_clicked(item, "mast"))
        mast_layout.addWidget(self.mast_tree)

        personnel_layout.addWidget(mast_group, 1)

        # 右侧：副接班人
        vice_group = QGroupBox("副接班人")
        vice_group.setStyleSheet(self.get_group_style("#27ae60"))
        vice_layout = QVBoxLayout(vice_group)

        # 选中的副接班人显示
        self.vice_display = QLabel("未选择")

        # self.vice_display.setAlignment(Qt.AlignCenter)
        vice_layout.addWidget(self.vice_display)

        # 树状结构（副接班人）
        self.vice_tree = QTreeWidget()
        self.vice_tree.setHeaderLabel("部门/人员")
        self.vice_tree.setStyleSheet(self.get_tree_style())
        self.vice_tree.setMinimumHeight(200)  # 关键：设置最小高度
        # self.vice_tree.setSizePolicy(QSizePolicy.Expanding, QSizePolicy.Expanding)
        self.vice_tree.itemClicked.connect(lambda item, col: self.on_tree_item_clicked(item, "vice"))
        vice_layout.addWidget(self.vice_tree)

        personnel_layout.addWidget(vice_group, 1)

        main_layout.addLayout(personnel_layout, 2)

        # ========== 时间设置 ==========
        time_group = QGroupBox("值班时间")
        # time_group.setStyleSheet(self.get_group_style("#8e44ad"))
        time_layout = QHBoxLayout(time_group)
        time_layout.setSpacing(20)

        # 起始时间
        time_layout.addWidget(QLabel("起始时间:"))
        self.date_from_edit = QDateTimeEdit()
        self.date_from_edit.setCalendarPopup(True)
        self.date_from_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        self.date_from_edit.setDateTime(QDateTime.currentDateTime())
        self.date_from_edit.setStyleSheet(self.get_datetime_style())
        time_layout.addWidget(self.date_from_edit)

        # 结束时间
        time_layout.addWidget(QLabel("结束时间:"))
        self.date_to_edit = QDateTimeEdit()
        self.date_to_edit.setCalendarPopup(True)
        self.date_to_edit.setDisplayFormat("yyyy-MM-dd HH:mm:ss")
        # 默认结束时间为8小时后
        self.date_to_edit.setDateTime(QDateTime.currentDateTime().addSecs(8 * 3600))
        self.date_to_edit.setStyleSheet(self.get_datetime_style())
        time_layout.addWidget(self.date_to_edit)

        time_layout.addStretch()
        main_layout.addWidget(time_group)

        # ========== 备注 ==========
        memo_group = QGroupBox("接班备注")
        # memo_group.setStyleSheet(self.get_group_style("#e67e22"))
        memo_layout = QVBoxLayout(memo_group)

        self.memo_edit = QTextEdit()
        self.memo_edit.setPlaceholderText("请输入接班备注说明...")
        self.memo_edit.setMaximumHeight(80)
        # self.memo_edit.setStyleSheet("""
        #     QTextEdit {
        #         border: 1px solid #ced4da;
        #         border-radius: 4px;
        #         padding: 8px;
        #         font-size: 13px;
        #     }
        # """)
        memo_layout.addWidget(self.memo_edit)

        main_layout.addWidget(memo_group)

        # ========== 密码输入 ==========
        password_group = QGroupBox("身份验证")
        password_group.setStyleSheet(self.get_group_style("#e74c3c"))
        password_layout = QHBoxLayout(password_group)

        password_layout.addWidget(QLabel("登录密码:"))

        self.password_edit = QLineEdit()
        self.password_edit.setPlaceholderText("请输入登录密码")
        self.password_edit.setEchoMode(QLineEdit.Password)
        self.password_edit.setStyleSheet("""
            QLineEdit {
                padding: 8px 12px;
                border: 1px solid #ced4da;
                border-radius: 4px;
                font-size: 13px;
                min-width: 200px;
            }
            QLineEdit:focus {
                border-color: #3498db;
            }
        """)
        password_layout.addWidget(self.password_edit)

        # 显示/隐藏密码按钮
        self.show_pwd_btn = QPushButton("👁")
        self.show_pwd_btn.setFixedSize(35, 35)
        self.show_pwd_btn.setToolTip("显示/隐藏密码")
        self.show_pwd_btn.setStyleSheet("""
            QPushButton {
                background-color: #ecf0f1;
                border: 1px solid #ced4da;
                border-radius: 4px;
                font-size: 16px;
            }
            QPushButton:hover {
                background-color: #d5dbdb;
            }
        """)
        self.show_pwd_btn.clicked.connect(self.toggle_password_visibility)
        password_layout.addWidget(self.show_pwd_btn)

        # 提取密码按钮
        self.load_pwd_btn = QPushButton("📋 提取密码")
        self.load_pwd_btn.setToolTip("从配置文件提取密码")
        self.load_pwd_btn.setStyleSheet("""
            QPushButton {
                background-color: #3498db;
                color: white;
                border: none;
                border-radius: 4px;
                padding: 8px 15px;
                font-size: 13px;
            }
            QPushButton:hover {
                background-color: #2980b9;
            }
        """)
        self.load_pwd_btn.clicked.connect(self.load_password_from_config)
        password_layout.addWidget(self.load_pwd_btn)

        password_layout.addStretch()
        main_layout.addWidget(password_group)

        # ========== 底部按钮 ==========
        btn_layout = QHBoxLayout()
        btn_layout.setSpacing(15)

        self.submit_btn = QPushButton("确认交接班")
        self.submit_btn.setStyleSheet("""
            QPushButton {
                background-color: #27ae60;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 40px;
                font-size: 15px;
                font-weight: bold;
            }
            QPushButton:hover {
                background-color: #219a52;
            }
            QPushButton:disabled {
                background-color: #95a5a6;
            }
        """)
        self.submit_btn.clicked.connect(self.submit_shift)

        self.cancel_btn = QPushButton("取消")
        self.cancel_btn.setStyleSheet("""
            QPushButton {
                background-color: #95a5a6;
                color: white;
                border: none;
                border-radius: 6px;
                padding: 12px 40px;
                font-size: 15px;
            }
            QPushButton:hover {
                background-color: #7f8c8d;
            }
        """)
        self.cancel_btn.clicked.connect(self.reject)

        btn_layout.addStretch()
        btn_layout.addWidget(self.submit_btn)
        btn_layout.addWidget(self.cancel_btn)

        main_layout.addLayout(btn_layout)

    def get_group_style(self, color: str) -> str:
        """获取分组框样式"""
        return f"""
            QGroupBox {{
                font-weight: bold;
                font-size: 14px;
                border: 2px solid {color};
                border-radius: 8px;
                margin-top: 10px;
                padding-top: 15px;
            }}
            QGroupBox::title {{
                subcontrol-origin: margin;
                left: 15px;
                padding: 0 8px;
                color: {color};
            }}
        """

    def get_tree_style(self) -> str:
        """获取树状控件样式"""
        return """
            QTreeWidget {
                border: 1px solid #ced4da;
                border-radius: 4px;
                background-color: white;
                font-size: 18px;
                outline: none;
            }
            QTreeWidget::item {
                padding: 5px;
                height: 25px;
            }
            QTreeWidget::item:hover {
                background-color: #ecf0f1;
            }
            QTreeWidget::item:selected {
                background-color: #3498db;
                color: white;
            }
        """

    def get_datetime_style(self) -> str:
        """获取时间控件样式"""
        return """
            QDateTimeEdit {
                padding: 6px 10px;
                border: 10px solid #ced4da;
                border-radius: 4px;
                font-size: 18px;
                min-width: 160px;
            }
            QDateTimeEdit:focus {
                border-color: #3498db;
            }
        """

    # ========== 数据加载 ==========



    def build_mast_tree(self):
        """构建主接班人树状结构"""
        self.mast_tree.clear()
        self._build_tree(self.mast_tree, "mast")

    def build_vice_tree(self):
        """构建副接班人树状结构"""
        self.vice_tree.clear()
        self._build_tree(self.vice_tree, "vice")



    def load_data(self):
        """加载部门和人员数据"""
        try:
            print("=" * 50)
            print("开始加载部门和人员数据...")

            # 从 API 获取部门列表
            self.department_list = self.api_service.get_department_list()
            print(f"部门列表原始数据: {self.department_list}")

            if not self.department_list:
                QMessageBox.warning(self, "提示", "无法获取部门数据，请检查网络连接")
                return

            # 从 API 获取人员列表
            self.user_list = self.api_service.get_user_list()
            print(f"人员列表原始数据: {self.user_list}")

            if not self.user_list:
                QMessageBox.warning(self, "提示", "无法获取人员数据，请检查网络连接")
                return

            # 打印第一条数据的字段名，用于调试
            if self.department_list:
                print(f"部门数据字段: {list(self.department_list[0].keys())}")
            if self.user_list:
                print(f"人员数据字段: {list(self.user_list[0].keys())}")

            # 构建树状结构
            self.build_mast_tree()
            self.build_vice_tree()

            print(f"加载了 {len(self.department_list)} 个部门，{len(self.user_list)} 个人员")
            print("=" * 50)

        except Exception as e:
            print(f"加载数据失败: {e}")
            import traceback
            traceback.print_exc()
            QMessageBox.warning(self, "错误", f"加载数据失败: {e}")

    def _build_tree(self, tree_widget, tree_type: str):
        """
        构建树状结构
        """
        tree_widget.clear()

        # 兼容不同字段名
        def get_field(item, *field_names, default=''):
            """尝试多个字段名，返回第一个存在的值"""
            for name in field_names:
                if name in item and item[name] is not None:
                    return item[name]
            return default

        # 找出所有根部门（parentId == "0" 或 0 或 "0"）
        root_departments = []
        for d in self.department_list:
            parent_id = get_field(d, 'parentId', 'parentID', 'ParentId', 'parent_id', default='0')
            if str(parent_id) == "0":
                root_departments.append(d)

        print(f"找到 {len(root_departments)} 个根部门")

        if not root_departments:
            # 如果没有根部门，把所有部门都作为根节点显示
            print("警告: 没有找到根部门(parentId=0)，尝试显示所有部门")
            root_departments = self.department_list

        for root_dept in root_departments:
            dept_name = get_field(root_dept, 'name', 'Name', 'departmentName', 'deptName', default='未知部门')
            dept_id = get_field(root_dept, 'id', 'ID', 'Id', 'departmentId', default='')

            # 创建根节点
            root_item = QTreeWidgetItem(tree_widget)
            root_item.setText(0, f"📁 {dept_name}")
            root_item.setData(0, Qt.UserRole, {
                'type': 'department',
                'id': dept_id,
                'name': dept_name
            })

            # 递归添加子部门和人员
            self._add_children(root_item, dept_id, tree_type, get_field)

        # 展开所有节点
        tree_widget.expandAll()

        # 打印树节点数量用于调试
        print(f"树节点总数: {self._count_tree_items(tree_widget)}")

    def _add_children(self, parent_item, parent_id: str, tree_type: str, get_field):
        """
        递归添加子部门和人员
        """
        # 1. 添加子部门
        sub_departments = []
        for d in self.department_list:
            d_parent_id = get_field(d, 'parentId', 'parentID', 'ParentId', 'parent_id', default='')
            if str(d_parent_id) == str(parent_id):
                sub_departments.append(d)

        for sub_dept in sub_departments:
            dept_name = get_field(sub_dept, 'name', 'Name', 'departmentName', 'deptName', default='未知部门')
            dept_id = get_field(sub_dept, 'id', 'ID', 'Id', 'departmentId', default='')

            sub_item = QTreeWidgetItem(parent_item)
            sub_item.setText(0, f"📁 {dept_name}")
            sub_item.setData(0, Qt.UserRole, {
                'type': 'department',
                'id': dept_id,
                'name': dept_name
            })
            # 递归添加子节点
            self._add_children(sub_item, dept_id, tree_type, get_field)

        # 2. 添加该部门下的人员
        dept_users = []
        for u in self.user_list:
            u_dept_id = get_field(u, 'departmentId', 'DepartmentId', 'deptId', 'dept_id', 'departmentID', default='')
            if str(u_dept_id) == str(parent_id):
                dept_users.append(u)

        for user in dept_users:
            user_name = get_field(user, 'userName', 'UserName', 'username', 'name', default='未知人员')
            user_id = get_field(user, 'id', 'ID', 'Id', 'userId', default='')

            user_item = QTreeWidgetItem(parent_item)
            user_item.setText(0, f"👤 {user_name}")
            user_item.setData(0, Qt.UserRole, {
                'type': 'user',
                'id': user_id,
                'name': user_name,
                'departmentId': get_field(user, 'departmentId', 'DepartmentId', 'deptId', default='')
            })

    def _count_tree_items(self, tree_widget) -> int:
        """递归计算树节点总数"""
        count = 0

        def count_recursive(item):
            nonlocal count
            count += 1
            for i in range(item.childCount()):
                count_recursive(item.child(i))

        for i in range(tree_widget.topLevelItemCount()):
            count_recursive(tree_widget.topLevelItem(i))

        return count

    def _get_department_icon(self) -> QIcon:
        """获取部门图标"""
        # 可以用 QIcon 加载本地图标，暂时返回空
        return QIcon()

    def _get_user_icon(self) -> QIcon:
        """获取人员图标"""
        return QIcon()

    # ========== 事件处理 ==========

    def on_tree_item_clicked(self, item: QTreeWidgetItem, tree_type: str):
        """
        树节点点击事件

        Args:
            item: 点击的节点
            tree_type: 'mast' 或 'vice'
        """
        data = item.data(0, Qt.UserRole)
        if not data:
            return

        if data.get('type') == 'user':
            # 选择了人员
            user_name = data.get('name')
            user_id = data.get('id')

            if tree_type == 'mast':
                self.mast_worker = {'id': user_id, 'name': user_name}
                self.mast_display.setText(f"✅ {user_name}")
                # self.mast_display.setStyleSheet("""
                #     QLabel {
                #         font-size: 14px;
                #         font-weight: bold;
                #         color: #2ecc71;
                #         padding: 8px;
                #         background-color: #eafaf1;
                #         border-radius: 4px;
                #         border: 1px solid #27ae60;
                #         min-height: 20px;
                #     }
                # """)
            else:
                self.vice_worker = {'id': user_id, 'name': user_name}
                self.vice_display.setText(f"✅ {user_name}")
                # self.vice_display.setStyleSheet("""
                #     QLabel {
                #         font-size: 14px;
                #         font-weight: bold;
                #         color: #2ecc71;
                #         padding: 8px;
                #         background-color: #eafaf1;
                #         border-radius: 4px;
                #         border: 1px solid #27ae60;
                #         min-height: 20px;
                #     }
                # """)

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

    def load_password_from_config(self):
        """从配置文件提取密码"""
        try:
            # 从配置文件读取保存的密码
            password = self.config_mgr.get('login', 'last_password', default='')
            if password:
                self.password_edit.setText(password)
                # 显示一下确认已填充
                self.password_edit.setStyleSheet("""
                    QLineEdit {
                        padding: 8px 12px;
                        border: 2px solid #27ae60;
                        border-radius: 4px;
                        font-size: 13px;
                        min-width: 200px;
                        background-color: #eafaf1;
                    }
                """)
                # 2秒后恢复样式
                from PyQt5.QtCore import QTimer
                QTimer.singleShot(2000, lambda: self.password_edit.setStyleSheet("""
                    QLineEdit {
                        padding: 8px 12px;
                        border: 1px solid #ced4da;
                        border-radius: 4px;
                        font-size: 13px;
                        min-width: 200px;
                    }
                    QLineEdit:focus {
                        border-color: #3498db;
                    }
                """))
                print("已从配置文件提取密码")
            else:
                QMessageBox.warning(self, "提示", "配置文件中没有保存的密码，请手动输入")
        except Exception as e:
            QMessageBox.warning(self, "错误", f"提取密码失败: {e}")

    # ========== 提交交接班 ==========

    def validate_input(self) -> bool:
        """验证输入"""
        if not self.mast_worker:
            QMessageBox.warning(self, "提示", "请选择主接班人")
            return False

        if not self.vice_worker:
            QMessageBox.warning(self, "提示", "请选择副接班人")
            return False

        if self.mast_worker['id'] == self.vice_worker['id']:
            QMessageBox.warning(self, "提示", "主接班人和副接班人不能是同一个人")
            return False

        # 验证时间
        date_from = self.date_from_edit.dateTime().toSecsSinceEpoch()
        date_to = self.date_to_edit.dateTime().toSecsSinceEpoch()

        if date_to <= date_from:
            QMessageBox.warning(self, "提示", "结束时间必须晚于起始时间")
            return False

        # 验证密码
        password = self.password_edit.text().strip()
        if not password:
            QMessageBox.warning(self, "提示", "请输入登录密码")
            self.password_edit.setFocus()
            return False

        return True

    def submit_shift(self):
        """提交交接班"""
        if not self.validate_input():
            return

        # 禁用提交按钮
        self.submit_btn.setEnabled(False)
        self.submit_btn.setText("正在提交...")

        try:
            # 准备参数
            mast_worker = self.mast_worker['name']
            vice_worker = self.vice_worker['name']
            password = self.password_edit.text().strip()

            # 时间格式化
            date_from = self.date_from_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss")
            date_to = self.date_to_edit.dateTime().toString("yyyy-MM-dd HH:mm:ss")

            work_memo = self.memo_edit.toPlainText().strip()
            reach_id = self.reach_id

            # 调用 API
            print(f"提交交接班:")
            print(f"  主接班人: {mast_worker}")
            print(f"  副接班人: {vice_worker}")
            print(f"  起始时间: {date_from}")
            print(f"  结束时间: {date_to}")
            print(f"  备注: {work_memo}")
            print(f"  河段ID: {reach_id}")

            result = self.api_service.record_shift_infor(
                mast_worker=mast_worker,
                password=password,
                vice_worker=vice_worker,
                date_from=date_from,
                date_to=date_to,
                work_memo=work_memo,
                reach_id=reach_id
            )

            if result and result.get('errorMsg')!='':
                error_msg = result.get('errorMsg', '交接班失败') if result else '交接班失败'
                QMessageBox.warning(self, "失败", error_msg)

            else:
                QMessageBox.information(self, "成功",
                                        f"交接班成功！\n主接班人: {mast_worker}\n副接班人: {vice_worker}")
                session=result["data"]["sessionId"]
                self.shift_success.emit(True,session)
                # self.accept()

        except Exception as e:
            QMessageBox.warning(self, "错误", f"交接班异常: {e}")
            print(f"交接班异常: {e}")
            import traceback
            traceback.print_exc()

        finally:
            # 恢复提交按钮
            self.submit_btn.setEnabled(True)
            self.submit_btn.setText("确认交接班")