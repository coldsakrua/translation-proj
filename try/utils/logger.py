import logging
from logging.handlers import RotatingFileHandler
import os

def setup_logger(name, log_file, level=logging.INFO):
    # 1. 确保日志目录存在
    log_dir = os.path.dirname(log_file)
    if log_dir and not os.path.exists(log_dir):
        os.makedirs(log_dir, exist_ok=True)

    formatter = logging.Formatter(
        "[%(asctime)s] [%(levelname)s] [%(name)s] %(message)s"
    )

    handler = RotatingFileHandler(
        log_file,
        maxBytes=5 * 1024 * 1024,
        backupCount=3,
        encoding="utf-8"
    )
    handler.setFormatter(formatter)

    logger = logging.getLogger(name)

    # 2. 防止重复添加 handler（这是个隐蔽坑）
    if not logger.handlers:
        logger.setLevel(level)
        logger.addHandler(handler)

    logger.propagate = False
    return logger
