import sqlite3
from typing import Any, List, Dict, Optional, Tuple, Union
from PyQt5.QtCore import QObject, pyqtSignal
from datetime import datetime




class SQLiteTableManager(QObject):
    """SQLite表格管理器 - 专门用于表格字段的增删改查操作"""

    # 信号定义
    operation_completed = pyqtSignal(str, bool)  # (操作类型, 是否成功)
    data_changed = pyqtSignal(str)  # 表名
    error_occurred = pyqtSignal(str)

    def __init__(self, db_path: str = "app_data.db", parent=None):
        super().__init__(parent)
        self.db_path = db_path
        self.connection = None
        self.cursor = None
        self.is_connected = False

    # ========== 基础连接方法 ==========
    def connect(self) -> bool:
        """连接到数据库"""
        try:
            self.connection = sqlite3.connect(self.db_path)
            self.connection.row_factory = sqlite3.Row
            self.cursor = self.connection.cursor()
            self.is_connected = True
            self.execute_query("PRAGMA foreign_keys = ON")
            print(f"✓ 数据库连接成功: {self.db_path}")
            return True
        except sqlite3.Error as e:
            self.error_occurred.emit(f"连接失败: {e}")
            return False

    def disconnect(self):
        """断开数据库连接"""
        if self.cursor:
            self.cursor.close()
        if self.connection:
            self.connection.close()
        self.is_connected = False

    def ensure_connected(self):
        """确保数据库已连接"""
        if not self.is_connected:
            self.connect()

    def execute_query(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """执行SQL查询"""
        self.ensure_connected()
        try:
            return self.cursor.execute(query, params)
        except sqlite3.Error as e:
            self.error_occurred.emit(f"SQL执行错误: {e}\n查询: {query}")
            raise

    # ========== 表格结构操作 ==========
    def get_table_columns(self, table_name: str) -> List[Dict]:
        """获取表格的所有字段信息"""
        query = f"PRAGMA table_info({table_name})"
        return [dict(row) for row in self.execute_query(query).fetchall()]

    def get_column_names(self, table_name: str) -> List[str]:
        """获取表格的所有字段名"""
        columns = self.get_table_columns(table_name)
        return [col['name'] for col in columns]



    def update_fields_by_condition(self, table_name: str,
                                   updates: Dict[str, Any],
                                   conditions: Dict[str, Any] = None,
                                   operator: str = "AND") -> bool:
        """
        根据多个条件更新多个记录的字段

        Args:
            table_name: 表名
            updates: 更新字段字典 {字段名: 新值}
            conditions: 条件字典 {字段名: 条件值}，为None时更新所有记录
            operator: 条件连接符 (AND 或 OR)
        """
        try:
            if not updates:
                return True

            # 验证字段是否存在
            columns = self.get_column_names(table_name)
            for field in updates.keys():
                if field not in columns:
                    self.error_occurred.emit(f"字段 {field} 不存在于表 {table_name}")
                    return False

            # 构建SET子句
            set_clause = ', '.join([f"{k} = ?" for k in updates.keys()])
            values = tuple(updates.values())

            # 构建WHERE子句
            sql = f"UPDATE {table_name} SET {set_clause}"

            if conditions:
                where_clause = f' {operator} '.join([f"{k} = ?" for k in conditions.keys()])
                sql += f" WHERE {where_clause}"
                values += tuple(conditions.values())

            # 执行更新
            self.execute_query(sql, values)
            self.connection.commit()

            affected_rows = self.cursor.rowcount
            print(f"✓ 已更新表 {table_name} 的 {affected_rows} 条记录")
            # self.operation_completed.emit("UPDATE_FIELDS", True)
            # self.data_changed.emit(table_name)

            return True

        except sqlite3.Error as e:
            if self.connection:
                self.connection.rollback()
            self.error_occurred.emit(f"更新失败: {e}")
            self.operation_completed.emit("UPDATE_FIELDS", False)
            return False

    def update_by_single_condition(self, table_name: str,
                                   updates: Dict[str, Any],
                                   condition_field: str,
                                   condition_value: Any) -> bool:
        """
        根据单个条件更新字段

        Args:
            table_name: 表名
            updates: 更新字段字典 {字段名: 新值}
            condition_field: 条件字段名
            condition_value: 条件值
        """
        conditions = {condition_field: condition_value}
        return self.update_fields_by_condition(table_name, updates, conditions)

    def update_single_field(self, table_name: str,
                            field_name: str,
                            new_value: Any,
                            conditions: Dict[str, Any] = None) -> bool:
        """
        更新单个字段

        Args:
            table_name: 表名
            field_name: 要更新的字段名
            new_value: 新值
            conditions: 条件字典，为None时更新所有记录
        """
        updates = {field_name: new_value}
        return self.update_fields_by_condition(table_name, updates, conditions)

    def delete_record(self, table_name: str, coloum: Any,
                     value) -> bool:
        """
        删除指定记录

        Args:
            table_name: 表名
            coloum: 字段名
            value: 字段名的值
        """
        try:
            sql = f"DELETE FROM {table_name} WHERE {coloum} = ?"
            self.execute_query(sql, (value,))
            self.connection.commit()

            print(f"✓ 已删除表 {table_name} 的记录 {coloum}={value} ")
            # self.operation_completed.emit("DELETE_RECORD", True)
            # self.data_changed.emit(table_name)
            return True

        except sqlite3.Error as e:
            self.connection.rollback()
            self.error_occurred.emit(f"删除记录失败: {e}")
            self.operation_completed.emit("DELETE_RECORD", False)
            return False

    def delete_by_conditions(self, table_name: str,
                             conditions: Dict[str, Any],
                             operator: str = "AND") -> bool:
        """
        根据多个条件删除记录

        Args:
            table_name: 表名
            conditions: 条件字典 {字段名: 值}
            operator: 条件连接符 AND/OR
        """
        try:
            if not conditions:
                self.error_occurred.emit("请提供删除条件")
                return False

            # 验证字段是否存在
            columns = self.get_column_names(table_name)
            for column in conditions.keys():
                if column not in columns:
                    self.error_occurred.emit(f"字段 {column} 不存在于表 {table_name}")
                    return False

            # 构建WHERE子句
            where_items = []
            values = []

            for column, value in conditions.items():
                where_items.append(f"{column} = ?")
                values.append(value)

            where_clause = f" {operator} ".join(where_items)

            # 执行删除
            sql = f"DELETE FROM {table_name} WHERE {where_clause}"
            self.execute_query(sql, tuple(values))
            self.connection.commit()

            affected_rows = self.cursor.rowcount
            print(f"✓ 已删除表 {table_name} 中满足条件的记录，影响行数: {affected_rows}")

            self.operation_completed.emit("DELETE_BY_CONDITIONS", True)
            self.data_changed.emit(table_name)
            return True

        except sqlite3.Error as e:
            self.rollback()
            self.error_occurred.emit(f"删除失败: {e}")
            self.operation_completed.emit("DELETE_BY_CONDITIONS", False)
            return False

    def delete_all(self, table_name: str) -> bool:
        """删除表中所有记录"""
        try:
            sql = f"DELETE FROM {table_name}"
            self.execute_query(sql)
            self.connection.commit()

            affected_rows = self.cursor.rowcount
            print(f"✓ 已删除表 {table_name} 中的所有记录，影响行数: {affected_rows}")

            self.operation_completed.emit("DELETE_ALL", True)
            self.data_changed.emit(table_name)
            return True

        except sqlite3.Error as e:
            self.connection.rollback()
            self.error_occurred.emit(f"删除所有记录失败: {e}")
            self.operation_completed.emit("DELETE_ALL", False)
            return False

    def insert_record(self, table_name: str, data: Dict[str, Any]) -> int:
        """
        插入新记录

        Args:
            table_name: 表名
            data: 数据字典 {字段名: 值}

        Returns:
            int: 新插入记录的ID，失败返回-1
        """
        try:
            # 验证字段是否存在
            columns = self.get_column_names(table_name)
            for field in data.keys():
                if field not in columns:
                    self.error_occurred.emit(f"字段 {field} 不存在于表 {table_name}")
                    return -1

            # 构建INSERT语句
            fields = ', '.join(data.keys())
            placeholders = ', '.join(['?'] * len(data))

            sql = f"INSERT INTO {table_name} ({fields}) VALUES ({placeholders})"

            self.execute_query(sql, tuple(data.values()))
            self.connection.commit()

            new_id = self.cursor.lastrowid

            print(f"✓ 已向表 {table_name} 插入新记录，ID: {new_id}")
            # self.operation_completed.emit("INSERT_RECORD", True)
            # self.data_changed.emit(table_name)

            return new_id

        except sqlite3.Error as e:
            self.connection.rollback()
            self.error_occurred.emit(f"插入记录失败: {e}")
            self.operation_completed.emit("INSERT_RECORD", False)
            return -1


    # ========== 查询方法 ==========
    def fetch_all(self, query: str, params: tuple = ()) -> List[Dict]:
        """获取所有记录"""
        cursor = self.execute_query(query, params)
        return [dict(row) for row in cursor.fetchall()]

    def fetch_one(self, query: str, params: tuple = ()) -> Optional[Dict]:
        """获取单条记录"""
        cursor = self.execute_query(query, params)
        row = cursor.fetchone()
        return dict(row) if row else None


    def get_all_records(self, table_name: str,
                        order_by: str = None) -> List[Dict]:
        """获取表的所有记录"""
        sql = f"SELECT * FROM {table_name}"
        if order_by:
            sql += f" ORDER BY {order_by}"
        return self.fetch_all(sql)

    def search_records(self, table_name: str, conditions: Dict[str, Any],
                       operator: str = "AND") -> List[Dict]:
        """
        根据条件搜索记录

        Args:
            table_name: 表名
            conditions: 条件字典 {字段名: 值}
            operator: 条件连接符 (AND 或 OR)
        """
        if not conditions:
            return self.get_all_records(table_name)

        where_clause = f' {operator} '.join([f"{k} = ?" for k in conditions.keys()])
        sql = f"SELECT * FROM {table_name} WHERE {where_clause}"

        return self.fetch_all(sql, tuple(conditions.values()))


    # ========== 工具方法 ==========
    def create_table_if_not_exists(self, table_name: str,
                                   columns: Dict[str, str]) -> bool:
        """如果表不存在则创建表"""
        try:
            # 检查表是否存在
            sql_check = """
                        SELECT name \
                        FROM sqlite_master
                        WHERE type = 'table' \
                          AND name = ? \
                        """
            result = self.fetch_one(sql_check, (table_name,))

            if result:
                print(f"表 {table_name} 已存在")
                return True

            # 创建表
            column_defs = [f"{name} {type_}" for name, type_ in columns.items()]
            create_sql = f"CREATE TABLE {table_name} ({', '.join(column_defs)})"

            self.execute_query(create_sql)
            self.connection.commit()

            print(f"✓ 已创建表 {table_name}")
            return True

        except sqlite3.Error as e:
            self.error_occurred.emit(f"创建表失败: {e}")
            return False



    # ========== 上下文管理器和析构函数 ==========
    def __enter__(self):
        self.connect()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.disconnect()

    # def __del__(self):
    #     self.disconnect()


# ========== 使用示例 ==========
if __name__ == "__main__":
    # 创建管理器实例
    db_manager = SQLiteTableManager("test.db")

    # 连接到数据库
    if db_manager.connect():
        river = db_manager.search_records("Reaches", {"ReachCode": 35})
        print(river)
        # 使用 split() 分割字符串
        longitude = river[0].get("UpBordLine")
        print(f"经度: {longitude}")

        TABLE_SCHEMA = {
            "id": "INTEGER PRIMARY KEY AUTOINCREMENT",
            "mmsi": "TEXT NOT NULL",
            "name": "TEXT NOT NULL",
            "direction": "TEXT NOT NULL",  # 'up' 或 'down'
            "tug_count": "INTEGER DEFAULT 0",
            "cargo": "TEXT",
            "actual_load": "REAL DEFAULT 0",
            "rated_load": "REAL DEFAULT 0",
            "water_level": "REAL DEFAULT 0",
            "duty_person": "TEXT",
            "weather": "TEXT",
            "pushing_status": "TEXT",
            "remark": "TEXT",
            "forecast_time": "INTEGER DEFAULT 0",  # 预告时间戳
            "supplement_time": "INTEGER DEFAULT 0",  # 补充时间戳
            "start_hang_time": "INTEGER DEFAULT 0",  # 起挂时间戳
            "half_pole_time": "INTEGER DEFAULT 0",  # 半杆时间戳
            "enter_channel_time": "INTEGER DEFAULT 0",  # 进漕时间戳
            "exit_channel_time": "INTEGER DEFAULT 0",  # 出漕时间戳
            "create_time": "INTEGER DEFAULT 0",  # 创建时间戳
            "last_update": "INTEGER DEFAULT 0",  # 最后更新时间戳
            "is_active": "INTEGER DEFAULT 1"  # 是否活跃记录（1=活跃，0=已完成）
        }
        # 1. 创建示例表
        db_manager.create_table_if_not_exists("CommandRecord", TABLE_SCHEMA)
        #
        # # 2. 插入测试数据
        # test_data = [
        #     {"name": "张三", "age": 30, "department": "技术部", "salary": 8000.0, "hire_date": "2020-01-15"},
        #     {"name": "李四", "age": 28, "department": "销售部", "salary": 7000.0, "hire_date": "2021-03-20"},
        #     {"name": "王五", "age": 35, "department": "管理部", "salary": 10000.0, "hire_date": "2019-08-10"}
        # ]
        #
        # for data in test_data:
        #     db_manager.insert_record("employees", data)
        #
        # print("初始数据:")
        # for emp in db_manager.get_all_records("employees"):
        #     print(emp)
        #
        # print("\n" + "=" * 50 + "\n")
        #
        # # 3. 更新单个字段
        # db_manager.update_single_field("employees", 'age', "31", {'name':'张三'})
        #
        # # 4. 批量更新多个字段
        # db_manager.update_by_single_condition("employees",{
        #     "department": "市场部",
        #     "salary": 7500.0
        # },'id',3)
        #
        #
        #
        # # 7. 删除记录
        # db_manager.delete_record("employees", 'name','李四')
        #
        # # 8. 搜索记录
        # print("搜索部门为'市场部'的员工:")
        # results = db_manager.search_records("employees", {"department": "市场部"})
        # for emp in results:
        #     print(emp)
        #
        # # 9. 查看表结构
        # print("\n表结构:")
        # columns = db_manager.get_table_columns("employees")
        # for col in columns:
        #     print(f"  {col['name']}: {col['type']} {'NOT NULL' if col['notnull'] else ''}")
        #
        # # 10. 重命名字段 (注意: SQLite需要特殊处理)
        # # db_manager.rename_column("employees", "age", "employee_age")
        #
        # # 11. 删除字段 (注意: SQLite需要特殊处理)
        # # db_manager.drop_column("employees", "hire_date")
        #
        # results=db_manager.search_records("Internet", {"NetType": "内网"})
        # if results:
        #     for result in results:
        #         print(result)
        #
        # # 断开连接
        # db_manager.disconnect()