# importer/database_importer.py
import os
import sqlite3
import pandas as pd
from tqdm import tqdm


def import_to_database(report_name, total_table_path, analysis_dir):
    """将总表和功能表导入SQLite数据库"""
    # 创建数据库目录
    db_dir = os.path.join("database", report_name)
    os.makedirs(db_dir, exist_ok=True)

    # 数据库路径
    db_path = os.path.join(db_dir, f"{report_name}.db")

    try:
        with sqlite3.connect(db_path) as conn:
            # 导入总表
            table_name = "总表"
            df_total = pd.read_csv(total_table_path, encoding='utf-8-sig')
            df_total.to_sql(table_name, conn, if_exists='replace', index=False)
            print(f"\n[总表] 导入成功，记录数：{len(df_total)}")

            # 导入功能表
            analysis_files = [f for f in os.listdir(analysis_dir) if f.endswith('.csv')]
            for file in tqdm(analysis_files, desc="导入功能表"):
                table_name = os.path.splitext(file)[0]  # 去除.csv后缀作为表名
                file_path = os.path.join(analysis_dir, file)
                df = pd.read_csv(file_path, encoding='utf-8-sig')
                df.to_sql(table_name, conn, if_exists='replace', index=False)

        print(f"\n数据库已保存至：{os.path.abspath(db_path)}")
        return True
    except Exception as e:
        print(f"\n数据库导入失败：{str(e)}")
        return False