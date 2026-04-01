# generate_test_data.py
import time
import random
from datetime import datetime, timedelta
from sqlite3Manager import SQLiteTableManager
from command_record_db import CommandRecordDB


def generate_test_records(db_manager):
    """生成测试通行记录数据"""

    # 创建通行记录数据库对象
    record_db = CommandRecordDB(db_manager)

    # 测试船舶数据
    ships = [
        {"mmsi": "413256789", "name": "长江一号", "direction": "up", "tug_count": 0, "cargo": "集装箱",
         "actual_load": 12000, "rated_load": 15000},
        {"mmsi": "413256790", "name": "长江二号", "direction": "up", "tug_count": 2, "cargo": "散货",
         "actual_load": 8000, "rated_load": 10000},
        {"mmsi": "413256791", "name": "长江三号", "direction": "down", "tug_count": 1, "cargo": "油品",
         "actual_load": 5000, "rated_load": 8000},
        {"mmsi": "413256792", "name": "长江四号", "direction": "down", "tug_count": 0, "cargo": "件杂货",
         "actual_load": 3000, "rated_load": 5000},
        {"mmsi": "413256793", "name": "长江五号", "direction": "up", "tug_count": 3, "cargo": "矿砂",
         "actual_load": 15000, "rated_load": 18000},
        {"mmsi": "413256794", "name": "长江六号", "direction": "down", "tug_count": 1, "cargo": "木材",
         "actual_load": 6000, "rated_load": 7000},
        {"mmsi": "413256795", "name": "长江七号", "direction": "up", "tug_count": 0, "cargo": "粮食",
         "actual_load": 9000, "rated_load": 12000},
        {"mmsi": "413256796", "name": "长江八号", "direction": "down", "tug_count": 2, "cargo": "钢材",
         "actual_load": 11000, "rated_load": 13000},
        {"mmsi": "413256797", "name": "长江九号", "direction": "up", "tug_count": 1, "cargo": "化工品",
         "actual_load": 4000, "rated_load": 6000},
        {"mmsi": "413256798", "name": "长江十号", "direction": "down", "tug_count": 0, "cargo": "设备",
         "actual_load": 2000, "rated_load": 3000},
    ]

    # 天气选项
    weathers = ["晴", "雨", "阴", "霾", "雾"]

    # 顶推情况
    push_status = ["", "顶推", "调头等待"]

    # 值班人
    duty_persons = ["张三", "李四", "王五", "赵六", "钱七"]

    # 水位数据
    water_levels = [2.5, 2.8, 3.0, 3.2, 3.5, 2.6, 2.9]

    # 生成最近7天的数据
    today = datetime.now()

    print("开始生成测试数据...")

    for day_offset in range(7):  # 最近7天
        record_date = today - timedelta(days=day_offset)

        # 每天生成5-10条记录
        records_count = random.randint(5, 10)

        for i in range(records_count):
            # 选择船舶
            ship = random.choice(ships)

            # 生成当天的时间（8:00-22:00之间）
            hour = random.randint(8, 22)
            minute = random.randint(0, 59)
            second = random.randint(0, 59)
            record_time = datetime(
                record_date.year, record_date.month, record_date.day,
                hour, minute, second
            )
            timestamp = int(record_time.timestamp())

            # 生成时间序列
            forecast_time = timestamp
            supplement_time = forecast_time + random.randint(60, 300)  # 1-5分钟后
            start_hang_time = supplement_time + random.randint(60, 300)
            half_pole_time = start_hang_time + random.randint(120, 600)
            enter_channel_time = half_pole_time + random.randint(180, 900)

            # 计算通过时间（10-60分钟）
            passage_minutes = random.randint(10, 60)
            exit_channel_time = enter_channel_time + (passage_minutes * 60)

            # 随机决定是否完成记录（80%完成，20%进行中）
            is_active = 0 if random.random() < 0.8 else 1

            if is_active:
                # 进行中的记录，没有出漕时间
                exit_channel_time = 0
            else:
                # 已完成的记录，确保有出漕时间
                exit_channel_time = enter_channel_time + (passage_minutes * 60)

            # 创建记录
            record = {
                "mmsi": ship["mmsi"],
                "name": ship["name"],
                "direction": ship["direction"],
                "tug_count": ship["tug_count"],
                "cargo": ship["cargo"],
                "actual_load": ship["actual_load"],
                "rated_load": ship["rated_load"],
                "water_level": random.choice(water_levels),
                "duty_person": random.choice(duty_persons),
                "weather": random.choice(weathers),
                "pushing_status": random.choice(push_status),
                "remark": f"测试记录 {day_offset + 1}-{i + 1}",
                "forecast_time": forecast_time,
                "supplement_time": supplement_time,
                "start_hang_time": start_hang_time,
                "half_pole_time": half_pole_time,
                "enter_channel_time": enter_channel_time,
                "exit_channel_time": exit_channel_time,
                "create_time": forecast_time,
                "last_update": int(time.time()),
                "is_active": is_active
            }

            # 插入数据库
            record_id = record_db.insert(record)
            if record_id > 0:
                print(f"✓ 插入记录: {ship['name']} - {record_time.strftime('%Y-%m-%d %H:%M:%S')}")
            else:
                print(f"✗ 插入失败: {ship['name']}")

    print(f"\n测试数据生成完成！共生成记录数: {len(ships) * 7}")


def generate_simple_test_data(db_manager):
    """生成简单的测试数据（用于快速测试）"""

    record_db = CommandRecordDB(db_manager)

    # 简单的测试数据
    test_records = [
        {
            "mmsi": "413256789",
            "name": "长江一号",
            "direction": "up",
            "tug_count": 0,
            "cargo": "集装箱",
            "actual_load": 12000,
            "rated_load": 15000,
            "water_level": 3.2,
            "duty_person": "张三",
            "weather": "晴",
            "pushing_status": "",
            "remark": "正常通行",
            "forecast_time": int(time.time()) - 3600,  # 1小时前
            "supplement_time": int(time.time()) - 3500,
            "start_hang_time": int(time.time()) - 3400,
            "half_pole_time": int(time.time()) - 3200,
            "enter_channel_time": int(time.time()) - 3000,
            "exit_channel_time": int(time.time()) - 2400,  # 40分钟前
            "create_time": int(time.time()) - 3600,
            "last_update": int(time.time()),
            "is_active": 0
        },
        {
            "mmsi": "413256790",
            "name": "长江二号",
            "direction": "up",
            "tug_count": 2,
            "cargo": "散货",
            "actual_load": 8000,
            "rated_load": 10000,
            "water_level": 3.0,
            "duty_person": "李四",
            "weather": "阴",
            "pushing_status": "顶推",
            "remark": "正在通行中",
            "forecast_time": int(time.time()) - 1800,  # 30分钟前
            "supplement_time": int(time.time()) - 1700,
            "start_hang_time": int(time.time()) - 1500,
            "half_pole_time": int(time.time()) - 1200,
            "enter_channel_time": int(time.time()) - 600,  # 10分钟前
            "exit_channel_time": 0,  # 还未出漕
            "create_time": int(time.time()) - 1800,
            "last_update": int(time.time()),
            "is_active": 1
        },
        {
            "mmsi": "413256791",
            "name": "长江三号",
            "direction": "down",
            "tug_count": 1,
            "cargo": "油品",
            "actual_load": 5000,
            "rated_load": 8000,
            "water_level": 2.8,
            "duty_person": "王五",
            "weather": "雾",
            "pushing_status": "调头等待",
            "remark": "能见度较低，减速通行",
            "forecast_time": int(time.time()) - 5400,  # 1.5小时前
            "supplement_time": int(time.time()) - 5300,
            "start_hang_time": int(time.time()) - 5100,
            "half_pole_time": int(time.time()) - 4800,
            "enter_channel_time": int(time.time()) - 4500,
            "exit_channel_time": int(time.time()) - 3600,  # 1小时前
            "create_time": int(time.time()) - 5400,
            "last_update": int(time.time()),
            "is_active": 0
        },
        {
            "mmsi": "413256792",
            "name": "长江四号",
            "direction": "down",
            "tug_count": 0,
            "cargo": "件杂货",
            "actual_load": 3000,
            "rated_load": 5000,
            "water_level": 3.5,
            "duty_person": "赵六",
            "weather": "晴",
            "pushing_status": "",
            "remark": "",
            "forecast_time": int(time.time()) - 7200,  # 2小时前
            "supplement_time": int(time.time()) - 7100,
            "start_hang_time": int(time.time()) - 6900,
            "half_pole_time": int(time.time()) - 6600,
            "enter_channel_time": int(time.time()) - 6300,
            "exit_channel_time": int(time.time()) - 5400,  # 1.5小时前
            "create_time": int(time.time()) - 7200,
            "last_update": int(time.time()),
            "is_active": 0
        },
        {
            "mmsi": "413256793",
            "name": "长江五号",
            "direction": "up",
            "tug_count": 3,
            "cargo": "矿砂",
            "actual_load": 15000,
            "rated_load": 18000,
            "water_level": 2.5,
            "duty_person": "钱七",
            "weather": "雨",
            "pushing_status": "顶推",
            "remark": "雨天注意安全",
            "forecast_time": int(time.time()) - 900,  # 15分钟前
            "supplement_time": int(time.time()) - 800,
            "start_hang_time": int(time.time()) - 700,
            "half_pole_time": int(time.time()) - 500,
            "enter_channel_time": int(time.time()) - 300,  # 5分钟前
            "exit_channel_time": 0,
            "create_time": int(time.time()) - 900,
            "last_update": int(time.time()),
            "is_active": 1
        },
    ]

    print("开始生成测试数据...")

    for record in test_records:
        record_id = record_db.insert(record)
        if record_id > 0:
            print(f"✓ 插入记录: {record['name']} - {record['forecast_time']}")
        else:
            print(f"✗ 插入失败: {record['name']}")

    print(f"\n测试数据生成完成！共生成 {len(test_records)} 条记录")


if __name__ == "__main__":
    # 创建数据库管理器
    db_manager = SQLiteTableManager("test.db")

    if db_manager.connect():
        print("数据库连接成功")

        # 方式1：生成简单的测试数据（推荐先运行这个）
        generate_simple_test_data(db_manager)

        # # 方式2：生成完整的测试数据（较多数据）
        # generate_test_records(db_manager)

        db_manager.disconnect()
        print("数据库已断开")
    else:
        print("数据库连接失败")