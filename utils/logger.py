# utils/logger.py
# Simple logging helper for testing the Raspberry Pi project.

from datetime import datetime


def log(message, level="INFO"):
    current_time = datetime.now().strftime("%H:%M:%S")
    print(f"[{current_time}] [{level}] {message}")


def log_success(message):
    log(message, level="SUCCESS")


def log_error(message):
    log(message, level="ERROR")


def log_warning(message):
    log(message, level="WARNING")

