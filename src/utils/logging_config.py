"""
全局日志配置模块

提供统一的日志配置，支持：
1. 控制台输出（彩色）
2. 文件输出（JSON格式）
3. Verbose级别详细日志
4. API调用追踪
"""

import logging
import sys
from pathlib import Path
from datetime import datetime
from typing import Optional
import json


class VerboseFilter(logging.Filter):
    """Verbose级别过滤器"""
    
    def filter(self, record):
        # 添加额外的上下文信息
        if not hasattr(record, 'step'):
            record.step = 'unknown'
        if not hasattr(record, 'operation'):
            record.operation = 'unknown'
        if not hasattr(record, 'api_call'):
            record.api_call = False
        if not hasattr(record, 'char_count'):
            record.char_count = 0
        return True


class JSONFormatter(logging.Formatter):
    """JSON格式化器"""
    
    def format(self, record):
        log_data = {
            'timestamp': datetime.fromtimestamp(record.created).isoformat(),
            'level': record.levelname,
            'logger': record.name,
            'message': record.getMessage(),
        }
        
        # 添加额外字段
        if hasattr(record, 'step'):
            log_data['step'] = record.step
        if hasattr(record, 'operation'):
            log_data['operation'] = record.operation
        if hasattr(record, 'api_call') and record.api_call:
            log_data['api_call'] = True
            if hasattr(record, 'api_type'):
                log_data['api_type'] = record.api_type
            if hasattr(record, 'char_count'):
                log_data['char_count'] = record.char_count
            if hasattr(record, 'token_estimate'):
                log_data['token_estimate'] = record.token_estimate
        
        # 添加异常信息
        if record.exc_info:
            log_data['exception'] = self.formatException(record.exc_info)
        
        return json.dumps(log_data, ensure_ascii=False)


class ColoredConsoleFormatter(logging.Formatter):
    """彩色控制台格式化器"""
    
    COLORS = {
        'DEBUG': '\033[36m',      # 青色
        'INFO': '\033[32m',       # 绿色
        'WARNING': '\033[33m',    # 黄色
        'ERROR': '\033[31m',      # 红色
        'CRITICAL': '\033[35m',   # 紫色
    }
    RESET = '\033[0m'
    
    def format(self, record):
        # 添加颜色
        color = self.COLORS.get(record.levelname, self.RESET)
        record.levelname = f"{color}{record.levelname}{self.RESET}"
        
        # 格式化消息
        msg = super().format(record)
        
        # 添加额外信息（verbose模式）
        if hasattr(record, 'api_call') and record.api_call:
            api_info = f" [API: {getattr(record, 'api_type', 'unknown')}"
            if hasattr(record, 'char_count'):
                api_info += f", {record.char_count} chars"
            if hasattr(record, 'token_estimate'):
                api_info += f", ~{record.token_estimate} tokens"
            api_info += "]"
            msg += f"\033[90m{api_info}\033[0m"  # 灰色
        
        return msg


def setup_logging(
    run_dir: Optional[Path] = None,
    console_level: str = "INFO",
    file_level: str = "DEBUG",
    verbose: bool = False
) -> None:
    """
    配置全局日志
    
    Args:
        run_dir: 运行目录（用于保存日志文件）
        console_level: 控制台日志级别
        file_level: 文件日志级别
        verbose: 是否启用verbose模式（更详细的日志）
    """
    # 获取根logger
    root_logger = logging.getLogger()
    root_logger.setLevel(logging.DEBUG)  # 设置为最低级别，由handler控制
    
    # 清除现有handlers
    root_logger.handlers.clear()
    
    # 1. 控制台handler（彩色输出）
    console_handler = logging.StreamHandler(sys.stdout)
    console_handler.setLevel(getattr(logging, console_level.upper()))
    console_formatter = ColoredConsoleFormatter(
        '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%H:%M:%S'
    )
    console_handler.setFormatter(console_formatter)
    console_handler.addFilter(VerboseFilter())
    root_logger.addHandler(console_handler)
    
    # 2. 文件handler（JSON格式）
    if run_dir:
        log_dir = run_dir / "logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        
        # 主日志文件
        log_file = log_dir / "pipeline.log"
        file_handler = logging.FileHandler(log_file, encoding='utf-8')
        file_handler.setLevel(getattr(logging, file_level.upper()))
        file_handler.setFormatter(JSONFormatter())
        file_handler.addFilter(VerboseFilter())
        root_logger.addHandler(file_handler)
        
        # Verbose日志文件（如果启用）
        if verbose:
            verbose_file = log_dir / "pipeline_verbose.log"
            verbose_handler = logging.FileHandler(verbose_file, encoding='utf-8')
            verbose_handler.setLevel(logging.DEBUG)
            verbose_handler.setFormatter(JSONFormatter())
            verbose_handler.addFilter(VerboseFilter())
            root_logger.addHandler(verbose_handler)
    
    # 设置第三方库的日志级别（避免过多噪音）
    logging.getLogger('urllib3').setLevel(logging.WARNING)
    logging.getLogger('requests').setLevel(logging.WARNING)
    logging.getLogger('httpx').setLevel(logging.WARNING)
    logging.getLogger('httpcore').setLevel(logging.WARNING)


def log_step_start(logger: logging.Logger, step_name: str, **kwargs):
    """记录步骤开始"""
    logger.info(
        f">>> 开始执行: {step_name}",
        extra={'step': step_name, 'operation': 'start', **kwargs}
    )


def log_step_end(logger: logging.Logger, step_name: str, **kwargs):
    """记录步骤结束"""
    logger.info(
        f"<<< 完成执行: {step_name}",
        extra={'step': step_name, 'operation': 'end', **kwargs}
    )


def log_api_call(
    logger: logging.Logger,
    api_type: str,
    operation: str,
    char_count: int = 0,
    token_estimate: Optional[int] = None,
    **kwargs
):
    """
    记录API调用
    
    Args:
        logger: Logger实例
        api_type: API类型（LLM, Research, TTS等）
        operation: 操作描述
        char_count: 字符数
        token_estimate: token估算（可选）
        **kwargs: 其他额外信息
    """
    if token_estimate is None and char_count > 0:
        # 简单估算：中文约1.5字符/token，英文约4字符/token
        token_estimate = int(char_count / 2)
    
    logger.info(
        f"API调用: {api_type} - {operation}",
        extra={
            'api_call': True,
            'api_type': api_type,
            'operation': operation,
            'char_count': char_count,
            'token_estimate': token_estimate,
            **kwargs
        }
    )


def log_operation(
    logger: logging.Logger,
    step: str,
    operation: str,
    result: str = "",
    **kwargs
):
    """
    记录操作详情
    
    Args:
        logger: Logger实例
        step: 步骤名称
        operation: 操作描述
        result: 操作结果
        **kwargs: 其他额外信息
    """
    msg = f"{operation}"
    if result:
        msg += f" - {result}"
    
    logger.info(
        msg,
        extra={
            'step': step,
            'operation': operation,
            **kwargs
        }
    )
