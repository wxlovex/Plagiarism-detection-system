# tasks.py （最终修复版 - 彻底解决循环导入）
from celery import Celery
from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND
from extractors import extract_acknowledgements
import json
from utils import compute_similarity, judge_plagiarism

celery = Celery('tasks', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)


@celery.task(bind=True)
def detect_plagiarism(self, test_filename, category, threshold, user_id):
    self.update_state(state='PROGRESS', meta={'progress': 10})

    try:
        # 关键修复：函数内部 lazy import，彻底打破循环导入
        from app import app, db
        from models import DetectionJob, Template

        with app.app_context():
            # 读取上传的文件
            with open(f'uploads/{test_filename}', 'r', encoding='utf-8') as f:
                text1 = f.read()

            text1 = extract_acknowledgements(text1)
            self.update_state(state='PROGRESS', meta={'progress': 30})

            # 获取模板
            db_results = Template.query.filter_by(category=category).all()
            if not db_results:
                raise ValueError(f"模板库 '{category}' 中没有数据！请先在后台添加模板。")

            templates = [(t.title, t.content) for t in db_results]

            batch_results = []
            matched_segments = []  # 新增：用于并排高亮
            total = len(templates)

            for i, (title, content) in enumerate(templates):
                score = compute_similarity(text1, content)
                judgment = judge_plagiarism(score, threshold)

                # 安全高亮（支持长文本，截取前200字符，避免渲染过慢 + 特殊字符转义）
                user_text = text1[:200] if len(text1) > 200 else text1
                template_text = content[:200] if len(content) > 200 else content

                # 转义特殊字符，避免 Jinja2 渲染错误
                user_text = user_text.replace('<', '&lt;').replace('>', '&gt;')
                template_text = template_text.replace('<', '&lt;').replace('>', '&gt;')

                if score > 0.3:
                    # 简单高亮前50字符
                    user_text = user_text.replace(user_text[:50],
                                                  f'<mark style="background:#ffebee;color:#d32f2f;">{user_text[:50]}</mark>')
                    template_text = template_text.replace(template_text[:50],
                                                          f'<mark style="background:#ffebee;color:#d32f2f;">{template_text[:50]}</mark>')

                batch_results.append((title, score, judgment))
                matched_segments.append({
                    'title': title,
                    'score': score,
                    'judgment': judgment,
                    'user_text': user_text,
                    'template_text': template_text
                })

                progress = 30 + int(60 * (i + 1) / total) if total > 0 else 90
                self.update_state(state='PROGRESS', meta={'progress': progress})

            batch_results.sort(key=lambda x: x[1], reverse=True)

            # 统计
            stats = {'原创': 0, '中等相似': 0, '疑似抄袭': 0}
            for _, _, jud in batch_results:
                if '原创' in jud:
                    stats['原创'] += 1
                elif '中等相似' in jud:
                    stats['中等相似'] += 1
                else:
                    stats['疑似抄袭'] += 1

            result = {
                'results': batch_results,
                'stats': stats,
                'total': len(batch_results),
                'threshold': threshold,
                'matched_segments': matched_segments  # ← 新增
            }

            # 保存结果
            job = DetectionJob.query.get(self.request.id)
            if job:
                job.status = 'completed'
                job.result_json = json.dumps(result)
                db.session.commit()

        return result

    except Exception as e:
        print(f"【检测任务异常】: {str(e)}")
        try:
            from app import app, db
            from models import DetectionJob
            with app.app_context():
                job = DetectionJob.query.get(self.request.id)
                if job:
                    job.status = 'failed'
                    job.result_json = json.dumps({"error": str(e)})
                    db.session.commit()
        except:
            pass
        raise