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
from datetime import timedelta
import redis

DB_CONFIG = {
    'host': os.getenv('MYSQL_HOST', '192.168.119.102'),
    'port': int(os.getenv('MYSQL_PORT', 3308)),   # ← 改成 3308
    'user': os.getenv('MYSQL_USER', 'plagiarism'),
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

JWT_SECRET_KEY = os.getenv('JWT_SECRET_KEY', 'your-super-secret-32-bytes-key-2026-change-it!')
JWT_ACCESS_TOKEN_EXPIRES = timedelta(minutes=15)   # 缩短
JWT_REFRESH_TOKEN_EXPIRES = timedelta(days=7)
JWT_BLACKLIST_ENABLED = True
JWT_BLACKLIST_TOKEN_CHECKS = ['access', 'refresh']


CELERY_BROKER_URL = f'redis://{REDIS_CONFIG["host"]}:{REDIS_CONFIG["port"]}/{REDIS_CONFIG["db"]}'
CELERY_RESULT_BACKEND = CELERY_BROKER_URL

redis_client = redis.Redis(
    host=REDIS_CONFIG['host'],
    port=REDIS_CONFIG['port'],
    password=REDIS_CONFIG.get('password') or None,
    db=REDIS_CONFIG['db'],
    decode_responses=True,      # 自动把 bytes 转成 str
    socket_connect_timeout=5,
    socket_timeout=5
)

ADMIN_USERNAME = 'admin'
ADMIN_DEFAULT_PASSWORD = os.getenv('ADMIN_DEFAULT_PASSWORD', 'Admin123!')  # 生产环境建议改

# 测试连接（启动时打印，生产可删）
try:
    redis_client.ping()
    print("✅ Redis 连接成功！")
except Exception as e:
    print(f"❌ Redis 连接失败: {e}")