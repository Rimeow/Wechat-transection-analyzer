import os
import sys
import uuid
import shutil
import datetime
import json
import subprocess
import platform
import sqlite3
import logging
from logging.handlers import RotatingFileHandler
from flask import Flask, request, redirect, url_for, render_template, flash, jsonify, send_file
from werkzeug.utils import secure_filename
from ai_chat import chat_blueprint
from pdf_processor.pdf_converter import wechat_pdf_to_excel

# 添加项目目录到路径，以便导入其他模块
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# 初始化Flask应用
app = Flask(__name__)
app.secret_key = 'wechat_analysis_app_secret_key'
app.config['MAX_CONTENT_LENGTH'] = 600 * 1024 * 1024 * 1024  # 设置上传文件大小限制为600GB
app.config['UPLOAD_FOLDER'] = 'uploads'
app.config['OUTPUT_FOLDER'] = 'output'
app.config['LOGS_FOLDER'] = 'logs'
app.config['DATABASE_FOLDER'] = 'database'

# 注册AI聊天蓝图
app.register_blueprint(chat_blueprint, url_prefix='/api')
from ai_chat import init_app
init_app(app)

# 确保必要的目录存在
for folder in [app.config['UPLOAD_FOLDER'], app.config['OUTPUT_FOLDER'],
               app.config['DATABASE_FOLDER'], app.config['LOGS_FOLDER']]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# 配置日志
log_handler = RotatingFileHandler(
    os.path.join(app.config['LOGS_FOLDER'], 'app.log'),
    maxBytes=10 * 1024 * 1024,  # 10MB
    backupCount=5
)
log_handler.setFormatter(logging.Formatter(
    '[%(asctime)s] %(levelname)s in %(module)s: %(message)s'
))
app.logger.addHandler(log_handler)
app.logger.setLevel(logging.INFO)

# 存储任务状态的字典
tasks = {}


def extract_zip_external(zip_path, extract_dir):
    """
    解压 ZIP 文件，但跳过名为 "resfile" 的文件夹

    Args:
        zip_path (str): ZIP 文件路径
        extract_dir (str): 解压目标目录

    Returns:
        tuple: (success: bool, message: str)
    """
    app.logger.info(f"解压文件（跳过resfile）: {zip_path} -> {extract_dir}")
    try:
        # 检测 7z 是否可用
        seven_z_cmd = None
        for cmd in ['7z', '7z.exe', 'C:\\Program Files\\7-Zip\\7z.exe']:
            try:
                subprocess.run([cmd], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                seven_z_cmd = cmd
                break
            except (FileNotFoundError, subprocess.CalledProcessError):
                continue
        if seven_z_cmd:
            # 7z 排除 resfile 文件夹（使用 -x! 选项）
            cmd = [
                seven_z_cmd, 'x', '-y', '-mmt=on',
                f'-x!*/resfile/*',  # 排除所有包含 "resfile" 的路径
                '-o' + extract_dir,
                zip_path
            ]
            app.logger.info(f"使用7z解压（排除resfile）: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            return (True, "解压成功（已跳过resfile）")
        # 如果 7z 不可用，回退到其他工具
        system = platform.system()
        if system == "Windows":
            # Windows 的 tar 排除选项（需要 PowerShell 或新版 tar）
            cmd = [
                'tar', '--exclude=*/resfile/*',  # 排除路径中的 resfile
                '-xf', zip_path,
                '-C', extract_dir
            ]
            app.logger.info(f"使用tar解压（排除resfile）: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            return (True, "解压成功（已跳过resfile）")
        else:  # Linux/MacOS
            # unzip 排除选项（-x 不支持目录，需结合其他方法）
            cmd = [
                'unzip', '-o', '-qq',
                zip_path,
                '-d', extract_dir,
                '-x', '*/resfile/*'  # 排除 resfile 目录
            ]
            app.logger.info(f"使用unzip解压（排除resfile）: {' '.join(cmd)}")
            subprocess.run(cmd, check=True)
            return (True, "解压成功（已跳过resfile）")
    except subprocess.CalledProcessError as e:
        error_msg = f"解压失败（排除resfile）: {e}"
        app.logger.error(error_msg)
        return (False, error_msg)
    except Exception as e:
        error_msg = f"未知错误: {str(e)}"
        app.logger.error(error_msg)
        return (False, error_msg)


def get_report_name(input_dir):
    """获取报告名称，通常是取证报告的名称或者目录名称"""
    # 从输入目录路径中提取文件夹名称
    dir_name = os.path.basename(input_dir)

    # 如果是-files结尾的目录，去掉-files后缀
    if dir_name.endswith("-files"):
        return dir_name[:-6]  # 去掉 "-files" 后缀

    # 如果是在uploads/某目录下，取该目录名称
    parent_dir = os.path.dirname(input_dir)
    if os.path.basename(parent_dir) in app.config['UPLOAD_FOLDER']:
        return os.path.basename(input_dir)

    # 如果上述都不匹配，则返回完整目录名
    return dir_name


def update_task_status(task_id, status, message=None, progress=None, files=None, report_name=None):
    """更新任务状态"""
    if task_id not in tasks:
        tasks[task_id] = {
            'id': task_id,
            'status': 'initial',
            'message': '',
            'progress': 0,
            'report_name': '',
            'start_time': datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'end_time': None,
            'files': []
        }

    if status:
        tasks[task_id]['status'] = status

    if message:
        tasks[task_id]['message'] = message

    if progress is not None:
        tasks[task_id]['progress'] = progress

    if report_name:
        tasks[task_id]['report_name'] = report_name

    if status == 'completed' or status == 'failed':
        tasks[task_id]['end_time'] = datetime.datetime.now().strftime('%Y-%m-%d %H:%M:%S')

    if files:
        tasks[task_id]['files'] = files


def process_report(task_id, input_dir, original_filename):
    """异步处理报告文件"""
    try:
        # 初始化目录
        report_name = original_filename
        update_task_status(task_id, 'processing', f'开始处理报告: {report_name}', 5, report_name=report_name)
        # 创建中间文件目录（日志目录）
        logs_dir = os.path.join(app.config['LOGS_FOLDER'], report_name)
        if not os.path.exists(logs_dir):
            os.makedirs(logs_dir)
        # 创建最终输出目录
        output_dir = os.path.join(app.config['OUTPUT_FOLDER'], report_name)
        if not os.path.exists(output_dir):
            os.makedirs(output_dir)

        # ===== 新增：保存任务类型标识文件 =====
        task_type_file = os.path.join(output_dir, '.task_type')
        with open(task_type_file, 'w') as f:
            f.write('zip')  # 微信流水分析任务类型为zip
        # =====================================

        # 创建数据库目录
        db_dir = os.path.join(app.config['DATABASE_FOLDER'], report_name)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)

        # 创建数据库目录
        db_dir = os.path.join(app.config['DATABASE_FOLDER'], report_name)
        if not os.path.exists(db_dir):
            os.makedirs(db_dir)

        # 数据库路径
        db_path = os.path.join(db_dir, f"{report_name}.db")

        # 步骤1: 提取基础流水表格
        update_task_status(task_id, 'processing', '步骤1: 提取基础流水表格', 20)
        try:
            from processors import step1_extract
            # 中间文件放在logs目录
            step1_output = os.path.join(logs_dir, "step1_basic_transactions.csv")
            step1_extract.process(input_dir, step1_output)
            app.logger.info(f"基础流水表格生成成功: {step1_output}")
        except Exception as e:
            app.logger.error(f"步骤1失败: {str(e)}", exc_info=True)
            update_task_status(task_id, 'failed', f'步骤1失败: {str(e)}')
            return

        # 步骤2: 整理流水表格
        update_task_status(task_id, 'processing', '步骤2: 整理流水表格', 40)
        try:
            from processors import step2_organize
            # 中间文件放在logs目录
            step2_output = os.path.join(logs_dir, "step2_organized_transactions.csv")
            step2_organize.process(step1_output, step2_output)
            app.logger.info(f"流水表格整理成功: {step2_output}")
        except Exception as e:
            app.logger.error(f"步骤2失败: {str(e)}", exc_info=True)
            update_task_status(task_id, 'failed', f'步骤2失败: {str(e)}')
            return

        # 步骤3: 去重处理
        update_task_status(task_id, 'processing', '步骤3: 去重处理', 60)
        try:
            from processors import step3_deduplicate
            # 中间文件放在logs目录
            step3_output = os.path.join(logs_dir, "step3_deduplicated_transactions.csv")
            step3_deduplicate.process(step2_output, step3_output)
            app.logger.info(f"去重处理完成: {step3_output}")
        except Exception as e:
            app.logger.error(f"步骤3失败: {str(e)}", exc_info=True)
            update_task_status(task_id, 'failed', f'步骤3失败: {str(e)}')
            return

        # 步骤4: 简化处理，生成流水总表
        update_task_status(task_id, 'processing', '步骤4: 简化处理，生成流水总表', 70)
        try:
            from processors import step4_simplify
            # 最终文件放在output目录，使用中文名称
            total_transactions_file = os.path.join(output_dir, "流水总表.csv")
            step4_simplify.process(step3_output, total_transactions_file)
            app.logger.info(f"流水总表生成成功: {total_transactions_file}")
        except Exception as e:
            app.logger.error(f"步骤4失败: {str(e)}", exc_info=True)
            update_task_status(task_id, 'failed', f'步骤4失败: {str(e)}')
            return

        # 分析1: 生成单笔转账表
        update_task_status(task_id, 'processing', '分析1: 生成单笔转账表', 80)
        try:
            from analyzers import transfer_analyzer
            # 分析结果放在output目录，使用中文名称
            transfer_file = os.path.join(output_dir, "单笔转账.csv")
            transfer_analyzer.analyze(total_transactions_file, transfer_file)
            app.logger.info("单笔转账分析表生成成功")
        except Exception as e:
            app.logger.error(f"分析1失败: {str(e)}", exc_info=True)
            update_task_status(task_id, 'failed', f'分析1失败: {str(e)}')
            return

        # 分析2: 生成交易总额表
        update_task_status(task_id, 'processing', '分析2: 生成交易总额表', 85)
        try:
            from analyzers import amount_analyzer
            # 分析结果放在output目录，使用中文名称
            amount_file = os.path.join(output_dir, "交易总额.csv")
            amount_analyzer.analyze(total_transactions_file, amount_file)
            app.logger.info("交易总额分析表生成成功")
        except Exception as e:
            app.logger.error(f"分析2失败: {str(e)}", exc_info=True)
            update_task_status(task_id, 'failed', f'分析2失败: {str(e)}')
            return

        # 导入数据库
        update_task_status(task_id, 'processing', '导入分析结果到数据库', 90)
        try:
            from importer import database_importer
            # 注意调整函数参数以匹配实际定义
            database_importer.import_to_database(
                report_name=report_name,  # 使用原始文件名
                total_table_path=total_transactions_file,
                analysis_dir=output_dir
            )
            app.logger.info(f"数据库导入成功: {db_path}")
        except Exception as e:
            app.logger.error(f"数据库导入失败: {str(e)}", exc_info=True)
            update_task_status(task_id, 'failed', f'数据库导入失败: {str(e)}')
            return

        # 更新配置文件
        update_task_status(task_id, 'processing', '更新配置文件', 95)
        try:
            from importer import config_updater
            config_updater.update_mcp_config(report_name)  # 使用原始文件名
            app.logger.info("配置文件更新成功")
        except Exception as e:
            app.logger.error(f"配置更新失败: {str(e)}", exc_info=True)
            update_task_status(task_id, 'failed', f'配置更新失败: {str(e)}')
            return

        # 准备文件列表 - 不在此处生成URL
        files = [
            {
                'name': '流水总表.csv',
                'path': total_transactions_file,
                'type': 'report',
                'description': '流水总表'
            },
            {
                'name': '单笔转账.csv',
                'path': transfer_file,
                'type': 'report',
                'description': '单笔转账分析'
            },
            {
                'name': '交易总额.csv',
                'path': amount_file,
                'type': 'report',
                'description': '交易总额分析'
            },
            {
                'name': f"{report_name}.db",
                'path': db_path,
                'type': 'database',
                'description': '数据库文件'
            }
        ]

        update_task_status(task_id, 'completed', '处理完成', 100, files)
        app.logger.info(f"任务 {task_id} 完成")

    except Exception as e:
        app.logger.error(f"处理报告时出现未知错误: {str(e)}", exc_info=True)
        update_task_status(task_id, 'failed', f'处理报告时出现未知错误: {str(e)}')


def process_pdf(task_id, pdf_path, original_filename):
    """处理PDF文件转换"""
    try:
        # 使用原始文件名（去掉扩展名）作为初始报告名
        initial_report_name = os.path.splitext(original_filename)[0]
        update_task_status(task_id, 'processing', f'开始处理PDF: {initial_report_name}', 5,
                           report_name=initial_report_name)

        # 创建临时输出目录
        temp_output_dir = os.path.join(app.config['OUTPUT_FOLDER'], 'pdf_temp', initial_report_name)
        if not os.path.exists(temp_output_dir):
            os.makedirs(temp_output_dir)

        update_task_status(task_id, 'processing', 'PDF转换中...', 50)

        # 使用现有的pdf_converter模块进行转换
        from pdf_processor.pdf_converter import wechat_pdf_to_excel

        # 调用转换函数 - 传递临时输出目录
        result_path = wechat_pdf_to_excel(pdf_path, temp_output_dir)

        if not result_path:
            update_task_status(task_id, 'failed', 'PDF转换失败')
            return

        # 从返回的完整路径中提取生成的文件名（不含扩展名）
        generated_filename = os.path.basename(result_path)
        generated_report_name = os.path.splitext(generated_filename)[0]

        # 创建最终输出目录（使用生成的文件名）
        final_output_dir = os.path.join(app.config['OUTPUT_FOLDER'], generated_report_name)

        # 如果最终目录已存在，添加时间戳避免冲突
        if os.path.exists(final_output_dir):
            timestamp = datetime.datetime.now().strftime('%Y%m%d_%H%M%S')
            generated_report_name = f"{generated_report_name}_{timestamp}"
            final_output_dir = os.path.join(app.config['OUTPUT_FOLDER'], generated_report_name)

        # 创建最终目录
        if not os.path.exists(final_output_dir):
            os.makedirs(final_output_dir)

        # 移动生成的文件到最终目录
        final_file_path = os.path.join(final_output_dir, generated_filename)
        shutil.move(result_path, final_file_path)

        # 保存任务类型标识文件
        task_type_file = os.path.join(final_output_dir, '.task_type')
        with open(task_type_file, 'w') as f:
            f.write('pdf')

        # 清理临时目录
        shutil.rmtree(temp_output_dir, ignore_errors=True)

        # 更新任务状态，使用生成的报告名
        update_task_status(task_id, None, None, None, report_name=generated_report_name)

        # 准备文件列表
        files = [{
            'name': generated_filename,
            'path': final_file_path,
            'type': 'excel',
            'description': 'PDF转Excel结果'
        }]

        update_task_status(task_id, 'completed', '转换完成', 100, files)
        app.logger.info(f"PDF转换任务 {task_id} 完成，报告名: {generated_report_name}，文件: {final_file_path}")

        # 清理上传的PDF文件
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

    except Exception as e:
        app.logger.error(f"处理PDF时出现错误: {str(e)}", exc_info=True)
        update_task_status(task_id, 'failed', f'处理失败: {str(e)}')

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/upload', methods=['POST'])
def upload():
    try:
        app.logger.info(f"收到上传请求，请求方法：{request.method}")
        app.logger.info(f"Content-Type: {request.content_type}")
        app.logger.info(f"表单数据键：{list(request.form.keys())}")
        app.logger.info(f"文件数据键：{list(request.files.keys())}")
        # 检查请求中是否包含文件
        if not request.files:
            app.logger.error("请求中没有文件")
            flash('没有文件上传', 'error')
            return redirect(url_for('index'))
        # 获取上传的文件，获取第一个文件字段
        file_field_name = list(request.files.keys())[0]
        file = request.files[file_field_name]
        app.logger.info(f"获取到文件字段名: {file_field_name}")
        app.logger.info(f"文件名: {file.filename}")
        if file.filename == '':
            app.logger.error("文件名为空")
            flash('未选择文件', 'error')
            return redirect(url_for('index'))
        # 检查文件类型
        if file.filename.endswith('.zip'):
            # ZIP文件处理逻辑（保持原有代码不变）
            original_filename = os.path.splitext(file.filename)[0]
            file_dir = os.path.join(app.config['UPLOAD_FOLDER'], original_filename)
            if not os.path.exists(file_dir):
                os.makedirs(file_dir)
            zip_path = os.path.join(file_dir, file.filename)
            file.save(zip_path)
            app.logger.info(f"ZIP文件已保存: {zip_path}")
            # 解压到文件专属目录
            success, message = extract_zip_external(zip_path, file_dir)
            if not success:
                app.logger.error(f"使用外部工具解压失败: {message}")
                flash('解压文件失败，请检查文件完整性', 'error')
                return redirect(url_for('index'))
            # 删除ZIP文件
            os.remove(zip_path)
            # 查找包含 "-files" 的目录
            files_dir = None
            for item in os.listdir(file_dir):
                item_path = os.path.join(file_dir, item)
                if os.path.isdir(item_path) and "-files" in item:
                    files_dir = item_path
                    break
            if files_dir:
                input_dir = files_dir
                app.logger.info(f"找到 -files 目录作为输入: {input_dir}")
            else:
                # 如果没有找到 -files 目录，查找任何目录作为输入
                for item in os.listdir(file_dir):
                    item_path = os.path.join(file_dir, item)
                    if os.path.isdir(item_path):
                        input_dir = item_path
                        app.logger.info(f"使用目录作为输入: {input_dir}")
                        break
                else:
                    input_dir = file_dir
                    app.logger.info(f"没有找到子目录，使用解压根目录作为输入")
            # 生成任务ID
            task_id = str(uuid.uuid4())
            update_task_status(task_id, 'initialized', '任务已初始化，准备处理', 0, report_name=original_filename)
            # 启动异步处理
            import threading
            thread = threading.Thread(target=process_report, args=(task_id, input_dir, original_filename))
            thread.daemon = True
            thread.start()
            return redirect(url_for('task_status', task_id=task_id))
        elif file.filename.endswith('.pdf'):
            # PDF文件处理逻辑
            app.logger.info("检测到PDF文件，开始处理")

            # 创建临时保存目录
            temp_dir = os.path.join(app.config['UPLOAD_FOLDER'], 'pdf_temp')
            if not os.path.exists(temp_dir):
                os.makedirs(temp_dir)

            # 保存PDF文件
            pdf_filename = secure_filename(file.filename)
            pdf_path = os.path.join(temp_dir, pdf_filename)
            file.save(pdf_path)
            app.logger.info(f"PDF文件已保存: {pdf_path}")

            # 生成任务ID
            task_id = str(uuid.uuid4())

            # 初始化任务状态（暂时使用原始文件名）
            update_task_status(task_id, 'initialized', '任务已初始化，准备处理PDF', 0,
                               report_name=os.path.splitext(pdf_filename)[0])

            # 启动异步处理
            import threading
            thread = threading.Thread(target=process_pdf, args=(task_id, pdf_path, pdf_filename))
            thread.daemon = True
            thread.start()

            return redirect(url_for('task_status', task_id=task_id))
        else:
            app.logger.error(f"不支持的文件类型: {file.filename}")
            flash('仅支持ZIP和PDF格式文件', 'error')
            return redirect(url_for('index'))
    except Exception as e:
        app.logger.error(f"上传处理失败: {str(e)}", exc_info=True)
        flash(f'上传处理失败: {str(e)}', 'error')
        return redirect(url_for('index'))


@app.route('/status/<task_id>')
def task_status(task_id):
    if task_id not in tasks:
        flash('找不到指定任务', 'error')
        return redirect(url_for('index'))

    task = tasks[task_id]

    # 在应用上下文中为文件添加URL
    if task.get('status') == 'completed' and 'files' in task:
        for file in task['files']:
            file_name = file['name']
            file_type = file['type']

            # 添加下载URL
            file['url'] = url_for('download_file', task_id=task_id, file_name=file_name, file_type=file_type)

            # 只为报告类型文件添加预览URL
            if file_type == 'report':
                file['preview_url'] = url_for('preview_file', task_id=task_id, file_name=file_name)
            else:
                file['preview_url'] = None

    return render_template('status.html', task=task)


@app.route('/api/status/<task_id>')
def api_task_status(task_id):
    if task_id not in tasks:
        return jsonify({'error': 'Task not found'}), 404

    return jsonify(tasks[task_id])


@app.route('/download/<task_id>/<file_name>')
def download_file(task_id, file_name):
    if task_id not in tasks:
        return "Task not found", 404

    report_name = tasks[task_id].get('report_name', '')
    if not report_name:
        return "Report name not found", 404

    file_type = request.args.get('file_type', 'report')

    if file_type == 'report':
        file_path = os.path.join(app.config['OUTPUT_FOLDER'], report_name, file_name)
    elif file_type == 'database':
        file_path = os.path.join(app.config['DATABASE_FOLDER'], report_name, file_name)
    else:
        return "Invalid file type", 400

    if not os.path.exists(file_path):
        return f"File not found: {file_path}", 404

    return send_file(file_path, as_attachment=True)


@app.route('/preview/<task_id>/<file_name>')
def preview_file(task_id, file_name):
    if task_id not in tasks:
        return "Task not found", 404

    report_name = tasks[task_id].get('report_name', '')
    if not report_name:
        return "Report name not found", 404

    file_path = os.path.join(app.config['OUTPUT_FOLDER'], report_name, file_name)

    if not os.path.exists(file_path) or not file_name.endswith('.csv'):
        return "File not found or not supported for preview", 404

    # 读取CSV文件前100行用于预览
    import csv
    import pandas as pd
    from markupsafe import Markup

    preview_data = []
    try:
        with open(file_path, 'r', encoding='utf-8-sig') as f:
            csv_reader = csv.reader(f)
            headers = next(csv_reader)
            row_count = 0
            total_rows = sum(1 for _ in open(file_path, encoding='utf-8-sig')) - 1

            for row in csv_reader:
                preview_data.append(row)
                row_count += 1
                if row_count >= 100:  # 限制预览行数
                    break

            df = pd.DataFrame(preview_data, columns=headers)
            table_html = Markup(df.head(100).to_html(classes='table table-striped table-hover', index=False))

            # 返回集成了AI聊天的预览模板
            return render_template('preview.html',
                                   filename=file_name,
                                   table=table_html,
                                   shown_rows=min(100, total_rows),
                                   total_rows=total_rows,
                                   task_id=task_id)
    except Exception as e:
        app.logger.error(f"读取文件预览失败: {str(e)}", exc_info=True)
        return f"Error reading file: {str(e)}", 500


@app.route('/api/preview_data/<task_id>/<file_name>')
def api_preview_data(task_id, file_name):
    """提供当前预览数据的API，供AI聊天使用"""
    try:
        # 对临时任务ID的处理（从报告名直接预览的情况）
        if task_id.startswith('temp_'):
            # 修正：将下划线替换回空格，但保留URL编码的特殊字符
            report_name = task_id[5:].replace('_', ' ')
            app.logger.info(f"使用临时任务ID: {task_id}, 报告名: {report_name}")
        else:
            # 常规任务ID处理
            if task_id not in tasks:
                return jsonify({"error": "Task not found"}), 404
            report_name = tasks[task_id].get('report_name', '')
            app.logger.info(f"使用常规任务ID: {task_id}, 报告名: {report_name}")

        if not report_name:
            return jsonify({"error": "Report name not found"}), 404

        file_path = os.path.join(app.config['OUTPUT_FOLDER'], report_name, file_name)

        # 添加日志，帮助诊断
        app.logger.info(f"尝试访问文件: {file_path}")

        if not os.path.exists(file_path):
            return jsonify({"error": f"File not found: {file_path}"}), 404

        # 从环境变量获取样本数据条数
        from ai_chat import SAMPLE_DATA_ROWS

        import pandas as pd

        # 根据文件扩展名选择读取方式
        if file_name.endswith('.csv'):
            df = pd.read_csv(file_path, encoding='utf-8-sig')
        elif file_name.endswith('.xlsx'):
            df = pd.read_excel(file_path)
        else:
            return jsonify({"error": "Unsupported file format"}), 400

        return jsonify({
            "columns": df.columns.tolist(),
            "data": df.head(SAMPLE_DATA_ROWS).values.tolist(),  # 使用环境变量中配置的样本行数
            "total_rows": len(df),
            "sample_rows": SAMPLE_DATA_ROWS,  # 返回样本行数配置
            "report_name": report_name,  # 添加报告名称，便于前端显示
            "file_name": file_name  # 添加文件名称
        })
    except Exception as e:
        app.logger.error(f"读取文件数据API失败: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/cleanup', methods=['POST'])
def cleanup():
    try:
        task_id = request.form.get('task_id')
        if not task_id or task_id not in tasks:
            return jsonify({'success': False, 'error': '无效的任务ID'})

        # 获取原始文件名
        report_name = tasks[task_id].get('report_name', '')

        # 清理上传目录
        if report_name and os.path.exists(os.path.join(app.config['UPLOAD_FOLDER'], report_name)):
            shutil.rmtree(os.path.join(app.config['UPLOAD_FOLDER'], report_name))

        return jsonify({'success': True})
    except Exception as e:
        app.logger.error(f"清理失败: {str(e)}")
        return jsonify({'success': False, 'error': str(e)})


@app.errorhandler(413)
def request_entity_too_large(error):
    flash('上传文件超过最大允许大小', 'error')
    return redirect(url_for('index')), 413


@app.errorhandler(500)
def internal_server_error(error):
    app.logger.error(f"服务器内部错误: {str(error)}")
    return "服务器内部错误", 500


@app.route('/api/reports')
def api_reports():
    """获取所有已处理的报告列表"""
    try:
        reports = []
        # 扫描输出目录查找所有报告
        output_dirs = os.listdir(app.config['OUTPUT_FOLDER'])
        for report_name in output_dirs:
            report_dir = os.path.join(app.config['OUTPUT_FOLDER'], report_name)
            if os.path.isdir(report_dir):
                # ===== 读取任务类型 =====
                task_type = 'unknown'
                task_type_file = os.path.join(report_dir, '.task_type')
                if os.path.exists(task_type_file):
                    try:
                        with open(task_type_file, 'r') as f:
                            task_type = f.read().strip()
                    except:
                        task_type = 'unknown'

                # 获取该报告下的所有CSV和Excel文件
                files = []
                for file_name in os.listdir(report_dir):
                    if file_name.endswith(('.csv', '.xlsx')):  # 支持CSV和Excel
                        file_path = os.path.join(report_dir, file_name)
                        temp_task_id = f"temp_{report_name.replace(' ', '_')}"
                        files.append({
                            'name': file_name,
                            'path': file_path,
                            'type': 'report' if file_name.endswith('.csv') else 'excel',
                            'description': os.path.splitext(file_name)[0],
                            'preview_url': url_for('preview_report', report_name=report_name, file_name=file_name)
                        })

                # 只有存在文件时才添加到报告列表
                if files:
                    # 添加时间戳
                    timestamp = None
                    for task_id, task in tasks.items():
                        if task.get('report_name') == report_name:
                            timestamp = task.get('start_time')
                            break
                    if not timestamp:
                        timestamp = datetime.datetime.fromtimestamp(
                            os.path.getmtime(report_dir)).strftime('%Y-%m-%d %H:%M:%S')

                    reports.append({
                        'name': report_name,
                        'timestamp': timestamp,
                        'files': files,
                        'type': task_type  # ===== 添加任务类型 =====
                    })

        # 按时间戳降序排序
        reports.sort(key=lambda x: x['timestamp'], reverse=True)
        return jsonify(reports)
    except Exception as e:
        app.logger.error(f"获取报告列表失败: {str(e)}", exc_info=True)
        return jsonify({"error": str(e)}), 500


@app.route('/preview/report/<report_name>/<file_name>')
def preview_report(report_name, file_name):
    """直接通过报告名和文件名预览文件"""
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], report_name, file_name)

    if not os.path.exists(file_path):
        return "文件不存在", 404

    # 初始化变量
    table_html = None
    total_rows = 0

    # 支持CSV和Excel文件预览
    if file_name.endswith('.csv'):
        # CSV文件处理
        import csv
        import pandas as pd
        from markupsafe import Markup
        preview_data = []
        try:
            with open(file_path, 'r', encoding='utf-8-sig') as f:
                csv_reader = csv.reader(f)
                headers = next(csv_reader)
                row_count = 0
                total_rows = sum(1 for _ in open(file_path, encoding='utf-8-sig')) - 1
                for row in csv_reader:
                    preview_data.append(row)
                    row_count += 1
                    if row_count >= 100:
                        break
                df = pd.DataFrame(preview_data, columns=headers)
                table_html = Markup(df.head(100).to_html(classes='table table-striped table-hover', index=False))
        except Exception as e:
            app.logger.error(f"读取CSV文件失败: {str(e)}", exc_info=True)
            return f"读取文件失败: {str(e)}", 500

    elif file_name.endswith('.xlsx'):
        # Excel文件处理
        import pandas as pd
        from markupsafe import Markup
        try:
            # 先读取前100行用于预览
            df = pd.read_excel(file_path, nrows=100)
            # 单独获取总行数（这样更高效）
            total_rows = len(pd.read_excel(file_path, usecols=[0]))  # 只读取第一列来计算行数
            table_html = Markup(df.to_html(classes='table table-striped table-hover', index=False))
        except Exception as e:
            app.logger.error(f"读取Excel文件失败: {str(e)}", exc_info=True)
            return f"读取文件失败: {str(e)}", 500
    else:
        return "不支持的文件格式", 400

    # 生成临时任务ID
    temp_task_id = f"temp_{report_name.replace(' ', '_')}"
    app.logger.info(f"生成临时任务ID: {temp_task_id} 用于报告: {report_name}")

    # 返回预览模板
    return render_template('preview.html',
                           filename=file_name,
                           table=table_html,
                           shown_rows=min(100, total_rows),
                           total_rows=total_rows,
                           task_id=temp_task_id,
                           report_name=report_name)


@app.route('/download/report/<report_name>/<file_name>')
def download_report_file(report_name, file_name):
    """直接通过报告名和文件名下载文件"""
    file_path = os.path.join(app.config['OUTPUT_FOLDER'], report_name, file_name)

    if not os.path.exists(file_path):
        return "文件不存在", 404

    return send_file(file_path, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True,threaded=True,port=5000,host="0.0.0.0")
