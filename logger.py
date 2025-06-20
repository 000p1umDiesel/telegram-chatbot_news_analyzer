import logging
import os
from datetime import datetime

# Создаем директорию для логов, если её нет
LOGS_DIR = "logs"
if not os.path.exists(LOGS_DIR):
    os.makedirs(LOGS_DIR)

# Формируем имя файла лога с текущей датой
current_date = datetime.now().strftime("%Y-%m-%d")
log_file = os.path.join(LOGS_DIR, f"telelytics_{current_date}.log")

# Настраиваем форматтер для логов
formatter = logging.Formatter(
    "%(asctime)s - %(levelname)s - %(message)s", datefmt="%Y-%m-%d %H:%M:%S"
)

# Настраиваем файловый handler
file_handler = logging.FileHandler(log_file, encoding="utf-8")
file_handler.setFormatter(formatter)

# Настраиваем консольный handler
console_handler = logging.StreamHandler()
console_handler.setFormatter(formatter)

# Настраиваем корневой logger
logger = logging.getLogger()
logger.setLevel(logging.INFO)
logger.addHandler(file_handler)
logger.addHandler(console_handler)


def get_logger():
    return logger
