# import os
#
# DB_CONFIG = {
#     'host': 'localhost',
#     'port': 3306,
#     'user': 'root',
#     'password': '123456',
#     'database': 'plagiarism_db',
#     'charset': 'utf8mb4'
# }
#
# REDIS_CONFIG = {
#     'host': os.getenv('REDIS_HOST', 'localhost'),
#     'port': int(os.getenv('REDIS_PORT', 6379)),
#     'password': os.getenv('REDIS_PASSWORD', ''),  # 若启用 auth
#     'db': int(os.getenv('REDIS_DB', 0)),
#     'decode_responses': True  # 返回字符串
# }
#
# JWT_SECRET_KEY = 'your-super-secret-jwt-key-change-in-production'

# filename: config.py
# config.py
import os

DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', '192.168.119.102'),
    'port': int(os.getenv('MYSQL_PORT', 3308)),   # ← 改成 3308
    'user': os.getenv('MYSQL_USER', 'root'),
    'password': os.getenv('MYSQL_PASSWORD', '123456'),
    'database': os.getenv('MYSQL_DATABASE', 'plagiarism_db'),
    'charset': 'utf8mb4'
}

REDIS_CONFIG = {
    'host': os.getenv('REDIS_HOST', '192.168.119.102'),
    'port': int(os.getenv('REDIS_PORT', 6379)),
    'password': os.getenv('REDIS_PASSWORD', ''),
    'db': int(os.getenv('REDIS_DB', 0)),
    'decode_responses': True
}

JWT_SECRET_KEY = 'your-super-secret-jwt-key-change-in-production-2026'

CELERY_BROKER_URL = f'redis://{REDIS_CONFIG["host"]}:{REDIS_CONFIG["port"]}/{REDIS_CONFIG["db"]}'
CELERY_RESULT_BACKEND = CELERY_BROKER_URL