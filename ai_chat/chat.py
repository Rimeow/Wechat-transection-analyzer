from flask import request, jsonify, render_template, Response, stream_with_context
import requests
import os
import json
import uuid
import time
from urllib.parse import unquote
from dotenv import load_dotenv
from . import chat_blueprint

# 加载环境变量
load_dotenv()
active_sessions = {}

# 配置API密钥
DEEPSEEK_API_KEY = os.getenv("DEEPSEEK_API_KEY")
OLLAMA_HOST = os.getenv("OLLAMA_HOST", "http://localhost:11434")
# 默认的Ollama模型，可通过环境变量覆盖
OLLAMA_DEFAULT_MODEL = os.getenv("OLLAMA_DEFAULT_MODEL", "deepseek-r1:32b")
# 添加样本数据条数配置，默认为5条
SAMPLE_DATA_ROWS = int(os.getenv("SAMPLE_DATA_ROWS", "5"))

# 日志输出控制
VERBOSE_LOGGING = os.getenv("VERBOSE_LOGGING", "false").lower() == "true"

if not DEEPSEEK_API_KEY:
    print("警告: 未设置DeepSeek API密钥。请创建.env文件并设置DEEPSEEK_API_KEY")


@chat_blueprint.route('/')
def index():
    """AI聊天独立页面"""
    return render_template('chat.html')


@chat_blueprint.route('/api/ollama/status')
def ollama_status():
    """检查Ollama服务器状态"""
    try:
        response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=5)
        if response.status_code == 200:
            models = response.json().get('models', [])
            return jsonify({
                'status': 'online',
                'models': [model.get('name') for model in models],
                'default_model': OLLAMA_DEFAULT_MODEL
            })
        else:
            return jsonify({'status': 'error', 'message': f"API返回非200状态: {response.status_code}"})
    except requests.exceptions.RequestException as e:
        return jsonify({'status': 'offline', 'error': str(e)})


@chat_blueprint.route('/api/chat', methods=['GET', 'POST'])
def chat():
    """AI聊天API接口 - 完全恢复旧版方式"""
    print(f"收到{request.method}请求到/api/chat")

    # 根据请求类型获取参数
    if request.method == 'POST':
        try:
            # 简化日志输出
            print(f"POST请求到/api/chat - 内容长度: {len(request.get_data(as_text=True))}")

            data = request.get_json(silent=True) or {}
            user_message = data.get('message', '')
            model_choice = data.get('model', 'deepseek')

            print(f"解析的JSON: message长度={len(user_message)}, model={model_choice}")

            # POST请求成功接收
            return jsonify({"status": "success"})
        except Exception as e:
            print(f"处理POST请求时出错: {e}")
            return jsonify({"error": str(e)}), 500
    else:  # GET 请求 (用于 EventSource)
        try:
            # 简化日志输出
            print(f"GET请求到/api/chat - 参数数量: {len(request.args)}")

            user_message = request.args.get('message', '')
            model_choice = request.args.get('model', 'deepseek')
            task_id = request.args.get('task_id', '')
            file_name = request.args.get('file_name', '')

            # 记录接收到的消息开头和任务信息
            print(f"接收到消息长度: {len(user_message)} 字符, 任务ID: {task_id}, 文件名: {file_name}")

            if not user_message:
                return jsonify({'error': '消息不能为空'}), 400

            # 根据选择的模型调用不同的API
            if model_choice == 'deepseek':
                return chat_with_deepseek(user_message)
            elif model_choice == 'ollama':
                return chat_with_ollama(user_message)
            else:
                return jsonify({'error': '不支持的模型选择'}), 400
        except Exception as e:
            print(f"处理GET请求时出错: {e}")
            return jsonify({"error": str(e)}), 500


def chat_with_deepseek(user_message):
    """调用DeepSeek API进行对话"""
    print(f"使用DeepSeek处理消息 (长度: {len(user_message)} 字符)")

    def generate():
        headers = {
            'Content-Type': 'application/json',
            'Authorization': f'Bearer {DEEPSEEK_API_KEY}'
        }

        payload = {
            'model': 'deepseek-chat',
            'messages': [
                {'role': 'system',
                 'content': '你是一个专业的数据分析AI助手，擅长帮助用户理解和分析数据。请提供清晰、准确的分析和建议。'},
                {'role': 'user', 'content': user_message}
            ],
            'stream': True
        }

        try:
            print("发送请求到DeepSeek API...")
            response = requests.post(
                'https://api.deepseek.com/v1/chat/completions',
                headers=headers,
                json=payload,
                stream=True,
                timeout=60  # 增加超时时间到60秒
            )

            if response.status_code != 200:
                error_msg = f"DeepSeek API调用失败: HTTP {response.status_code}"
                print(error_msg)
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                return

            print("开始流式处理DeepSeek响应...")
            token_count = 0
            progress_marker = 0

            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8').strip()

                    # 详细日志仅在开启详细模式时显示
                    if VERBOSE_LOGGING:
                        print(f"收到行: {line_text[:50]}...")

                    if line_text.startswith('data: '):
                        line_text = line_text[6:]  # 移除 "data: " 前缀

                        if line_text == "[DONE]":
                            print("流式响应完成，共接收 %d 个token" % token_count)
                            yield "data: [DONE]\n\n"
                            return

                        try:
                            json_data = json.loads(line_text)
                            delta = json_data.get('choices', [{}])[0].get('delta', {}).get('content', '')
                            if delta:
                                token_count += 1
                                # 每接收10个token更新一次进度
                                if token_count % 10 == 0:
                                    new_marker = token_count // 10
                                    if new_marker > progress_marker:
                                        progress_marker = new_marker
                                        print(
                                            f"DeepSeek响应进度: 已接收 {token_count} 个token {'.' * (progress_marker % 10)}")

                                # 统一格式
                                output = f"data: {json.dumps({'text': delta})}\n\n"
                                yield output
                        except json.JSONDecodeError as e:
                            print(f"JSON解析错误: {e}, 原始数据长度: {len(line_text)}")
                            continue

            # 确保结束标记发送
            yield "data: [DONE]\n\n"

        except requests.exceptions.Timeout:
            error_message = "DeepSeek API请求超时"
            print(error_message)
            yield f"data: {json.dumps({'error': error_message})}\n\n"
        except requests.exceptions.ConnectionError:
            error_message = "无法连接DeepSeek API服务器"
            print(error_message)
            yield f"data: {json.dumps({'error': error_message})}\n\n"
        except Exception as e:
            error_message = f"API调用异常: {str(e)}"
            print(error_message)
            yield f"data: {json.dumps({'error': error_message})}\n\n"

    response = Response(stream_with_context(generate()), content_type='text/event-stream')
    # 添加必要的头部以防止缓存
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


def chat_with_ollama(user_message):
    """调用本地Ollama API进行对话"""
    print(f"使用Ollama处理消息 (长度: {len(user_message)} 字符)")

    def generate():
        # 首先检查Ollama是否可用
        try:
            # 使用短超时快速检查连接
            check_response = requests.get(f"{OLLAMA_HOST}/api/tags", timeout=3)

            # 如果无法连接，会抛出异常，这里处理正常情况
            if check_response.status_code != 200:
                error_msg = f"Ollama服务返回非200状态: {check_response.status_code}"
                print(error_msg)
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                return

            # 获取可用模型列表
            models = check_response.json().get('models', [])
            available_models = [model.get('name') for model in models]

            # 使用环境变量中的默认模型，确保它在可用列表中
            ollama_model = OLLAMA_DEFAULT_MODEL
            if not models or ollama_model not in [m.split(':')[0] for m in available_models]:
                # 尝试找到可用的替代模型
                if available_models:
                    ollama_model = available_models[0]
                    print(f"默认模型不可用，使用 {ollama_model} 替代")
                else:
                    error_msg = "Ollama服务没有可用模型"
                    print(error_msg)
                    yield f"data: {json.dumps({'error': error_msg})}\n\n"
                    return

            print(f"使用Ollama模型: {ollama_model}")

        except requests.exceptions.RequestException as e:
            error_msg = f"Ollama服务连接失败: {str(e)}"
            print(error_msg)
            yield f"data: {json.dumps({'error': error_msg})}\n\n"
            return

        # 准备请求数据
        payload = {
            'model': ollama_model,
            'messages': [
                {'role': 'system',
                 'content': '你是一个专业的数据分析AI助手，擅长帮助用户理解和分析数据。当需要思考时，请将思考过程用<think>和</think>标签包裹。'},
                {'role': 'user', 'content': user_message}
            ],
            'stream': True
        }

        try:
            print(f"发送请求到Ollama: {OLLAMA_HOST}/api/chat")
            response = requests.post(
                f"{OLLAMA_HOST}/api/chat",
                json=payload,
                stream=True,
                timeout=60  # 60秒超时
            )

            if response.status_code != 200:
                error_msg = f"Ollama API调用失败: HTTP {response.status_code}"
                print(error_msg)
                yield f"data: {json.dumps({'error': error_msg})}\n\n"
                return

            print("开始流式处理Ollama响应...")
            last_content = ""
            full_content = ""  # 用于跟踪完整内容
            token_count = 0
            progress_marker = 0

            for line in response.iter_lines():
                if line:
                    line_text = line.decode('utf-8').strip()

                    # 详细日志仅在开启详细模式时显示
                    if VERBOSE_LOGGING:
                        print(f"收到Ollama行: {line_text[:50]}...")

                    try:
                        json_data = json.loads(line_text)

                        # 处理不同的响应格式
                        if 'message' in json_data and 'content' in json_data['message']:
                            # 标准Ollama响应
                            content = json_data['message']['content']
                            full_content = content  # 替换而不是累加，因为这是完整内容
                        elif 'response' in json_data:
                            # 旧版或替代格式
                            new_chunk = json_data['response']
                            full_content += new_chunk
                            content = full_content
                        else:
                            # 尝试其他可能的字段
                            content = (json_data.get('content') or
                                       json_data.get('text') or
                                       json_data.get('delta', {}).get('content', ''))
                            if content:
                                full_content += content

                        # 如果有内容变化，发送更新
                        if full_content and full_content != last_content:
                            response_type = 'thinking' if '<think>' in full_content.lower() else None

                            # 确定增量内容
                            if last_content:
                                # 尝试找出新增的内容
                                if full_content.startswith(last_content):
                                    delta = full_content[len(last_content):]
                                else:
                                    # 如果不是简单的追加，就发送整个内容
                                    delta = full_content
                            else:
                                delta = full_content

                            if delta:  # 只有在有新内容时才发送
                                token_count += len(delta.split())
                                # 每接收10个token更新一次进度
                                if token_count % 10 == 0:
                                    new_marker = token_count // 10
                                    if new_marker > progress_marker:
                                        progress_marker = new_marker
                                        print(
                                            f"Ollama响应进度: 已接收约 {token_count} 个token {'.' * (progress_marker % 10)}")

                                output = f"data: {json.dumps({'text': delta, 'type': response_type})}\n\n"
                                yield output

                            last_content = full_content

                        # 检查是否完成
                        if json_data.get('done') is True:
                            print(f"Ollama响应标记为完成，共接收约 {token_count} 个token")
                            break

                    except json.JSONDecodeError as e:
                        print(f"Ollama JSON解析错误: {e}, 原始数据长度: {len(line_text)}")
                        continue
                    except Exception as e:
                        print(f"处理Ollama响应时出错: {str(e)}")
                        continue

            print("Ollama流式响应完成")
            yield "data: [DONE]\n\n"

        except requests.exceptions.Timeout:
            error_message = "Ollama API请求超时"
            print(error_message)
            yield f"data: {json.dumps({'error': error_message})}\n\n"
        except requests.exceptions.ConnectionError:
            error_message = "无法连接Ollama服务器"
            print(error_message)
            yield f"data: {json.dumps({'error': error_message})}\n\n"
        except Exception as e:
            error_message = f"Ollama API调用异常: {str(e)}"
            print(error_message)
            yield f"data: {json.dumps({'error': error_message})}\n\n"
        finally:
            yield "data: [DONE]\n\n"

    response = Response(stream_with_context(generate()), content_type='text/event-stream')
    # 添加必要的头部以防止缓存
    response.headers['Cache-Control'] = 'no-cache'
    response.headers['X-Accel-Buffering'] = 'no'
    return response


@chat_blueprint.route('/api/analyze', methods=['POST'])
def analyze_data():
    """用于分析上传的数据文件"""
    data = request.get_json(silent=True) or {}
    file_content = data.get('file_content', '')
    question = data.get('question', '')
    model_choice = data.get('model', 'deepseek')
    task_id = data.get('task_id', '')
    file_name = data.get('file_name', '')
    if not file_content or not question:
        return jsonify({'error': '缺少必要参数'}), 400
    prompt = f"""请分析以下数据并回答问题:
数据内容:
{file_content}
问题: {question}
请提供详细分析。
"""
    # 生成唯一会话ID
    session_id = str(uuid.uuid4())

    # 存储会话信息
    active_sessions[session_id] = {
        'message': prompt,
        'model': model_choice,
        'task_id': task_id,
        'file_name': file_name,
        'created_at': time.time()
    }

    return jsonify({'session_id': session_id})


@chat_blueprint.route('/create_session', methods=['POST'])
def create_session():
    """创建新的AI聊天会话"""
    try:
        # 简化日志输出
        print(f"POST请求到/create_session - 内容长度: {len(request.get_data(as_text=True))}")
        print(f"请求路径: {request.path}")
        print(f"请求URL: {request.url}")
        print(f"请求方法: {request.method}")

        # 只打印关键请求头
        headers = {k: v for k, v in request.headers.items()
                   if k.lower() in ['content-type', 'content-length', 'host', 'user-agent']}
        print(f"关键请求头: {headers}")

        data = request.get_json(silent=True) or {}
        user_message = data.get('message', '')
        model_choice = data.get('model', 'deepseek')
        task_id = data.get('task_id', '')
        file_name = data.get('file_name', '')
        if not user_message:
            print("错误: 消息不能为空")
            return jsonify({'error': '消息不能为空'}), 400
        # 生成唯一会话ID
        session_id = str(uuid.uuid4())
        # 存储会话信息
        active_sessions[session_id] = {
            'message': user_message,
            'model': model_choice,
            'task_id': task_id,
            'file_name': file_name,
            'created_at': time.time()
        }
        print(f"创建会话 {session_id} - 模型: {model_choice}, 任务ID: {task_id}, 文件: {file_name}")
        print(f"消息长度: {len(user_message)} 字符")
        return jsonify({'session_id': session_id})
    except Exception as e:
        print(f"创建会话失败: {e}")
        return jsonify({'error': str(e)}), 500


@chat_blueprint.route('/stream/<session_id>')
def stream_response(session_id):
    """流式返回AI响应"""
    print(f"请求流式响应: 会话ID={session_id}")

    # 解码 session_id 以处理特殊字符
    decoded_session_id = unquote(session_id)

    if decoded_session_id not in active_sessions:
        print(f"错误: 无效的会话ID {decoded_session_id}")
        return jsonify({'error': '无效的会话ID或会话已过期'}), 404

    session_data = active_sessions[decoded_session_id]
    user_message = session_data['message']
    model_choice = session_data['model']
    print(f"开始流式响应会话 {session_id} - 模型: {model_choice}")
    print(f"消息长度: {len(user_message)} 字符")

    # 根据模型选择调用不同的处理函数
    if model_choice == 'deepseek':
        return chat_with_deepseek(user_message)
    elif model_choice == 'ollama':
        return chat_with_ollama(user_message)
    else:
        print(f"错误: 不支持的模型选择 {model_choice}")
        return jsonify({'error': '不支持的模型选择'}), 400


# 添加一个定时清理过期会话的函数
def cleanup_expired_sessions():
    """清理超过30分钟的过期会话"""
    current_time = time.time()
    expired_sessions = []

    for session_id, session_data in active_sessions.items():
        if current_time - session_data.get('created_at', 0) > 1800:  # 30分钟 = 1800秒
            expired_sessions.append(session_id)

    for session_id in expired_sessions:
        print(f"清理过期会话: {session_id}")
        active_sessions.pop(session_id, None)
