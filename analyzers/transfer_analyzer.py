import pandas as pd
import re
from tqdm import tqdm


def analyze(input_file, output_file):
    """单笔转账分析（精确金额提取版）"""
    try:
        df = pd.read_csv(input_file, encoding='utf-8-sig')

        # 先填充原始数据中的空值
        df = df.fillna('')

        results = []
        for _, row in tqdm(df.iterrows(), total=len(df), desc="解析转账"):
            detail = parse_detail(row)
            if detail:
                results.append({
                    '时间': str(row['时间']).strip() if pd.notna(row['时间']) and str(
                        row['时间']).strip() else '<空缺>',
                    '转账方': detail['payer'] if detail['payer'] and detail['payer'].strip() else '<空缺>',
                    '收款方': detail['payee'] if detail['payee'] and detail['payee'].strip() else '<空缺>',
                    '金额': detail.get('amount', '微信红包')
                })

        result_df = pd.DataFrame(results)

        # 再次检查并填充所有空值和空字符串
        for col in result_df.columns:
            result_df[col] = result_df[col].apply(
                lambda x: '<空缺>' if pd.isna(x) or (isinstance(x, str) and not x.strip()) else x
            )

        result_df.to_csv(output_file, index=False, encoding='utf-8-sig')
        return True
    except Exception as e:
        print(f"单笔转账分析失败: {str(e)}")
        return False


def parse_detail(row):
    """增强型交易明细解析"""
    try:
        # 确保所有字段不为None
        tx_type = str(row.get('交易方式', '')).strip() if pd.notna(row.get('交易方式')) else ''
        tx_detail = str(row.get('交易明细', '')).strip() if pd.notna(row.get('交易明细')) else ''
        counterpart = str(row.get('对方微信名', '')).strip() if pd.notna(row.get('对方微信名')) else '<空缺>'
        examiner = str(row.get('检材微信名', '')).strip() if pd.notna(row.get('检材微信名')) else '<空缺>'

        # 确保默认值不为空
        counterpart = counterpart if counterpart else '<空缺>'
        examiner = examiner if examiner else '<空缺>'

        # 微信红包特殊处理
        if '微信红包' in tx_type:
            return {
                'payer': counterpart,
                'payee': examiner
            }

        # 提取转账双方
        payer_match = re.search(r'^(.*?)\s+向', tx_detail)
        payee_match = re.search(r'向\s*([^转发送红包]+?)(?:转账|发送|$)', tx_detail)

        payer = payer_match.group(1).strip() if payer_match and payer_match.group(1).strip() else '<空缺>'
        payee = payee_match.group(1).strip() if payee_match and payee_match.group(1).strip() else '<空缺>'

        # 精确匹配金额部分
        amount_match = re.search(
            r'￥([\d,]+(?:\.\d{1,2})?)(?:元|\s|$)',
            tx_detail
        )

        # 处理金额格式
        if amount_match:
            amount = float(amount_match.group(1).replace(',', ''))
        else:
            amount = 0.0

        return {
            'payer': payer,
            'payee': payee,
            'amount': amount
        }
    except Exception as e:
        print(f"解析失败：{str(row.get('交易明细', ''))[:30]}... | 错误：{str(e)}")
        return {
            'payer': '<空缺>',
            'payee': '<空缺>',
            'amount': 0.0
        }


if __name__ == "__main__":
    analyze("周志强、蒲雄鑫等人侵犯公民个人信息案报告_流水总表.csv", "test_transfer.csv")
