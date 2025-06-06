import os
import re
import csv
import glob
import multiprocessing
from bs4 import BeautifulSoup
from tqdm import tqdm
from functools import partial


def get_parser():
    """获取可用的最佳解析器"""
    try:
        from lxml import etree
        return 'lxml'
    except ImportError:
        try:
            import html5lib
            return 'html5lib'
        except ImportError:
            return 'html.parser'


def process_single_file(file_path, parser):
    """处理单个HTML文件"""
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            soup = BeautifulSoup(f, parser)
            file_results = []

            for h_tag in soup.find_all(['h1', 'h2', 'h3', 'h4', 'h5', 'h6']):
                if '流水记录' in h_tag.get_text():
                    div_tag = h_tag.find_next('div')
                    if div_tag:
                        header = re.sub(r'\s+', ' ', h_tag.get_text(strip=True))
                        content = div_tag.get_text(strip=True, separator=' ')
                        file_results.append([
                            os.path.basename(file_path),
                            header,
                            content
                        ])
            return file_results
    except Exception as e:
        print(f"处理文件 {file_path} 时出错: {str(e)}")
        return []


def process(input_dir, output_file):
    """主处理函数"""
    parser = get_parser()
    print(f"使用的HTML解析器: {parser}")
    if parser == 'html.parser':
        print("警告: 建议安装lxml以获得更好性能 (pip install lxml)")

    # 获取并排序文件列表
    html_files = glob.glob(os.path.join(input_dir, 'page*.html'))
    html_files.sort(key=lambda x: int(re.search(r'page(\d+)\.html', x).group(1)))
    total_files = len(html_files)

    if not html_files:
        print("未找到匹配的HTML文件")
        return

    # 初始化进度条（放在这里确保只创建一次）
    pbar = tqdm(total=total_files, desc="解析进度", unit="文件")

    # 多进程处理
    results = []
    with multiprocessing.Pool(processes=multiprocessing.cpu_count()) as pool:
        # 使用imap按顺序处理文件
        for file_result in pool.imap(
                partial(process_single_file, parser=parser),
                html_files
        ):
            if file_result:
                results.extend(file_result)
            pbar.update(1)  # 每个文件处理完更新一次进度

    pbar.close()  # 确保进度条关闭

    # 按原始文件顺序排序结果（imap已保持顺序，此步可省略）
    results.sort(key=lambda x: int(re.search(r'page(\d+)\.html', x[0]).group(1)))

    # 写入CSV
    with open(output_file, 'w', encoding='utf-8-sig', newline='') as f:
        writer = csv.writer(f)
        writer.writerow(['来源文件', '标题', '原始内容'])
        writer.writerows(results)
    print(f"处理完成！共处理 {total_files} 个文件，生成 {len(results)} 条记录")


if __name__ == '__main__':
    input_directory = './html_files'
    output_csv = './output.csv'
    process(input_directory, output_csv)
