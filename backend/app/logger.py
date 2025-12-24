"""
日志配置模块 - 将日志输出到文件和终端

支持多用户环境：
- 日志记录包含用户上下文
- 每个用户可以有独立的日志文件（可选）
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from logging.handlers import RotatingFileHandler
from contextvars import ContextVar
from typing import Optional

# 日志目录
LOG_DIR = Path(__file__).parent.parent / "logs"
LOG_DIR.mkdir(parents=True, exist_ok=True)

# 日志文件路径（按日期命名）
LOG_FILE = LOG_DIR / f"api_{datetime.now().strftime('%Y%m%d')}.log"

# 当前用户的上下文变量（用于日志记录）
_log_user_context: ContextVar[Optional[str]] = ContextVar('log_user_context', default=None)


def set_log_user_context(username: Optional[str]):
    """设置日志的用户上下文"""
    _log_user_context.set(username)


def get_log_user_context() -> Optional[str]:
    """获取日志的用户上下文"""
    return _log_user_context.get()


class UserContextFilter(logging.Filter):
    """日志过滤器：添加用户上下文到日志记录"""
    
    def filter(self, record):
        username = get_log_user_context()
        record.user = f"[{username}]" if username else ""
        return True


# 创建日志格式（包含用户上下文）
LOG_FORMAT = "%(asctime)s | %(levelname)-8s | %(user)s %(name)s | %(message)s"
DATE_FORMAT = "%Y-%m-%d %H:%M:%S"

# 详细格式（用于文件，包含用户上下文）
DETAILED_FORMAT = "%(asctime)s | %(levelname)-8s | %(user)s %(name)s:%(lineno)d | %(message)s"


def setup_logging(level: int = logging.INFO) -> logging.Logger:
    """
    配置全局日志系统
    
    Args:
        level: 日志级别，默认 INFO
        
    Returns:
        根日志记录器
    """
    # 获取根日志记录器
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    
    # 清除已有的处理器（避免重复添加）
    root_logger.handlers.clear()
    
    # 创建用户上下文过滤器
    user_filter = UserContextFilter()
    
    # 创建终端处理器
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(level)
    console_handler.setFormatter(logging.Formatter(LOG_FORMAT, DATE_FORMAT))
    console_handler.addFilter(user_filter)
    root_logger.addHandler(console_handler)
    
    # 创建文件处理器（轮转日志，最大10MB，保留10个备份）
    file_handler = RotatingFileHandler(
        LOG_FILE,
        maxBytes=10 * 1024 * 1024,  # 10MB
        backupCount=10,
        encoding='utf-8'
    )
    file_handler.setLevel(level)
    file_handler.setFormatter(logging.Formatter(DETAILED_FORMAT, DATE_FORMAT))
    file_handler.addFilter(user_filter)
    root_logger.addHandler(file_handler)
    
    # 设置第三方库日志级别（减少噪音）
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)
    
    return root_logger


def get_logger(name: str) -> logging.Logger:
    """
    获取指定名称的日志记录器
    
    Args:
        name: 日志记录器名称，通常使用 __name__
        
    Returns:
        日志记录器
    """
    return logging.getLogger(name)


class APILogger:
    """
    API 请求/响应日志记录器
    用于记录 DashScope API 调用的详细信息
    """
    
    def __init__(self, name: str):
        self.logger = get_logger(name)
    
    def request(self, service: str, model: str, **params):
        """记录 API 请求"""
        self.logger.info(f"{'='*60}")
        self.logger.info(f"[{service}请求] 模型: {model}")
        for key, value in params.items():
            if isinstance(value, str) and len(value) > 200:
                value = value[:200] + "..."
            self.logger.info(f"[{service}请求] {key}: {value}")
        self.logger.info(f"{'='*60}")
    
    def response(self, service: str, status_code: int, request_id: str = None, 
                 task_id: str = None, task_status: str = None, **extra):
        """记录 API 响应"""
        self.logger.info(f"{'='*60}")
        self.logger.info(f"[{service}响应] status_code: {status_code}")
        if request_id:
            self.logger.info(f"[{service}响应] request_id: {request_id}")
        if task_id:
            self.logger.info(f"[{service}响应] task_id: {task_id}")
        if task_status:
            self.logger.info(f"[{service}响应] task_status: {task_status}")
        for key, value in extra.items():
            self.logger.info(f"[{service}响应] {key}: {value}")
        self.logger.info(f"{'='*60}")
    
    def error(self, service: str, code: str, message: str, **extra):
        """记录 API 错误"""
        self.logger.error(f"{'!'*60}")
        self.logger.error(f"[{service}错误] code: {code}")
        self.logger.error(f"[{service}错误] message: {message}")
        for key, value in extra.items():
            self.logger.error(f"[{service}错误] {key}: {value}")
        self.logger.error(f"{'!'*60}")
    
    def status_query(self, service: str, task_id: str, status: str, **extra):
        """记录状态查询"""
        self.logger.info(f"[{service}状态查询] task_id: {task_id}, status: {status}")
        for key, value in extra.items():
            if isinstance(value, str) and len(value) > 100:
                value = value[:100] + "..."
            self.logger.info(f"[{service}状态查询] {key}: {value}")
    
    def info(self, message: str):
        """记录信息"""
        self.logger.info(message)
    
    def debug(self, message: str):
        """记录调试信息"""
        self.logger.debug(message)
    
    def warning(self, message: str):
        """记录警告"""
        self.logger.warning(message)


# 重定向 print 到日志（可选）
class PrintLogger:
    """将 print 输出重定向到日志文件"""
    
    def __init__(self, logger: logging.Logger, original_stdout):
        self.logger = logger
        self.original_stdout = original_stdout
    
    def write(self, message: str):
        # 写入原始 stdout
        self.original_stdout.write(message)
        # 同时写入日志文件（过滤空行）
        message = message.strip()
        if message:
            self.logger.info(message)
    
    def flush(self):
        self.original_stdout.flush()


def redirect_print_to_log():
    """将 print 输出重定向到日志文件"""
    logger = get_logger("print")
    sys.stdout = PrintLogger(logger, sys.stdout)


# 初始化日志系统
_initialized = False

def init_logging():
    """初始化日志系统（只执行一次）"""
    global _initialized
    if not _initialized:
        setup_logging()
        redirect_print_to_log()
        _initialized = True
        
        # 记录启动信息
        logger = get_logger("app")
        logger.info(f"日志系统已初始化")
        logger.info(f"日志文件: {LOG_FILE}")

