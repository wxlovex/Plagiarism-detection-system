from flask_wtf.file import FileRequired, FileAllowed
from werkzeug.datastructures import file_storage
from werkzeug.utils import secure_filename, send_file
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
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity, unset_jwt_cookies, \
    set_access_cookies, get_jwt, current_user , unset_jwt_cookies
from werkzeug.security import generate_password_hash, check_password_hash
from config import DB_CONFIG, JWT_SECRET_KEY, redis_client, ADMIN_USERNAME, ADMIN_DEFAULT_PASSWORD
from models import db, User, Template, DetectionJob
from extractors import extract_text, extract_acknowledgements
from flask_wtf.csrf import CSRFProtect
from flask_wtf import FlaskForm
from wtforms import FileField, SelectField, FloatField
from wtforms.validators import DataRequired
from admin import admin_bp
#  报告导出
from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import inch
from io import BytesIO
# PDF 中文字体支持
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.cidfonts import UnicodeCIDFont


# ====================== 启动时自动创建管理员 ======================
def init_admin():
    with app.app_context():
        admin = User.query.filter_by(username=ADMIN_USERNAME).first()
        if not admin:
            # 首次创建
            hashed_pw = generate_password_hash(ADMIN_DEFAULT_PASSWORD)
            admin = User(
                username=ADMIN_USERNAME,
                hashed_password=hashed_pw,
                role='admin'
            )
            db.session.add(admin)
            db.session.commit()
            print(f"✅ 默认管理员账号已自动创建！ 用户名: {ADMIN_USERNAME}  密码: {ADMIN_DEFAULT_PASSWORD}")
        else:
            # 强制修复已有 admin 账号的角色
            if admin.role != 'admin':
                admin.role = 'admin'
                db.session.commit()
                print(f"✅ 已自动修复 admin 用户角色 → 'admin'")
            else:
                print(f"✅ 管理员账号已存在且角色正确（{ADMIN_USERNAME}）")

app = Flask(__name__)
app.config['JWT_COOKIE_SAMESITE'] = 'Lax'
# 注册管理员蓝图
app.register_blueprint(admin_bp)

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

#JWT 过期/无效友好处理
@jwt.expired_token_loader
def expired_token_callback(jwt_header, jwt_payload):
    """Token 过期时自动跳转登录页 + 清除旧 Cookie"""
    resp = make_response(redirect(url_for('login')))
    unset_jwt_cookies(resp)
    flash('⚠️ 您的登录已过期，请重新登录！', 'warning')
    return resp


@jwt.invalid_token_loader
def invalid_token_callback(error):
    """Token 无效时自动跳转"""
    resp = make_response(redirect(url_for('login')))
    unset_jwt_cookies(resp)
    flash('⚠️ 登录信息无效，请重新登录！', 'warning')
    return resp


@jwt.unauthorized_loader
def unauthorized_callback(error):
    """未登录时访问保护页面"""
    flash('⚠️ 请先登录系统！', 'warning')
    return redirect(url_for('login'))

# 让 current_user 正确加载 User 对象
@jwt.user_lookup_loader
def user_lookup_callback(_jwt_header, jwt_data):
    identity = jwt_data["sub"]
    return User.query.get(int(identity))

# 创建表单类
class DetectionForm(FlaskForm):
    test_file = FileField('测试文件（支持 TXT / PDF / DOCX）', validators=[
        FileRequired(),
        FileAllowed(ALLOWED_EXTENSIONS, '只允许上传 .txt、.pdf、.docx 文件！')
    ])
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
#登录
@app.route('/login', methods=['GET', 'POST'])
@jwt_required(optional=True)
def login():
    # 安全判断：如果已有有效 Token 则自动跳转首页
    if get_jwt_identity():
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        selected_role = request.form.get('login_role')

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            # 强制校验角色选择
            if selected_role == 'admin' and user.role != 'admin':
                flash('❌ 该账号没有管理员权限！请选择“普通用户”登录', 'danger')
                return redirect(url_for('login'))

            if selected_role == 'student' and user.role != 'student':
                flash('❌ 该账号为管理员，请选择“管理员”登录', 'danger')
                return redirect(url_for('login'))

            # 登录成功
            access_token = create_access_token(identity=str(user.id))
            resp = make_response(redirect(url_for('index')))
            set_access_cookies(resp, access_token)
            flash(f'✅ 欢迎回来，{user.username}！', 'success')
            return resp

        else:
            flash('❌ 用户名或密码错误！', 'danger')

    return render_template('index.html')

#注册
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

        # 特殊处理：用户名是 admin 时强制设为管理员
        role = 'admin' if username.lower() == ADMIN_USERNAME else 'student'

        hashed_pw = generate_password_hash(password)
        user = User(username=username, hashed_password=hashed_pw)
        db.session.add(user)
        db.session.commit()
        flash(f'注册成功！{"（管理员账号）" if role == "admin" else ""} 请登录！')
        return redirect(url_for('login'))
    return render_template('register.html')

#登出
@app.route('/logout')
@jwt_required()
def logout():
    jti = get_jwt()['jti']
    redis_client.setex(f"jwt_blacklist:{jti}", timedelta(days=7), '')
    resp = make_response(redirect(url_for('login')))
    unset_jwt_cookies(resp)
    flash('已登出。')
    return resp

# 检测主路由
@app.route('/', methods=['GET', 'POST'])
@jwt_required()
def index():
    #统一身份解析
    identity = get_jwt_identity()
    user = User.query.get(int(identity)) if identity else None
    if not user:
        flash('⚠️ 用户异常，请重新登录！', 'danger')
        return redirect(url_for('logout'))


    form = DetectionForm()

    if request.method == 'POST' and form.validate_on_submit():
        test_file = form.test_file.data
        category = form.folder.data
        threshold = form.threshold.data

        if not allowed_file(test_file.filename):
            flash('❌ 仅支持 .txt / .pdf / .docx 文件！')
            return render_template('index.html', current_user=user.username, form=form)

        filename = secure_filename(test_file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)

        if '..' in filename or filename.startswith('/'):
            flash('❌ 非法文件名！')
            return render_template('index.html', current_user=user.username, form=form)

        test_file.save(filepath)

        #提交 Celery 任务
        task = detect_plagiarism.delay(
            test_filename=filename,
            category=category,
            threshold=threshold,
            user_id=user.id
        )

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

    return render_template('index.html',
                           current_user=user.username,
                           form=form)

# status 路由
@app.route('/status/<task_id>')
@jwt_required()
def status(task_id):
    identity = get_jwt_identity()
    user = User.query.get(int(identity)) if identity else None
    if not user:
        flash('⚠️ 用户异常，请重新登录！', 'danger')
        return redirect(url_for('logout'))

    job = DetectionJob.query.get(task_id)
    if not job:
        flash(f'❌ 任务 {task_id} 不存在或已过期')
        return redirect(url_for('index'))


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
                flash('结果解析失败，请重试')
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

        # ====================== 优化显示逻辑 ======================
        all_results = result.get('results', [])
        matched_segments = result.get('matched_segments', [])

        # Top N 高相似（默认显示前8条最相似的）
        top_n = request.args.get('top', 8, type=int)
        top_results = sorted(all_results, key=lambda x: x[1], reverse=True)[:top_n]
        top_matched = [m for m in matched_segments if m['title'] in [r[0] for r in top_results]]

        # 其余结果（用于“加载更多”）
        remaining_results = all_results[top_n:]
        remaining_matched = [m for m in matched_segments if m['title'] not in [r[0] for r in top_results]]

        return render_template('index.html',
                               current_user=current_user,
                               results=top_results,  # 前端只显示 Top N
                               remaining_results=remaining_results,  # 导出
                               stats=result.get('stats', {}),
                               matched_segments=top_matched,  # 前端只显示 Top N
                               remaining_matched=remaining_matched,
                               total=len(all_results),
                               threshold=result.get('threshold', 0.7),
                               status='completed',
                               task_id=task_id,
                               aigc_analysis=result.get('aigc_analysis', {}),
                               form=form )          # ← 加上 form=form

    else:
        # 显示进度条页面
        return render_template('index.html',
                               current_user=current_user,
                               status='pending',
                               task_id=task_id,
                               form=form)          # ← 也加上 form=form


# ====================== 一键数据库字段迁移（执行一次即可） ======================
@app.route('/migrate')
def migrate_db():
    with app.app_context():
        try:
            # 之前模板迁移
            db.engine.execute("""
                ALTER TABLE templates 
                ADD COLUMN IF NOT EXISTS sub_category VARCHAR(50) DEFAULT '本科'
            """)
            db.engine.execute("""
                ALTER TABLE templates 
                ADD COLUMN IF NOT EXISTS school VARCHAR(100) DEFAULT '通用'
            """)

            # 新增：用户检测次数字段
            db.engine.execute("""
                ALTER TABLE users 
                ADD COLUMN IF NOT EXISTS detection_count INTEGER DEFAULT 0
            """)

            print("✅ 数据库迁移成功！新增 detection_count 字段")
            return """
                <h1 style="color:green">✅ 迁移成功！</h1>
                <p>已自动为 users 表添加 detection_count 字段</p>
                <p><strong>现在可以正常检测了！</strong></p>
            """
        except Exception as e:
            return f"""
                <h1 style="color:red">❌ 迁移失败</h1>
                <p>{str(e)}</p>
            """


# 检测历史记录
@app.route('/history')
@jwt_required()   # 必须保留保护
def history():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '').strip()

    # === 关键修复：使用 get_jwt_identity() 替代 current_user ===
    identity = get_jwt_identity()
    if not identity:
        flash('⚠️ 请先登录系统！', 'warning')
        return redirect(url_for('login'))

    user_id = int(identity)
    user = User.query.get(user_id)
    if not user:
        flash('⚠️ 用户信息异常，请重新登录！', 'danger')
        return redirect(url_for('login'))

    # 查询当前用户的检测记录
    query = DetectionJob.query.filter_by(user_id=user.id).order_by(DetectionJob.created_at.desc())

    if search:
        query = query.filter(DetectionJob.test_filename.like(f'%{search}%'))

    jobs = query.paginate(page=page, per_page=10, error_out=False)

    return render_template('history.html',
                           jobs=jobs,
                           search=search,
                           current_user=user)   # 传递给模板使用

# 仪表盘路由
@app.route('/dashboard')
@jwt_required()
def dashboard():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))

    # ==================== 统计数据 ====================
    total_jobs = DetectionJob.query.filter_by(user_id=user.id).count()
    this_month_jobs = DetectionJob.query.filter(
        DetectionJob.user_id == user.id,
        DetectionJob.created_at >= datetime.utcnow().replace(day=1)
    ).count()

    # 平均 AI 生成率（安全解析 JSON 字符串）
    jobs = DetectionJob.query.filter_by(user_id=user.id).all()
    ai_rates = []
    for job in jobs:
        if job.result_json:
            try:
                # 如果是字符串就解析，否则直接使用
                data = json.loads(job.result_json) if isinstance(job.result_json, str) else job.result_json
                if isinstance(data, dict) and 'aigc_analysis' in data:
                    ai_rates.append(data['aigc_analysis'].get('total_score', 0))
            except (json.JSONDecodeError, TypeError, KeyError):
                continue  # 跳过异常数据
    avg_ai_rate = round(sum(ai_rates) / len(ai_rates), 1) if ai_rates else 0

    # 模板库数量
    total_templates = Template.query.count()

    # 最近 5 次检测
    recent_jobs = DetectionJob.query.filter_by(user_id=user.id)\
        .order_by(DetectionJob.created_at.desc()).limit(5).all()

    return render_template('dashboard.html',
                           total_jobs=total_jobs,
                           this_month_jobs=this_month_jobs,
                           avg_ai_rate=avg_ai_rate,
                           total_templates=total_templates,
                           recent_jobs=recent_jobs,
                           current_user=user)


# 报告导出
@app.route('/export/pdf/<task_id>')
@jwt_required()
def export_pdf(task_id):
    identity = get_jwt_identity()
    user = User.query.get(int(identity)) if identity else None
    if not user:
        flash('⚠️ 用户异常，请重新登录！', 'danger')
        return redirect(url_for('logout'))

    print(f"访问 PDF 导出路由，task_id = {task_id}")
    job = DetectionJob.query.get_or_404(task_id)


    # 权限校验
    # user = User.query.filter_by(username=current_user).first()
    if not user or job.user_id != user.id:
        flash('❌ 只能导出自己的检测报告！')
        return redirect(url_for('index'))

    try:
        result = json.loads(job.result_json)
    except:
        flash('报告数据异常')
        return redirect(url_for('status', task_id=task_id))

    buffer = BytesIO()
    doc = SimpleDocTemplate(buffer, pagesize=A4, rightMargin=72, leftMargin=72, topMargin=72, bottomMargin=72)

    # 注册中文字体
    pdfmetrics.registerFont(UnicodeCIDFont('STSong-Light'))

    styles = getSampleStyleSheet()

    # 全局设置为中文字体
    styles['Normal'].fontName = 'STSong-Light'
    styles['Heading1'].fontName = 'STSong-Light'
    styles['Heading2'].fontName = 'STSong-Light'

    #标题
    title_style = ParagraphStyle(
        'Title',
        parent=styles['Heading1'],
        fontName='STSong-Light',
        fontSize=18,
        spaceAfter=30,
        alignment=1  # 居中
    )

    story = []


    story.append(Paragraph(f"毕业论文致谢抄袭检测报告", title_style))
    story.append(Paragraph(f"任务ID: {task_id}", styles['Normal']))
    story.append(Spacer(1, 20))

    # 统计
    stats = result.get('stats', {})
    data = [
        ['检测项目', '数量'],
        ['总参考模板', str(result.get('total', 0))],
        ['原创（低相似）', str(stats.get('原创', 0))],
        ['中等相似', str(stats.get('中等相似', 0))],
        ['疑似抄袭（高相似）', str(stats.get('疑似抄袭', 0))],
        ['阈值设置', f"{result.get('threshold', 0.7):.2f}"]
    ]
    t = Table(data, colWidths=[3 * inch, 2 * inch])
    t.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.HexColor('#007BFF')),
        ('TEXTCOLOR', (0, 0), (-1, 0), colors.whitesmoke),
        ('ALIGN', (0, 0), (-1, -1), 'CENTER'),
        ('FONTNAME', (0, 0), (-1, 0), 'STSong-Light'),
        ('FONTSIZE', (0, 0), (-1, 0), 12),
        ('BOTTOMPADDING', (0, 0), (-1, 0), 12),
        ('BACKGROUND', (0, 1), (-1, -1), colors.white),
        ('GRID', (0, 0), (-1, -1), 1, colors.black)
    ]))
    story.append(t)
    story.append(Spacer(1, 30))

    # 相似段落
    story.append(Paragraph("🔍 相似段落对比（Top 3）", styles['Heading2']))
    for seg in result.get('matched_segments', [])[:3]:
        story.append(Paragraph(f"<b>模板：</b>{seg['title']}（{seg['score'] * 100:.1f}% 相似）", styles['Normal']))
        story.append(Paragraph(f"<b>你的原文：</b>{seg['user_text'][:300]}...", styles['Normal']))
        story.append(Spacer(1, 12))

    doc.build(story)
    buffer.seek(0)

    # ================ 关键修复：中文文件名 + 干净 header ================
    from urllib.parse import quote
    filename = f"检测报告_{task_id[:8]}.pdf"
    encoded_filename = quote(filename)

    response = make_response(buffer.getvalue())
    response.headers['Content-Type'] = 'application/pdf'
    response.headers['Content-Disposition'] = f'attachment; filename*=UTF-8\'\'{encoded_filename}'
    response.headers['Cache-Control'] = 'no-cache'

    return response

@app.after_request
def add_security_headers(response):
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'

    # 严格但可用的 CSP（本地 + data: + 必要 fallback）
    response.headers['Content-Security-Policy'] = (
        "default-src 'self'; "
        "script-src 'self' 'unsafe-inline' 'unsafe-eval'; "          # 允许本地 JS + 内联脚本
        "style-src 'self' 'unsafe-inline'; "                          # 允许内联样式 + 本地 CSS
        "img-src 'self' data: blob:; "                                # 允许 data: SVG 图标
        "font-src 'self' data:; "                                     # 如果有字体
        "connect-src 'self'; "                                        # 防止 source map 等连接被挡
        "object-src 'none'; "                                         # 禁用插件
        "frame-ancestors 'self';"                                     # 防点击劫持
    )
    return response

if __name__ == '__main__':
    # ====================== 启动初始化 ======================
    init_admin()
    app.run(debug=True)

