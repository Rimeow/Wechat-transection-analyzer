from flask import Blueprint
import threading
import time

# 创建蓝图
chat_blueprint = Blueprint('chat', __name__,
                          template_folder='templates',
                          static_folder='static')

# 导入视图
from . import chat
from .chat import SAMPLE_DATA_ROWS


# 添加初始化函数
def init_app(app):
    """初始化聊天模块"""
    pass


def session_cleanup_thread():
    """定期清理过期会话的后台线程"""
    from .chat import cleanup_expired_sessions

    while True:
        time.sleep(300)  # 每5分钟检查一次
        try:
            cleanup_expired_sessions()
        except Exception as e:
            print(f"清理会话时出错: {e}")


def init_app(app):
    """初始化聊天模块"""
    # 启动会话清理线程
    cleanup_thread = threading.Thread(target=session_cleanup_thread)
    cleanup_thread.daemon = True
    cleanup_thread.start()