## python3.6
#FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/python:3.6-slim
#
#WORKDIR /app
#
## 复制requirements + 安装所有依赖（一键，避免多RUN）
#COPY requirements.txt .
#RUN pip install --no-cache-dir -r requirements.txt -i https://pypi.tuna.tsinghua.edu.cn/simple --timeout 300 --retries 3
#
## 复制项目文件
#COPY . .
#
## 创建uploads
#RUN mkdir -p uploads && chmod 755 uploads
#
## 暴露端口
#EXPOSE 5000
#
## 运行gunicorn
#CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "app:app"]

# filename: Dockerfile
FROM python:3.12-slim

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 libglib2.0-0 libfontconfig1 libx11-6 libxext6 libsm6 libxrender1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt \
    -i https://pypi.tuna.tsinghua.edu.cn/simple \
    --extra-index-url https://pypi.org/simple

COPY . .

RUN mkdir -p uploads && chmod 755 uploads

EXPOSE 5000

CMD ["sh", "-c", "celery -A tasks worker --loglevel=info & gunicorn --bind 0.0.0.0:5000 --workers 3 app:app"]