# 匹配你的3.6，slim减大小
FROM python:3.6-slim

WORKDIR /app

# 复制requirements + 安装所有依赖（一键，避免多RUN）
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建uploads
RUN mkdir -p uploads && chmod 755 uploads

# 暴露端口
EXPOSE 5000

# 运行gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "app:app"]