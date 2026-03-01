from werkzeug.utils import secure_filename
from detector import read_file
from utils import compute_similarity, judge_plagiarism, get_templates_from_db, aigc_score
from tasks import detect_plagiarism
import os
from bleach import clean
import json
from datetime import datetime, timedelta
import re
import jieba
print("🚀 预加载 jieba 模型...")
jieba.lcut("预加载模型测试")
print("✅ jieba 模型预加载完成")
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from flask import Flask, render_template, request, flash, redirect, url_for, jsonify, make_response
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity, unset_jwt_cookies, set_access_cookies, get_jwt
from werkzeug.security import generate_password_hash, check_password_hash
from config import DB_CONFIG, JWT_SECRET_KEY, redis_client
from models import db, User, Template, DetectionJob
from extractors import extract_text, extract_acknowledgements
from flask_wtf.csrf import CSRFProtect
from flask_wtf import FlaskForm
from wtforms import FileField, SelectField, FloatField
from wtforms.validators import DataRequired

app = Flask(__name__)
app.secret_key = 'your_secret_key'
app.config['JWT_SECRET_KEY'] = JWT_SECRET_KEY
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=15)
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_CSRF_PROTECT'] = False
app.config['SQLALCHEMY_DATABASE_URI'] = f"mysql+pymysql://{DB_CONFIG['user']}:{DB_CONFIG['password']}@{DB_CONFIG['host']}:{DB_CONFIG['port']}/{DB_CONFIG['database']}?charset=utf8mb4"
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False

# ==================== 全局配置 ====================
ALLOWED_EXTENSIONS = {'txt', 'pdf', 'docx'}
MAX_CONTENT_LENGTH = 10 * 1024 * 1024  # 10MB
app.config['MAX_CONTENT_LENGTH'] = MAX_CONTENT_LENGTH
app.config['UPLOAD_FOLDER'] = 'uploads'
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

csrf = CSRFProtect(app)
jwt = JWTManager(app)

# 创建表单类
class DetectionForm(FlaskForm):
    test_file = FileField('测试文件', validators=[DataRequired()])
    folder = SelectField('模板库', choices=[('general', '致谢模版50篇（通用）'), ('computer', '计算机致谢模版30篇（专业）')], validators=[DataRequired()])
    threshold = FloatField('阈值', default=0.7, validators=[DataRequired()])

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

db.init_app(app)
app.jinja_env.globals.update(aigc_score=aigc_score)

# 密码策略
def is_strong_password(password):
    if len(password) < 8:
        return False
    if not re.search(r'[A-Z]', password) or not re.search(r'[a-z]', password) or not re.search(r'\d', password):
        return False
    return True

# JWT黑名单
@jwt.token_in_blocklist_loader
def check_if_token_is_revoked(jwt_header, jwt_payload):
    jti = jwt_payload['jti']
    return redis_client.get(f"jwt_blacklist:{jti}") is not None

# ====================== 路由 ======================
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
        if not is_strong_password(password):
            flash('密码必须≥8位，包含大小写字母和数字！')
            return render_template('register.html')
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
    jti = get_jwt()['jti']
    redis_client.setex(f"jwt_blacklist:{jti}", timedelta(days=7), '')
    resp = make_response(redirect(url_for('login')))
    unset_jwt_cookies(resp)
    flash('已登出。')
    return resp

@app.route('/', methods=['GET', 'POST'])
@jwt_required()
def index():
    current_user = get_jwt_identity()
    form = DetectionForm()   # 每次都实例化

    if request.method == 'POST' and form.validate_on_submit():
        test_file = form.test_file.data
        category = form.folder.data
        threshold = form.threshold.data

        if not allowed_file(test_file.filename):
            flash('❌ 仅支持 .txt / .pdf / .docx 文件！')
            return render_template('index.html', current_user=current_user, form=form)

        filename = secure_filename(test_file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        if '..' in filename or filename.startswith('/'):
            flash('❌ 非法文件名！')
            return render_template('index.html', current_user=current_user, form=form)

        test_file.save(filepath)

        user = User.query.filter_by(username=current_user).first()
        if not user:
            flash('用户异常')
            return redirect(url_for('logout'))

        task = detect_plagiarism.delay(filename, category, threshold, user.id)

        job = DetectionJob(
            id=task.id,
            user_id=user.id,
            test_filename=filename,
            category=category,
            threshold=threshold,
            status='pending'
        )
        db.session.add(job)
        db.session.commit()

        flash(f'✅ 检测任务已提交！任务ID: {task.id}')
        return redirect(url_for('status', task_id=task.id))

    # GET 或验证失败 → 重新渲染表单（关键！）
    return render_template('index.html', current_user=current_user, form=form)

# status 路由保持你原来的最终版（已正确）
@app.route('/status/<task_id>')
@jwt_required()
def status(task_id):
    job = DetectionJob.query.get(task_id)
    if not job:
        flash(f'❌ 任务 {task_id} 不存在或已过期')
        return redirect(url_for('index'))

    current_user = get_jwt_identity()
    task = detect_plagiarism.AsyncResult(task_id)

    # 优先判断数据库是否有结果（应对超快完成任务）
    has_result = bool(job.result_json and job.status == 'completed')

    # === JSON 请求（JS轮询）===
    if request.args.get('json') == '1' or request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        if has_result or task.state in ('SUCCESS', 'completed') or task.ready():
            try:
                result = json.loads(job.result_json) if job.result_json else {}
            except:
                result = {}
            return jsonify({
                'status': 'completed',
                'progress': 100,
                'results': result.get('results', []),
                'stats': result.get('stats', {}),
                'matched_segments': result.get('matched_segments', [])
            })
        elif task.state == 'PROGRESS':
            progress = task.info.get('progress', 30) if isinstance(task.info, dict) else 30
            return jsonify({'status': 'PROGRESS', 'progress': progress})
        elif task.state == 'PENDING':
            return jsonify({'status': 'PENDING', 'progress': 15})
        else:
            return jsonify({'status': task.state or 'unknown', 'progress': 30})

    # === 普通浏览器访问 → HTML页面（关键修复在这里）===
    form = DetectionForm()   # ← 新增这一行！每次都创建 form

    if has_result or task.state in ('SUCCESS', 'completed') or task.ready():
        try:
            result = json.loads(job.result_json) if job.result_json else {}
        except:
            result = {}
            flash('结果解析失败，请重试')

        return render_template('index.html',
                               current_user=current_user,
                               results=result.get('results', []),
                               stats=result.get('stats', {}),
                               matched_segments=result.get('matched_segments', []),
                               status='completed',
                               form=form)          # ← 加上 form=form

    else:
        # 显示进度条页面
        return render_template('index.html',
                               current_user=current_user,
                               status='pending',
                               task_id=task_id,
                               form=form)          # ← 也加上 form=form

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    response.headers['Content-Security-Policy'] = "default-src 'self'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net"
    return response

if __name__ == '__main__':
    app.run(debug=True)