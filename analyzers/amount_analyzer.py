import pandas as pd
import re
from tqdm import tqdm


def analyze(input_file, output_file):
    """交易总额分析（增强版）"""
    try:
        df = pd.read_csv(input_file, encoding='utf-8-sig')

        # 先填充原始数据中的空值
        df = df.fillna('')

        # 提取交易双方信息
        df[['转账方', '收款方']] = df.apply(
            lambda row: extract_parties(row['交易明细'], row['交易方式'], row['检材微信名'], row['对方微信名']),
            axis=1,
            result_type='expand'
        )

        # 提取金额
        df['金额'] = df['交易明细'].apply(extract_amount)

        # 统计总金额和交易次数
        summary = df.groupby(['转账方', '收款方']).agg(
            总金额=('金额', 'sum'),
            总交易数=('金额', 'count')
        ).reset_index()

        # 统计微信红包个数
        red_packet_counts = df[df['交易方式'] == '微信红包'].groupby(['转账方', '收款方']).size().reset_index(
            name='微信红包个数')

        # 合并结果
        final_df = pd.merge(
            summary,
            red_packet_counts,
            on=['转账方', '收款方'],
            how='left'
        )

        # 处理微信红包个数
        final_df['微信红包个数'] = final_df['微信红包个数'].fillna(0).astype(int)

        # 调整列顺序
        final_df = final_df[['转账方', '收款方', '总金额', '微信红包个数']]

        # 再次检查并填充所有空值
        for col in final_df.columns:
            final_df[col] = final_df[col].apply(
                lambda x: '<空缺>' if pd.isna(x) or (isinstance(x, str) and not x.strip()) else x
            )

        final_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        return True
    except Exception as e:
        print(f"交易总额分析失败: {str(e)}")
        return False


def extract_parties(detail, tx_type, default_payer, default_payee):
    """从交易明细提取交易双方（增强版）"""
    try:
        # 确保默认值不为空
        default_payer = str(default_payer).strip() if pd.notna(default_payer) and str(default_payer).strip() else '<空缺>'
        default_payee = str(default_payee).strip() if pd.notna(default_payee) and str(default_payee).strip() else '<空缺>'

        # 确保detail不为空
        if pd.isna(detail) or not str(detail).strip():
            return (default_payer, default_payee)

        detail = str(detail)

        # 微信红包特殊处理
        if pd.notna(tx_type) and "微信红包" in str(tx_type):
            return (default_payee, default_payer)

        # 普通转账处理
        payer_match = re.search(r'^(.*?)\s+向', detail)
        payee_match = re.search(r'向\s*([^转发送]+?)(?:转账|发送|$)', detail)

        payer = payer_match.group(1).strip() if payer_match else default_payer
        payee = payee_match.group(1).strip() if payee_match else default_payee

        # 最终检查，确保不返回空字符串
        payer = payer if payer else '<空缺>'
        payee = payee if payee else '<空缺>'

        return (payer, payee)
    except Exception as e:
        return ('<空缺>', '<空缺>')


def extract_amount(detail):
    """精确提取金额（只匹配￥后的第一个金额）"""
    try:
        if pd.isna(detail):
            return 0.0
        # 匹配模式：￥开头，后接数字（允许小数点和逗号分隔）
        match = re.search(r'￥([\d,]+\.?\d*|\d+\.?\d*)', str(detail).replace('，', ''))
        if match:
            # 清理逗号并转换为浮点数
            return float(match.group(1).replace(',', ''))
        return 0.0
    except:
        return 0.0


if __name__ == "__main__":
    # 测试代码
    analyze("流水总表.csv", "test_output.csv")
