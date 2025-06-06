# processors/step4_simplify.py
import csv
import re
from tqdm import tqdm


def process(input_file, output_file):
    """生成最终流水总表（完全清理交易明细）"""
    with open(input_file, 'r', encoding='utf-8-sig') as f_in, \
            open(output_file, 'w', encoding='utf-8-sig', newline='') as f_out:

        reader = csv.reader(f_in)
        headers = next(reader) + ["交易单号", "交易方式"]
        writer = csv.writer(f_out)
        writer.writerow(headers)

        # 增强正则模式（匹配所有交易单号/交易方式格式）
        tx_id_pattern = re.compile(r'(\[交易单号：(\d+)\]|交易单号：(\d+))\s*')
        tx_type_pattern = re.compile(r'\s*微信(转账|红包)\s*$')

        # 进度条支持
        total_lines = sum(1 for _ in open(input_file, encoding='utf-8-sig'))
        pbar = tqdm(total=total_lines - 1, desc="生成总表", unit="条")

        for row in reader:
            pbar.update(1)
            original_detail = row[6]

            # 提取交易信息
            tx_id_match = tx_id_pattern.search(original_detail)
            tx_type_match = tx_type_pattern.search(original_detail)

            # 清理交易明细（关键修改点）
            cleaned_detail = tx_id_pattern.sub('', original_detail)  # 移除交易单号
            cleaned_detail = tx_type_pattern.sub('', cleaned_detail)  # 移除交易类型
            cleaned_detail = re.sub(r'\s{2,}', ' ', cleaned_detail).strip()  # 清理多余空格

            # 获取提取值
            tx_id = ""
            if tx_id_match:
                tx_id = tx_id_match.group(2) or tx_id_match.group(3)  # 匹配两种格式

            tx_type = f"微信{tx_type_match.group(1)}" if tx_type_match else ""

            # 更新明细列
            row[6] = cleaned_detail

            # 填充所有空缺值为<空缺>
            processed_row = []
            for cell in row + [tx_id, tx_type]:
                if cell == "" or cell is None or (isinstance(cell, str) and cell.strip() == ""):
                    processed_row.append("<空缺>")
                else:
                    processed_row.append(cell)

            writer.writerow(processed_row)

        pbar.close()

if __name__ == "__main__":
    # 测试代码
    process("step3_organized_transactions.csv", "test_output.csv")
