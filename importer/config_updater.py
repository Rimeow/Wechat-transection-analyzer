# importer/config_updater.py
import os
import yaml
from pathlib import Path


def get_project_root() -> Path:
    """获取项目根目录路径"""
    current_dir = Path(__file__).parent  # importer目录
    return current_dir.parent  # 项目根目录


def update_mcp_config(report_name):
    """将新生成的数据库信息写入MCP配置文件"""
    # 获取配置文件路径
    config_path = get_project_root() / "config.yaml"

    # 获取数据库绝对路径
    db_path = get_project_root() / "database" / report_name / f"{report_name}.db"
    db_abs_path = db_path.resolve().absolute().as_posix()

    # 读取现有配置
    config = {"connections": {}}
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            config = yaml.safe_load(f) or config

    # 构建连接信息
    connection_info = {
        "type": "sqlite",
        "path": db_abs_path,
        "password": "null"
    }

    # 更新配置
    config.setdefault("connections", {})[report_name] = connection_info

    # 写入新配置（保持原有格式）
    with open(config_path, "w", encoding="utf-8") as f:
        yaml.dump(
            config,
            f,
            allow_unicode=True,
            sort_keys=False,
            default_flow_style=False,
            indent=2
        )

    print(f"\n[配置更新] 已添加数据库连接：{report_name}")
    print(f"数据库路径：{db_abs_path}")


# 测试代码
if __name__ == "__main__":
    # 测试时需要手动设置报告名称
    test_report = "测试"
    update_mcp_config(test_report)