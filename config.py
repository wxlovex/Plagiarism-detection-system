import os

DB_CONFIG = {
    'host': '192.168.119.102',
    'port': 3308,
    'user': 'root',
    'password': '123456',
    'database': 'plagiarism_db',
    'charset': 'utf8mb4'
}

REDIS_CONFIG = {
    'host': os.getenv('REDIS_HOST', '192.168.119.102'),
    'port': int(os.getenv('REDIS_PORT', 6379)),
    'password': os.getenv('REDIS_PASSWORD', ''),  # 若启用 auth
    'db': int(os.getenv('REDIS_DB', 0)),
    'decode_responses': True  # 返回字符串
}

JWT_SECRET_KEY = 'your-super-secret-jwt-key-change-in-production'