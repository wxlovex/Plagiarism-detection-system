
# 🎓 毕业论文致谢抄袭检测系统

基于 Flask + Celery + Docker + AIGC 检测的智能论文致谢查重平台

## ✨ 核心功能
- 支持 **TXT / PDF / DOCX** 上传
- 自动提取「致谢」段落
- 多模板库对比（通用50篇 + 计算机专业30篇）
- 融合 **TF-IDF + Jaccard** 相似度算法
- 升级版 **AIGC 生成概率检测**（v2 多维度融合）
- Celery 异步任务 + 实时进度条
- Docker 一键部署 + Jenkins CI/CD

## 🚀 快速启动（Docker）

```bash
docker build -t plagiarism-app .
docker run -d -p 5000:5000 \
  -e MYSQL_HOST=你的数据库IP \
  plagiarism-app
