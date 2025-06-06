import csv
import re
from tqdm import tqdm

# 预编译正则表达式
HEADER_PATTERN = re.compile(
    r"(.+?)/(微信(?:\(分身版\))?)/(.+?)\((.+?)\)/流水记录/(.+?)(?:\((\d+)\))?$"
)
TRANSACTION_PATTERN = re.compile(r'(?<=微信转账)\s+|(?<=微信红包)\s+')


def process(input_file, output_file):
    """整理并规范化交易数据"""
    with open(input_file, 'r', encoding='utf-8-sig') as f_in, \
            open(output_file, 'w', encoding='utf-8-sig', newline='') as f_out:

        reader = csv.reader(f_in)
        next(reader)  # 跳过标题行
        writer = csv.writer(f_out)
        writer.writerow(["时间", "平台", "检材微信名", "微信号", "对方微信名", "对方微信号", "交易明细"])

        # 进度条设置
        total_lines = sum(1 for _ in open(input_file, encoding='utf-8-sig'))
        progress = tqdm(total=total_lines - 1, desc="整理数据", unit="条")

        for row in reader:
            progress.update(1)
            if len(row) < 3:
                continue

            # 解析标题信息
            header_match = HEADER_PATTERN.match(row[1])
            if not header_match:
                continue

            # 提取基础信息
            platform = header_match.group(2)
            self_name = header_match.group(3).strip()
            self_id = header_match.group(4).strip()
            target_part = header_match.group(5).strip()

            # 解析对方信息
            target_name, target_id = parse_target_info(target_part)

            # 分割交易记录
            transactions = TRANSACTION_PATTERN.split(row[2])

            for tx in transactions:
                tx = tx.strip()
                if not tx:
                    continue

                # 提取时间戳
                time_match = re.search(r"\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}", tx)
                if not time_match:
                    continue

                writer.writerow([
                    time_match.group(),
                    platform,
                    self_name,
                    self_id,
                    target_name,
                    target_id,
                    tx
                ])


def parse_target_info(target_part):
    """解析对方信息"""
    if '（' in target_part and '）' in target_part:
        target_match = re.match(r"(.+?)（(.+?)）", target_part)
        if target_match:
            return target_match.group(1).strip(), target_match.group(2).strip()
        else:
            parts = re.split(r"[（）]", target_part)
            return parts[0].strip(), parts[1].strip() if len(parts) > 1 else ""
    return target_part.strip(), ""