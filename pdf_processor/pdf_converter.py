import pdfplumber
import pandas as pd
import re
import os
from typing import Optional
import numpy as np  # 新增导入numpy用于处理NaN值


def extract_metadata(text: str) -> dict:
    """提取PDF中的关键元数据：姓名、微信号、时间段"""
    metadata = {
        "name": "未知姓名",
        "wechat_id": "未知微信号",
        "time_range": "未知时间段",
        "date_range": "未知日期范围"  # 新增字段，仅包含日期部分
    }

    try:
        # 提取姓名（不包含身份证号）
        name_match = re.search(r"兹证明：([^(（]+?)[(（]", text)
        if name_match:
            metadata["name"] = name_match.group(1).strip()

        # 提取微信号
        wechat_match = re.search(r"微信号：([^中\s]+)", text)
        if wechat_match:
            metadata["wechat_id"] = wechat_match.group(1).strip()

        # 提取时间段（精确匹配完整的时间格式）
        time_match = re.search(
            r"交易明细对应时间段\s*([\d-]+)\s[\d:]+\s*至\s*([\d-]+)\s[\d:]+",
            text
        )
        if time_match:
            # 完整时间范围（保留原始格式）
            metadata["time_range"] = f"{time_match.group(1)}至{time_match.group(2)}"
            # 仅日期部分（用于文件名）
            metadata["date_range"] = f"{time_match.group(1)}至{time_match.group(2)}"
    except Exception as e:
        print(f"元数据提取异常: {e}")

    return metadata


def clean_filename(text: str) -> str:
    """生成安全的文件名（保留原始空格但不包含非法字符）"""
    return re.sub(r'[\\/*?:"<>|]', '', text).strip()


def extract_tables_from_pdf(pdf_path: str) -> list:
    """使用pdfplumber提取PDF中的所有表格数据"""
    all_data = []

    with pdfplumber.open(pdf_path) as pdf:
        for page in pdf.pages:
            # 优先尝试提取表格
            tables = page.extract_tables()
            if tables:
                for table in tables:
                    # 过滤空行和无效数据
                    cleaned_table = [row for row in table if any(cell and str(cell).strip() for cell in row)]
                    all_data.extend(cleaned_table)
            else:
                # 备用方案：文本提取（如果表格识别失败）
                text = page.extract_text()
                if text:
                    # 处理文本格式数据（示例需要根据实际调整）
                    lines = [line.strip() for line in text.split('\n') if line.strip()]
                    all_data.extend([line.split() for line in lines])

    return all_data


def process_table_data(all_data: list) -> list:
    """处理提取的表格数据，返回表头和数据行"""
    # 定位数据起始行（跳过标题和表头）
    start_idx = 0
    for i, row in enumerate(all_data):
        if "交易单号" in str(row) and "交易时间" in str(row):
            start_idx = i
            break

    # 提取有效数据（假设表头在start_idx行，数据从start_idx+1开始）
    if len(all_data) > start_idx + 1:
        # 处理可能的合并表头（微信PDF的表头可能跨多行）
        header = all_data[start_idx]
        data_rows = all_data[start_idx + 1:]

        # 清理数据：去除多余空格和换行符
        processed_data = []
        for row in data_rows:
            cleaned_row = [re.sub(r'\s+', ' ', str(cell)).strip() if cell else "" for cell in row]
            processed_data.append(cleaned_row)

        return [header] + processed_data
    else:
        print("警告：未找到有效交易数据")
        return []


def fill_empty_cells(df: pd.DataFrame) -> pd.DataFrame:
    """将所有空值填充为/"""
    # 替换各种形式的空值
    df = df.replace([None, np.nan, ""], "/")
    # 处理包含空格的空字符串 - 使用map替代applymap
    df = df.map(lambda x: "/" if isinstance(x, str) and not x.strip() else x)
    return df


def wechat_pdf_to_excel(pdf_path: str, output_dir: str = "") -> Optional[str]:
    """主处理函数"""
    try:
        # 第一步：读取PDF内容并提取元数据
        with pdfplumber.open(pdf_path) as pdf:
            full_text = "\n".join(page.extract_text() for page in pdf.pages if page.extract_text())

        metadata = extract_metadata(full_text)

        # 第二步：生成文件名（使用date_range而非time_range）
        filename = (
            f"{clean_filename(metadata['name'])}（{clean_filename(metadata['wechat_id'])}）"
            f"微信支付交易明细证明 {clean_filename(metadata['date_range'])}.xlsx"
        )
        excel_path = os.path.join(output_dir, filename) if output_dir else filename

        # 第三步：提取表格数据
        all_data = extract_tables_from_pdf(pdf_path)
        table_data = process_table_data(all_data)

        if not table_data or len(table_data) < 2:
            print("错误：未找到有效的交易数据")
            return None

        # 第四步：创建DataFrame
        try:
            df = pd.DataFrame(table_data[1:], columns=table_data[0])

            # 第五步：去除指定列的所有空格
            columns_to_clean = ["交易类型", "收/支/其他", "交易方式", "金额(元)", "交易对方"]
            for col in columns_to_clean:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace(r'\s+', '', regex=True)

            # 第六步：填充所有空单元格为<空缺>
            df = fill_empty_cells(df)

            # 第七步：保存Excel
            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)

            print(f"转换成功！文件已保存为：{excel_path}")
            return excel_path
        except ValueError as e:
            print(f"数据格式错误: {e}")
            print("尝试修复数据格式...")

            # 修复数据格式：确保每行都有与表头相同的列数
            header_len = len(table_data[0])
            fixed_data = []
            for row in table_data[1:]:
                if len(row) != header_len:
                    fixed_row = row + [""] * (header_len - len(row)) if len(row) < header_len else row[:header_len]
                    fixed_data.append(fixed_row)
                else:
                    fixed_data.append(row)

            # 创建DataFrame并处理
            df = pd.DataFrame(fixed_data, columns=table_data[0])

            # 去除指定列的所有空格
            columns_to_clean = ["交易类型", "收/支/其他", "交易方式", "金额(元)", "交易对方"]
            for col in columns_to_clean:
                if col in df.columns:
                    df[col] = df[col].astype(str).str.replace(r'\s+', '', regex=True)

            # 填充所有空单元格为<空缺>
            df = fill_empty_cells(df)

            with pd.ExcelWriter(excel_path, engine='openpyxl') as writer:
                df.to_excel(writer, index=False)

            print(f"已修复数据格式并保存为：{excel_path}")
            return excel_path

    except Exception as e:
        print(f"处理失败: {e}")
        return None


if __name__ == "__main__":
    # 使用示例
    pdf_path = "剑.pdf"
    output_dir = ""  # 可指定输出目录如 "C:/output"
    result_path = wechat_pdf_to_excel(pdf_path, output_dir)
