# command_record_db.py
from sqlite3Manager import SQLiteTableManager
from typing import List, Dict, Optional
import time


class CommandRecordDB:
    """通行记录数据库操作类"""

    # 表名
    TABLE_NAME = "CommandRecord"

    # 表结构定义
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

    def __init__(self, db_manager: SQLiteTableManager):
        self.db = db_manager
        self._init_table()

    def _init_table(self):
        """初始化表"""
        self.db.create_table_if_not_exists(self.TABLE_NAME, self.TABLE_SCHEMA)
        print(f"✓ 通行记录表初始化完成")

    def insert(self, record: Dict) -> int:
        """
        插入新记录

        Args:
            record: 记录字典，包含字段名和值

        Returns:
            int: 插入记录的ID
        """
        # 添加时间戳
        current_time = int(time.time())
        if 'create_time' not in record:
            record['create_time'] = current_time
        record['last_update'] = current_time
        record['is_active'] = 1

        return self.db.insert_record(self.TABLE_NAME, record)

    def update(self, record_id: int, updates: Dict) -> bool:
        """
        更新记录

        Args:
            record_id: 记录ID
            updates: 要更新的字段字典

        Returns:
            bool: 是否成功
        """
        # 添加更新时间戳
        updates['last_update'] = int(time.time())

        return self.db.update_by_single_condition(
            self.TABLE_NAME,
            updates,
            'id',
            record_id
        )

    def update_by_mmsi(self, mmsi: str, updates: Dict) -> bool:
        """
        根据MMSI更新记录

        Args:
            mmsi: 船舶MMSI
            updates: 要更新的字段字典
        """
        updates['last_update'] = int(time.time())
        return self.db.update_by_single_condition(
            self.TABLE_NAME,
            updates,
            'mmsi',
            mmsi
        )

    def get_active_by_mmsi(self, mmsi: str) -> Optional[Dict]:
        """
        获取船舶的活跃记录

        Args:
            mmsi: 船舶MMSI

        Returns:
            Dict: 记录字典，如果没有返回None
        """
        conditions = {
            'MMSI': mmsi,
            'is_active': 1
        }
        results = self.db.search_records(self.TABLE_NAME, conditions)
        return results[0] if results else None

    def get_records_by_date(self, date_str: str) -> List[Dict]:
        """
        获取指定日期的记录

        Args:
            date_str: 日期字符串，格式 'YYYY-MM-DD'
        """
        from datetime import datetime
        # 计算当天开始和结束的时间戳
        start_date = datetime.strptime(date_str, '%Y-%m-%d')
        start_timestamp = int(start_date.timestamp())
        end_timestamp = int((start_date.replace(hour=23, minute=59, second=59)).timestamp())

        # 查询当天的记录（包括活跃和非活跃）
        query = f"""
            SELECT * FROM {self.TABLE_NAME} 
            WHERE create_time BETWEEN ? AND ?
            ORDER BY create_time DESC
        """
        return self.db.fetch_all(query, (start_timestamp, end_timestamp))

    def get_today_records(self) -> List[Dict]:
        """获取今天的记录"""
        from datetime import datetime
        today = datetime.now().strftime('%Y-%m-%d')
        return self.get_records_by_date(today)

    def get_active_records(self) -> List[Dict]:
        """获取所有活跃记录（未完成的）"""
        return self.db.search_records(self.TABLE_NAME, {'is_active': 1})

    def get_completed_records(self, limit: int = 100) -> List[Dict]:
        """获取已完成的记录"""
        query = f"""
            SELECT * FROM {self.TABLE_NAME} 
            WHERE is_active = 0 
            ORDER BY create_time DESC 
            LIMIT ?
        """
        return self.db.fetch_all(query, (limit,))

    def get_records_by_mmsi(self, mmsi: str) -> List[Dict]:
        """获取指定船舶的所有记录"""
        return self.db.search_records(self.TABLE_NAME, {'mmsi': mmsi})

    def complete_record(self, mmsi: str, exit_time: int = None) -> bool:
        """
        完成记录（设置出漕时间和is_active=0）

        Args:
            mmsi: 船舶MMSI
            exit_time: 出漕时间戳，默认当前时间
        """
        updates = {
            'exit_channel_time': exit_time or int(time.time()),
            'is_active': 0,
            'last_update': int(time.time())
        }
        return self.update_by_mmsi(mmsi, updates)

    def delete_record(self, record_id: int) -> bool:
        """删除记录"""
        return self.db.delete_record(self.TABLE_NAME, 'id', record_id)

    def delete_by_mmsi(self, mmsi: str) -> bool:
        """删除船舶的所有记录"""
        return self.db.delete_record(self.TABLE_NAME, 'mmsi', mmsi)

    def delete_expired_records(self, days: int = 7) -> int:
        """
        删除过期的记录

        Args:
            days: 保留天数，超过此天数的记录会被删除

        Returns:
            int: 删除的记录数
        """
        from datetime import datetime, timedelta
        cutoff_date = datetime.now() - timedelta(days=days)
        cutoff_timestamp = int(cutoff_date.timestamp())

        query = f"""
            DELETE FROM {self.TABLE_NAME} 
            WHERE is_active = 0 AND create_time < ?
            RETURNING id
        """
        try:
            self.db.execute_query(query, (cutoff_timestamp,))
            self.db.connection.commit()
            deleted_count = self.db.cursor.rowcount
            print(f"✓ 删除了 {deleted_count} 条过期记录")
            return deleted_count
        except Exception as e:
            print(f"删除过期记录失败: {e}")
            return 0

    def get_statistics(self, date_str: str = None) -> Dict:
        """
        获取统计信息

        Args:
            date_str: 日期字符串，不传则统计全部
        """
        from datetime import datetime

        if date_str:
            start_date = datetime.strptime(date_str, '%Y-%m-%d')
            start_timestamp = int(start_date.timestamp())
            end_timestamp = int((start_date.replace(hour=23, minute=59, second=59)).timestamp())
            query = f"""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) as completed,
                    AVG(CASE WHEN exit_channel_time > 0 AND enter_channel_time > 0 
                        THEN (exit_channel_time - enter_channel_time) / 60.0 END) as avg_passage_time
                FROM {self.TABLE_NAME}
                WHERE create_time BETWEEN ? AND ?
            """
            results = self.db.fetch_all(query, (start_timestamp, end_timestamp))
        else:
            query = f"""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) as active,
                    SUM(CASE WHEN is_active = 0 THEN 1 ELSE 0 END) as completed,
                    AVG(CASE WHEN exit_channel_time > 0 AND enter_channel_time > 0 
                        THEN (exit_channel_time - enter_channel_time) / 60.0 END) as avg_passage_time
                FROM {self.TABLE_NAME}
            """
            results = self.db.fetch_all(query)

        return results[0] if results else {}