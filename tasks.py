# filename: tasks.py
from celery import Celery
from config import CELERY_BROKER_URL, CELERY_RESULT_BACKEND
from extractors import extract_text, extract_acknowledgements
from app import app, db, compute_similarity, judge_plagiarism, get_templates_from_db  # 后面会定义
import json

celery = Celery('tasks', broker=CELERY_BROKER_URL, backend=CELERY_RESULT_BACKEND)
celery.conf.update(app.config)


@celery.task(bind=True)
def detect_plagiarism(self, test_filename, category, threshold, user_id):
    self.update_state(state='PROGRESS', meta={'progress': 10})

    # 模拟读取（实际从 uploads 读取）
    with open(f'uploads/{test_filename}', 'r', encoding='utf-8') as f:
        text1 = f.read()

    text1 = extract_acknowledgements(text1)
    self.update_state(state='PROGRESS', meta={'progress': 30})

    db_results = get_templates_from_db(category)  # 用 ORM 版本
    batch_results = []
    total = len(db_results)

    for i, (title, content) in enumerate(db_results):
        score = compute_similarity(text1, content)
        judgment = judge_plagiarism(score, threshold)
        batch_results.append((title, score, judgment))
        progress = 30 + int(60 * (i + 1) / total)
        self.update_state(state='PROGRESS', meta={'progress': progress})

    batch_results.sort(key=lambda x: x[1], reverse=True)
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
        'threshold': threshold
    }

    # 保存到数据库
    from models import DetectionJob
    job = DetectionJob.query.filter_by(id=self.request.id).first()  # task id 即 job id
    if job:
        job.status = 'completed'
        job.result_json = json.dumps(result)
        db.session.commit()

    return result