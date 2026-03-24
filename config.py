import json
import os
import sys

class ConfigManager:
    """应用程序配置管理器（配置文件位于程序目录）"""

    def __init__(self, app_name="MyApp"):
        # 获取当前程序所在目录
        if getattr(sys, 'frozen', False):
            # 如果是打包后的可执行文件（如 PyInstaller）
            program_dir = os.path.dirname(sys.executable)
        else:
            # 如果是普通 Python 脚本运行
            program_dir = os.path.dirname(os.path.abspath(sys.argv[0]))

        self.config_path = os.path.join(program_dir, "config.json")

        # 默认配置
        self.default_config = {
            "map": {
                "center": [28.0, 110.0],
                "zoom": 12
            },
            "window": {
                "width": 1024,
                "height": 768,
                "maximized": False
            },
            "other_settings": {
                "theme": "light"
            }
        }

        # 加载配置（如果文件不存在则自动创建）
        self.config = self.load_config()

    def load_config(self):
        """加载配置文件，若不存在则创建默认配置并保存"""
        if os.path.exists(self.config_path):
            try:
                with open(self.config_path, 'r', encoding='utf-8') as f:
                    config = json.load(f)
                return self._merge_with_defaults(config)
            except Exception as e:
                print(f"加载配置文件失败: {e}，将使用默认配置并尝试重新生成")
                # 如果读取失败，备份原文件并创建默认配置
                return self._create_default_config()
        else:
            # 文件不存在，创建默认配置并保存
            return self._create_default_config()

    def _create_default_config(self):
        """创建默认配置并保存到文件，返回默认配置副本"""
        self.config = self.default_config.copy()
        self.save_config()
        return self.config

    def save_config(self):
        """将当前配置保存到文件"""
        try:
            # 确保目录存在（程序目录通常已存在，但以防万一）
            os.makedirs(os.path.dirname(self.config_path), exist_ok=True)
            with open(self.config_path, 'w', encoding='utf-8') as f:
                json.dump(self.config, f, ensure_ascii=False, indent=4)
            print(f"配置文件已保存至: {self.config_path}")
            return True
        except Exception as e:
            print(f"保存配置文件失败: {e}")
            return False

    def get(self, *keys, default=None):
        """按层级获取配置值，例如 config.get('map', 'center')"""
        value = self.config
        for key in keys:
            if isinstance(value, dict) and key in value:
                value = value[key]
            else:
                return default
        return value

    def set(self, *keys, value):
        """按层级设置配置值，自动创建中间字典"""
        current = self.config
        for key in keys[:-1]:
            if key not in current:
                current[key] = {}
            current = current[key]
        current[keys[-1]] = value

    def _merge_with_defaults(self, loaded):
        """将加载的配置与默认配置合并，确保所有默认键都存在"""
        merged = self.default_config.copy()
        self._dict_merge(merged, loaded)
        return merged

    def _dict_merge(self, target, source):
        """递归合并字典（source 覆盖 target）"""
        for key, value in source.items():
            if key in target and isinstance(target[key], dict) and isinstance(value, dict):
                self._dict_merge(target[key], value)
            else:
                target[key] = value