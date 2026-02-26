from detector import read_file
from utils import compute_similarity, judge_plagiarism, get_templates_from_db, aigc_score
from tasks import detect_plagiarism
import os
import json
from datetime import datetime, timedelta
import re
import jieba
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from flask import Flask, render_template, request, flash, redirect, url_for, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity, unset_jwt_cookies, set_access_cookies
from werkzeug.security import generate_password_hash, check_password_hash
from config import DB_CONFIG, JWT_SECRET_KEY
from models import db, User, Template, DetectionJob
from extractors import extract_text, extract_acknowledgements



app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['JWT_SECRET_KEY'] = JWT_SECRET_KEY
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=30)
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?charset=utf8mb4"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

db.init_app(app)
jwt = JWTManager(app)
app.jinja_env.globals.update(aigc_score=aigc_score)

# 预处理函数（保持不变）
def clean_text(text):
    cleaned = re.sub(r'[^\w\s]', ' ', text)
    cleaned = re.sub(r'\s+', ' ', cleaned)
    return cleaned.strip()

def segment_text(text):
    words = jieba.cut(text)
    return list(words)

stop_words = {'的', '和', '我的', '们', '我', '在', '此', '非常'}

def filter_words(words):
    return [w for w in words if w not in stop_words and len(w) > 1]

def preprocess_text(text):
    cleaned = clean_text(text)
    words = segment_text(cleaned)
    return filter_words(words)

def jaccard_similarity(words1, words2):
    set1, set2 = set(words1), set(words2)
    intersection = len(set1.intersection(set2))
    union = len(set1.union(set2))
    return intersection / union if union != 0 else 0.0

def compute_similarity(text1, text2):
    words1 = preprocess_text(text1)
    words2 = preprocess_text(text2)
    doc1 = ' '.join(words1)
    doc2 = ' '.join(words2)
    if not doc1 or not doc2:
        return 0.0
    vectorizer = TfidfVectorizer(max_features=50)
    tfidf_matrix = vectorizer.fit_transform([doc1, doc2])
    tfidf_score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]
    jaccard_score = jaccard_similarity(words1, words2)
    return 0.7 * tfidf_score + 0.3 * jaccard_score

def judge_plagiarism(score, threshold):
    if score > threshold:
        return "疑似抄袭（高相似）"
    elif score > 0.3:
        return "中等相似（需人工审）"
    else:
        return "原创（低相似）"

def get_templates_from_db(category):
    return [(t.title, t.content) for t in Template.query.filter_by(category=category).all()]

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        user = User.query.filter_by(username=username).first()
        if user and check_password_hash(user.hashed_password, password):
            access_token = create_access_token(identity=username)
            resp = make_response(redirect(url_for('index')))
            set_access_cookies(resp, access_token)
            flash('登录成功！')
            return resp
        flash('用户名或密码错误！')
    return render_template('login.html')

@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if User.query.filter_by(username=username).first():
            flash('用户名已存在！')
            return render_template('register.html')
        hashed_pw = generate_password_hash(password)
        user = User(username=username, hashed_password=hashed_pw)
        db.session.add(user)
        db.session.commit()
        flash('注册成功，请登录！')
        return redirect(url_for('login'))
    return render_template('register.html')

@app.route('/logout')
@jwt_required()
def logout():
    resp = make_response(redirect(url_for('login')))
    unset_jwt_cookies(resp)
    flash('已登出。')
    return resp

@app.route('/', methods=['GET', 'POST'])
@jwt_required()
def index():
    current_user = get_jwt_identity()
    if request.method == 'POST':
        direct_text = request.form.get('direct_text', '').strip()
        test_file = request.files.get('test_file')
        category = request.form.get('folder')
        try:
            threshold = float(request.form.get('threshold', 0.7))
        except:
            threshold = 0.7

        # ==================== 绝对优先：文本框（只要有有效内容就用） ====================
        if direct_text and len(direct_text) > 10:
            text1 = extract_acknowledgements(direct_text)
            test_filename = f"direct_input_{datetime.now().strftime('%Y%m%d_%H%M%S')}.txt"
            os.makedirs('uploads', exist_ok=True)
            filepath = os.path.join('uploads', test_filename)
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(text1)
            flash('✅ 已使用文本框内容进行检测（文件上传已忽略）')

        # ==================== 文本框为空，则处理文件上传 ====================
        elif test_file and test_file.filename and test_file.filename.strip() != '':
            os.makedirs('uploads', exist_ok=True)
            test_filename = test_file.filename
            filepath = os.path.join('uploads', test_filename)
            test_file.save(filepath)
            text1 = extract_acknowledgements(read_file(filepath))
            flash('✅ 已使用上传文件进行检测')

        else:
            flash('❌ 请上传文件 或 在文本框中输入至少10个字符的内容！')
            return render_template('index.html', current_user=current_user)

        if not category:
            flash('❌ 请选择参考模板库！')
            return render_template('index.html', current_user=current_user)

        user = User.query.filter_by(username=current_user).first()
        if not user:
            flash('用户异常')
            return redirect(url_for('logout'))

        task = detect_plagiarism.delay(test_filename, category, threshold, user.id)

        job = DetectionJob(
            id=task.id,
            user_id=user.id,
            test_filename=test_filename,
            category=category,
            threshold=threshold,
            status='pending'
        )
        db.session.add(job)
        db.session.commit()

        flash(f'✅ 检测任务已提交！任务ID: {task.id}')
        return redirect(url_for('status', task_id=task.id))

    return render_template('index.html', current_user=current_user)

@app.route('/status/<task_id>', methods=['GET'])  # ← 明确只允许 GET
@jwt_required()
def status(task_id):
    job = DetectionJob.query.get(task_id)
    if not job:
        flash('任务不存在！')
        return redirect(url_for('index'))

    current_user = get_jwt_identity()

    if job.status == 'completed':
        result = json.loads(job.result_json)
        return render_template('index.html',
                               results=result['results'],
                               stats=result['stats'],
                               current_user=current_user,
                               task_id=task_id,
                               status='completed')   # ← 传递状态

    elif job.status in ('pending', 'running'):
        # 返回等待页面（带自动刷新）
        return render_template('index.html',
                               current_user=current_user,
                               task_id=task_id,
                               status='pending')   # ← 关键

    else:
        flash(f'任务异常：{job.status}')
        return redirect(url_for('index'))

# 创建表（第一次运行）
# with app.app_context():
#     db.create_all()

if __name__ == '__main__':
    app.run(debug=True)