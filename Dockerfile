FROM swr.cn-north-4.myhuaweicloud.com/ddn-k8s/docker.io/library/python:3.6

WORKDIR /app

# 复制requirements + 安装依赖
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# 复制项目文件
COPY . .

# 创建uploads目录
RUN mkdir -p uploads && chmod 755 uploads

# 暴露端口
EXPOSE 5000

# 运行gunicorn
CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "3", "app:app"]