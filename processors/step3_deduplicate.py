import csv
import re
import os
from tqdm import tqdm


def parse_transaction_detail(detail):
    """清洗交易明细（处理微信名为空的情况）"""
    cleaned = detail

    # 1. 处理转款方为空的情况（以"（微信号） 时间戳"开头）
    cleaned = re.sub(r'^（[^）]+）\s*\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}\s*', '<微信名为空> ', cleaned)

    # 2. 删除其他情况下的转款方微信号
    cleaned = re.sub(r'（[^）]+）\s*\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}', '', cleaned)

    # 3. 处理收款方为空的情况
    cleaned = re.sub(r'向\s+转账', '向<微信名为空>转账', cleaned)

    # 4. 清理多余空格
    cleaned = re.sub(r'[\s　]+', ' ', cleaned).strip()

    return cleaned


def process(input_file, output_file):
    """主处理函数"""
    processed_count = 0
    seen_transactions = set()

    # 获取文件总行数用于进度条
    with open(input_file, 'r', encoding='utf-8-sig') as f:
        total_lines = sum(1 for _ in f) - 1  # 减去标题行

    with open(input_file, 'r', encoding='utf-8-sig') as f_in, \
            open(output_file, 'w', encoding='utf-8-sig', newline='') as f_out:

        reader = csv.reader(f_in)
        writer = csv.writer(f_out)

        # 处理标题行（不再添加新列）
        headers = next(reader)
        writer.writerow(headers)  # 保持原有列结构

        # 创建进度条
        pbar = tqdm(total=total_lines, desc="去重清洗", unit="条")

        for row in reader:
            pbar.update(1)

            # 过滤包含"来自"的记录
            if "来自" in row[6]:
                continue

            # 解析和清洗交易明细（仅清洗）
            cleaned_detail = parse_transaction_detail(row[6])

            # 创建唯一标识（来源文件+清洗后明细）
            unique_id = (row[0], cleaned_detail)
            if unique_id in seen_transactions:
                continue
            seen_transactions.add(unique_id)

            # 更新清洗后的明细到原列
            row[6] = cleaned_detail
            writer.writerow(row)
            processed_count += 1

        pbar.close()


if __name__ == "__main__":
    # 测试代码
    process("step2_organized_transactions.csv", "test_output.csv")
