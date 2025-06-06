/**
 * AI聊天集成脚本 - 修复版
 * 处理与AI模型的交互，支持在预览页面中分析数据
 */

class AIChatIntegration {
    constructor() {
        this.chatContainer = document.getElementById('chat-messages');
        this.userInput = document.getElementById('user-input');
        this.sendButton = document.getElementById('send-button');
        this.modelOptions = document.querySelectorAll('.model-option');

        this.taskId = document.getElementById('task-id')?.value;
        this.fileName = document.getElementById('file-name')?.value;

        this.selectedModel = 'deepseek';
        this.isWaitingForResponse = false;
        this.messageCounter = 0;
        this.shouldScrollToBottom = true;
        this.activeEventSource = null;
    }

    init() {
        if (!this.validateElements()) return;
        this.setupEventListeners();
        this.addWelcomeMessage();
        this.userInput.focus();

        // 添加页面卸载事件监听器，确保连接被关闭
        window.addEventListener('beforeunload', () => {
            if (this.activeEventSource) {
                console.log('页面卸载，关闭EventSource连接');
                this.activeEventSource.close();
                this.activeEventSource = null;
            }
        });
    }

    validateElements() {
        if (!this.chatContainer || !this.userInput || !this.sendButton) {
            console.warn("未找到聊天界面元素，可能在其他页面");
            return false;
        }

        if (!this.taskId || !this.fileName) {
            console.error('缺少任务ID或文件名信息');
            this.displayErrorMessage('系统配置错误: 缺少必要参数');
            return false;
        }

        return true;
    }

    setupEventListeners() {
        // 滚动检测
        this.chatContainer.addEventListener('scroll', () => {
            const isAtBottom = this.chatContainer.scrollHeight -
                               this.chatContainer.scrollTop -
                               this.chatContainer.clientHeight < 20;
            this.shouldScrollToBottom = isAtBottom;
        });

        // 模型选择
        this.modelOptions.forEach(option => {
            option.addEventListener('click', () => {
                this.modelOptions.forEach(opt => opt.classList.remove('active'));
                option.classList.add('active');
                this.selectedModel = option.dataset.model;
                console.log(`已选择模型: ${this.selectedModel}`);
            });
        });

        // 发送消息
        this.sendButton.addEventListener('click', () => this.sendMessage());

        // 回车发送
        this.userInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter' && !e.shiftKey) {
                e.preventDefault();
                this.sendMessage();
            }
        });
    }

    addWelcomeMessage() {
        this.addMessage('ai',
            `我是AI助手，可以帮你分析这份数据文件 "${this.fileName}"。你可以询问关于数据的任何问题！`);
    }

    async sendMessage() {
        const message = this.userInput.value.trim();
        if (!message || this.isWaitingForResponse) return;

        // 显示用户消息并重置输入
        this.addMessage('user', message);
        this.userInput.value = '';
        this.shouldScrollToBottom = true;
        this.scrollToBottom();

        // 准备AI响应容器
        this.messageCounter++;
        const currentMessageId = `response-${this.messageCounter}`;
        const typingIndicator = this.showTypingIndicator();

        try {
            // 获取数据上下文
            const dataContext = await this.fetchDataContext();

            // 发送聊天请求 - 修改为直接使用/api/chat路由
            await this.sendChatRequest(message, dataContext, currentMessageId, typingIndicator);
        } catch (error) {
            console.error('发送消息失败:', error);
            this.displayErrorMessage(`请求失败: ${error.message}`, typingIndicator);
        }
    }

    async fetchDataContext() {
        try {
            console.log(`正在获取数据: 任务ID=${this.taskId}, 文件名=${this.fileName}`);

            const response = await fetch(`/api/preview_data/${this.taskId}/${this.fileName}`);

            if (!response.ok) {
                const errorText = await response.text();
                console.error(`获取数据失败: ${response.status} ${response.statusText}`, errorText);
                throw new Error(`获取数据失败: ${response.statusText}`);
            }

            const data = await response.json();
            console.log('成功获取数据:', data);
            return data;
        } catch (error) {
            console.error('获取数据上下文时出错:', error);
            throw error;
        }
    }

    showTypingIndicator() {
        const indicator = document.createElement('div');
        indicator.className = 'typing-indicator';
        indicator.innerHTML = '<span></span><span></span><span></span>';
        this.chatContainer.appendChild(indicator);
        this.scrollToBottom();

        this.isWaitingForResponse = true;
        this.sendButton.disabled = true;
        this.userInput.disabled = true;

        return indicator;
    }

    async sendChatRequest(userMessage, dataContext, messageId, typingIndicator) {
        try {
            // 关闭现有连接
            if (this.activeEventSource) {
                console.log("关闭现有的EventSource连接");
                this.activeEventSource.close();
                this.activeEventSource = null;
            }

            // 构建提示信息
            const prompt = this.buildPrompt(userMessage, dataContext);

            console.log("步骤1: 创建聊天会话...");

            // 步骤1: 使用POST请求创建会话
            const sessionResponse = await fetch('/api/create_session', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    message: prompt,
                    model: this.selectedModel,
                    task_id: this.taskId,
                    file_name: this.fileName
                })
            });

            if (!sessionResponse.ok) {
                const errorText = await sessionResponse.text();
                console.error(`创建会话失败: HTTP ${sessionResponse.status}`, errorText);
                throw new Error(`创建会话失败: ${sessionResponse.statusText}`);
            }

            const sessionData = await sessionResponse.json();
            const sessionId = sessionData.session_id;

            if (!sessionId) {
                throw new Error('服务器未返回有效的会话ID');
            }

            console.log(`步骤1完成: 已创建会话 ${sessionId}`);

            // 步骤2: 使用EventSource连接到流式API
            console.log(`步骤2: 创建流式连接...`);
            const cacheBuster = Date.now();
            const eventSourceUrl = `/api/stream/${sessionId}?_=${cacheBuster}`;

            console.log(`创建EventSource连接: ${eventSourceUrl}`);
            this.activeEventSource = new EventSource(eventSourceUrl);

            let aiResponse = '';
            let aiMessageDiv = null;

            this.activeEventSource.onopen = (event) => {
                console.log(`EventSource连接已打开`);
            };

            this.activeEventSource.onmessage = (event) => {
                try {
                    // 记录原始数据用于调试
                    console.debug('收到原始数据:', event.data);

                    if (event.data === '[DONE]') {
                        console.log("收到完成标记，关闭连接");
                        this.cleanupAfterResponse();
                        return;
                    }

                    // 更安全的JSON解析
                    let data;
                    try {
                        data = JSON.parse(event.data);
                    } catch (parseError) {
                        console.warn("JSON解析失败，原始数据:", event.data);
                        console.warn("解析错误:", parseError);
                        // 尝试清理数据后再解析
                        const cleanedData = event.data.replace(/^data:\s*/, '').trim();
                        try {
                            data = JSON.parse(cleanedData);
                            console.log("使用清理后的数据成功解析");
                        } catch (secondError) {
                            console.error("第二次解析也失败:", secondError);
                            // 忽略此消息而不是终止整个流
                            return;
                        }
                    }

                    if (data.error) {
                        this.displayErrorMessage(data.error, typingIndicator);
                        this.cleanupAfterResponse();
                        return;
                    }

                    if (!aiMessageDiv) {
                        this.createAiMessageElement(messageId, typingIndicator);
                        aiMessageDiv = document.getElementById(messageId);
                    }

                    if (data.text) {
                        aiResponse += data.text;
                        this.updateMessageContent(aiMessageDiv, aiResponse, data.type);
                    }
                } catch (error) {
                    console.error('处理AI响应时出错:', error);
                    console.error('原始数据:', event.data);
                    // 不终止处理，尝试继续接收后续消息
                }
            };

            this.activeEventSource.onerror = (error) => {
                console.error('EventSource错误:', error);
                this.displayErrorMessage('连接错误，请稍后再试', typingIndicator);
                this.cleanupAfterResponse();
            };
        } catch (error) {
            console.error('发送聊天请求失败:', error);
            this.displayErrorMessage(`请求失败: ${error.message}`, typingIndicator);
            this.cleanupAfterResponse();
        }
    }


    buildPrompt(userMessage, dataContext) {
        const sampleRows = dataContext.sample_rows || 5; // 使用服务器返回的样本数据条数，如果没有则默认为5条
        return `以下是我正在分析的CSV文件"${this.fileName}"数据:

列名: ${dataContext.columns.join(', ')}
总行数: ${dataContext.total_rows}
样本数据 (前${Math.min(dataContext.data.length, sampleRows)}行):
${this.formatSampleData(dataContext.data.slice(0, sampleRows), dataContext.columns)}

基于以上数据，请回答以下问题:
${userMessage}`;
    }

    createAiMessageElement(messageId, typingIndicator) {
        if (typingIndicator && document.contains(typingIndicator)) {
            this.chatContainer.removeChild(typingIndicator);
        }

        const aiMessageDiv = document.createElement('div');
        aiMessageDiv.className = 'message ai-message';

        const modelBadge = document.createElement('span');
        modelBadge.className = `model-badge ${this.selectedModel}-badge`;
        modelBadge.textContent = this.selectedModel;

        const modelInfo = document.createElement('div');
        modelInfo.className = 'model-info';
        modelInfo.appendChild(modelBadge);
        aiMessageDiv.appendChild(modelInfo);

        const contentSpan = document.createElement('div');
        contentSpan.id = messageId;
        contentSpan.className = 'message-content';
        aiMessageDiv.appendChild(contentSpan);
        this.chatContainer.appendChild(aiMessageDiv);
    }

    updateMessageContent(element, content, contentType) {
        try {
            element.innerHTML = this.formatMessage(content);

            if (contentType === 'thinking') {
                this.processThinkingContent(element);
            }

            if (this.shouldScrollToBottom) {
                this.scrollToBottom();
            }
        } catch (err) {
            console.error("渲染消息时出错:", err);
            element.textContent = content;
        }
    }

    cleanupAfterResponse() {
        if (this.activeEventSource) {
            console.log(`关闭EventSource连接`);
            this.activeEventSource.close();
            this.activeEventSource = null;
        }
        this.isWaitingForResponse = false;
        this.sendButton.disabled = false;
        this.userInput.disabled = false;
        this.userInput.focus();
    }

    addMessage(role, content) {
        const messageDiv = document.createElement('div');
        messageDiv.className = `message ${role}-message`;

        if (role === 'ai') {
            const modelBadge = document.createElement('span');
            modelBadge.className = `model-badge ${this.selectedModel}-badge`;
            modelBadge.textContent = this.selectedModel;

            const modelInfo = document.createElement('div');
            modelInfo.className = 'model-info';
            modelInfo.appendChild(modelBadge);
            messageDiv.appendChild(modelInfo);

            const contentSpan = document.createElement('div');
            contentSpan.className = 'message-content';
            contentSpan.innerHTML = this.formatMessage(content);
            messageDiv.appendChild(contentSpan);
        } else {
            messageDiv.textContent = content;
        }

        this.chatContainer.appendChild(messageDiv);
        this.scrollToBottom();
    }

    formatSampleData(data, columns) {
        if (!data || data.length === 0) return '没有样本数据';

        return data.map((row, i) =>
            `行 ${i+1}: ${columns.map((col, j) => `${col}="${row[j]}"`).join(' ')}`
        ).join('\n');
    }

    formatMessage(text) {
        // 代码块处理
        let formattedText = text.replace(/```([\s\S]*?)```/g, (match, code) => {
            const languageMatch = code.match(/^([a-zA-Z0-9]+)\n/);
            if (languageMatch) {
                const language = languageMatch[1];
                const codeContent = code.slice(language.length + 1);
                return `<pre><code class="language-${language}">${this.escapeHtml(codeContent)}</code></pre>`;
            }
            return `<pre><code>${this.escapeHtml(code)}</code></pre>`;
        });

        // 其他Markdown格式化...
        formattedText = formattedText.replace(/`([^`]+)`/g, '<code>$1</code>')
                                    .replace(/^#+ (.*$)/gm, '<h2>$1</h2>')
                                    .replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>')
                                    .replace(/\*(.*?)\*/g, '<em>$1</em>')
                                    .replace(/\n\s*\n/g, '<br><br>')
                                    .replace(/\n/g, '<br>');

        return formattedText;
    }

    escapeHtml(unsafe) {
        return unsafe.replace(/&/g, "&amp;")
                    .replace(/</g, "&lt;")
                    .replace(/>/g, "&gt;")
                    .replace(/"/g, "&quot;")
                    .replace(/'/g, "&#039;");
    }

    processThinkingContent(element) {
        // 同时支持 <thinking> 和 <think> 标签
        element.innerHTML = element.innerHTML.replace(
            /<(thinking|think)>([\s\S]*?)<\/(thinking|think)>/gi,
            (match, openTag, content, closeTag) => `
                <div class="thinking-content">
                    ${content.trim()}
                    <button class="toggle-thinking">折叠</button>
                </div>
            `
        );

        // 添加事件监听器
        element.querySelectorAll('.toggle-thinking').forEach(button => {
            button.addEventListener('click', function() {
                const thinkingDiv = this.parentElement;
                thinkingDiv.classList.toggle('collapsed');
                this.textContent = thinkingDiv.classList.contains('collapsed') ? '展开' : '折叠';
            });
        });
    }

    displayErrorMessage(message, indicator = null) {
        if (indicator && document.contains(indicator)) {
            this.chatContainer.removeChild(indicator);
        }

        const errorDiv = document.createElement('div');
        errorDiv.className = 'error-message';
        errorDiv.textContent = message;
        this.chatContainer.appendChild(errorDiv);

        this.cleanupAfterResponse();
        this.scrollToBottom();
    }

    scrollToBottom() {
        this.chatContainer.scrollTo({
            top: this.chatContainer.scrollHeight,
            behavior: 'smooth'
        });
    }
}

// 初始化
document.addEventListener('DOMContentLoaded', () => {
    const chat = new AIChatIntegration();
    chat.init();
});

// 全局函数
window.toggleThinking = function(button) {
    const thinkingDiv = button.parentElement;
    thinkingDiv.classList.toggle('collapsed');
    button.textContent = thinkingDiv.classList.contains('collapsed') ? '展开' : '折叠';
};

window.addEventListener('error', function(event) {
    console.error('全局错误:', event.error);
    // 如果有活动的EventSource连接，尝试关闭它
    if (window.activeEventSource) {
        console.log('检测到错误，关闭EventSource连接');
        window.activeEventSource.close();
        window.activeEventSource = null;
    }
});
