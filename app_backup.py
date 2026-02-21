import re
from datetime import timedelta, datetime

import jieba
import argparse
import glob
import os
import pymysql
import redis
import json
from datetime import timedelta
from werkzeug.security import generate_password_hash, check_password_hash
from config import DB_CONFIG, REDIS_CONFIG, JWT_SECRET_KEY
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from flask import Flask, render_template, request, flash, redirect, url_for, session, make_response
from flask_jwt_extended import JWTManager, jwt_required, create_access_token, get_jwt_identity, unset_jwt_cookies, \
    set_access_cookies, get_csrf_token, get_jwt

from config import DB_CONFIG, REDIS_CONFIG, JWT_SECRET_KEY
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from flask import Flask, render_template, request, flash, session, redirect, url_for

rdb = redis.from_url(f'redis://{REDIS_CONFIG["host"]}:{REDIS_CONFIG["port"]}/{REDIS_CONFIG["db"]}',
                     decode_responses=True)


# 预处理函数
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


# 相似度计算
def compute_similarity(text1, text2):
    words1 = preprocess_text(text1)
    words2 = preprocess_text(text2)
    doc1 = ' '.join(words1)
    doc2 = ' '.join(words2)

    if not doc1 or not doc2:
        return 0.0

    # TF-IDF
    vectorizer = TfidfVectorizer(max_features=50)  # 优化：限50词
    tfidf_matrix = vectorizer.fit_transform([doc1, doc2])
    tfidf_score = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])[0][0]

    # Jaccard
    jaccard_score = jaccard_similarity(words1, words2)

    # 融合（可调权重）
    final_score = 0.7 * tfidf_score + 0.3 * jaccard_score
    return final_score


def get_templates_from_db(folder):
    """从DB拉取指定category的所有content"""
    # 新增：从路径提取category
    if folder.endswith('/'):
        folder = folder.rstrip('/')
    category = folder.split('/')[-1] if '/' in folder else folder  # e.g., "./refs/general/" → 'general'
    print(f"调试：提取category = '{category}' 从 folder='{folder}'")  # 日志1：检查提取

    try:
        conn = pymysql.connect(**DB_CONFIG)
        print(f"调试：DB连接成功")  # 日志2：连接OK
        cursor = conn.cursor()
        sql = "SELECT title, content FROM templates WHERE category = %s"
        cursor.execute(sql, (category,))
        results = cursor.fetchall()
        print(f"调试：查询结果数 = {len(results)}")  # 日志3：行数
        cursor.close()
        conn.close()
        return results
    except Exception as e:
        print(f"DB错误: {e}")  # 已有的，日志4：异常
        return []


# 读文件
def read_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            return f.read().strip()
    except FileNotFoundError:
        print(f"错误：文件 {filepath} 不存在！请检查路径。")
        return None
    except Exception as e:
        print(f"读取错误：{e}")
        return None


# 判断
def judge_plagiarism(score, threshold):
    if score > threshold:
        return "疑似抄袭（高相似）"
    elif score > 0.3:
        return "中等相似（需人工审）"
    else:
        return "原创（低相似）"


# 主函数
def main():
    parser = argparse.ArgumentParser(description="毕业论文致谢抄袭检测系统")
    parser.add_argument('files', nargs='*', help="文件路径（单模式：两个文件；批量：一个测试文件）")
    parser.add_argument('--batch', action='store_true', help="批量模式：测试文件 vs --folder内所有txt")
    parser.add_argument('--folder', help="批量参考文件夹路径")
    parser.add_argument('--threshold', type=float, default=0.7, help="相似度阈值（默认0.7）")

    args = parser.parse_args()

    # 调试：打印参数（生产时可删）
    print(f"调试：参数 - 批量模式: {args.batch}, 文件夹: {args.folder}, 阈值: {args.threshold}, 位置参数: {args.files}")

    if args.batch:
        # 批量模式
        if not args.folder:
            print("错误：批量模式必须指定 --folder（如 --folder ./refs/）")
            return
        if not args.files:
            print("错误：批量模式需指定测试文件（如 thanks.txt）")
            return
        test_file = args.files[0]  # 第一个位置参数作为测试文件
        text1 = read_file(test_file)
        if not text1:
            return  # 已打印错误

        # 找参考文件
        ref_pattern = os.path.join(args.folder, "*.txt")
        ref_files = glob.glob(ref_pattern)
        print(f"调试：找到 {len(ref_files)} 个参考文件: {ref_files}")  # 调试
        if not ref_files:
            print(f"错误：文件夹 {args.folder} 无 .txt 文件！请创建并添加样本。")
            return

        # 计算所有
        results = []
        for ref_file in ref_files:
            text2 = read_file(ref_file)
            if text2:
                score = compute_similarity(text1, text2)
                judgment = judge_plagiarism(score, args.threshold)
                results.append((ref_file, score, judgment))

        # 排序并输出
        results.sort(key=lambda x: x[1], reverse=True)
        print(f"\n=== 批量检测报告（{len(results)} 个参考） ===")
        print(f"测试文件: {test_file}")
        print(f"阈值: {args.threshold}")
        print("{:<40} {:<10} {:<20}".format("参考文件", "相似度", "判断"))
        print("-" * 70)
        for file_path, score, jud in results:
            print("{:<40} {:<10.4f} {:<20}".format(os.path.basename(file_path), score, jud))

    else:
        # 单模式：需正好2个位置参数
        if len(args.files) != 2:
            print("错误：单模式需指定两个文件路径！如: python detector.py file1.txt file2.txt --threshold 0.5")
            parser.print_help()
            return

        file1, file2 = args.files
        text1 = read_file(file1)
        text2 = read_file(file2)
        if not text1 or not text2:
            return  # 已打印错误

        score = compute_similarity(text1, text2)
        judgment = judge_plagiarism(score, args.threshold)

        print(f"\n=== 检测报告 ===")
        print(f"文件1: {file1}")
        print(f"文件2: {file2}")
        print(f"相似度分数: {score:.4f}")
        print(f"判断: {judgment}")
        print(f"阈值: {args.threshold}")


app = Flask(__name__)
app.secret_key = 'your_secret_key'  # 闪现消息用
# JWT 配置
app.config['JWT_SECRET_KEY'] = JWT_SECRET_KEY
app.config['JWT_ACCESS_TOKEN_EXPIRES'] = timedelta(minutes=30)
app.config['JWT_TOKEN_LOCATION'] = ['cookies']
app.config['JWT_COOKIE_CSRF_PROTECT'] = True  # 保持启用
app.config['JWT_CSRF_CHECK_FORM'] = True  # 新增：检查 form['csrf_token'] 而非 header
app.config['JWT_ACCESS_COOKIES'] = {
    'secure': False,  # 生产：True (HTTPS)
    'httponly': True,
    'samesite': 'Lax'
}
jwt = JWTManager(app)



# 登录路由
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if not username or not password:
            flash('用户名和密码不能为空！')
            return render_template('login.html')

        user_key = f"user:{username}"
        user_data_str = rdb.get(user_key)
        if not user_data_str:
            flash('用户不存在！')
            return render_template('login.html')

        user_data = json.loads(user_data_str)
        if check_password_hash(user_data['hashed_password'], password):
            access_token = create_access_token(identity=username)  # 自动嵌入随机 CSRF 到 JWT
            resp = make_response(redirect(url_for('index')))
            set_access_cookies(resp, access_token)  # 设置 JWT cookie + 非 httponly CSRF cookie
            flash('登录成功！')
            return resp
        else:
            flash('密码错误！')
    return render_template('login.html')


# 注册路由（不变，注册后重定向登录）
@app.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username'].strip()
        password = request.form['password']
        if not username or len(password) < 6:
            flash('用户名不能为空，密码至少6位！')
            return render_template('register.html')

        user_key = f"user:{username}"
        if rdb.exists(user_key):
            flash('用户名已存在！')
            return render_template('register.html')

        hashed_pw = generate_password_hash(password, method='pbkdf2:sha256:600000')
        user_data = json.dumps({'hashed_password': hashed_pw, 'created_at': datetime.now()})
        rdb.set(user_key, user_data, ex=86400 * 365)  # 1年过期
        flash('注册成功，请登录！')
        return redirect(url_for('login'))
    return render_template('register.html')


@app.errorhandler(401)
def unauthorized(e):
    flash('请先登录！')
    return redirect(url_for('login'))


# 登出路由
@app.route('/logout')
@jwt_required()
def logout():
    resp = make_response(redirect(url_for('login')))
    unset_jwt_cookies(resp)  # 清除 cookie
    flash('已登出。')
    return resp


@app.route('/', methods=['GET', 'POST'])
@jwt_required()
def index():
    current_user = get_jwt_identity()  # 从 JWT 获取用户名
    # 从JWT提取token
    csrf_token = get_jwt().get('csrf', '')

    results = None
    stats = None  # 统计

    if request.method == 'POST':
        # 调试日志
        print(f"POST CSRF from form: {request.form.get('csrf_token', 'MISSING')}")
        print(f"Expected CSRF from JWT: {csrf_token}")

        # 处理上传
        test_file = request.files['test_file']
        folder = request.form['folder']
        threshold = float(request.form['threshold'])

        if test_file and test_file.filename.endswith('.txt'):
            # 保存上传文件到临时
            test_path = os.path.join('uploads', test_file.filename)
            os.makedirs('uploads', exist_ok=True)
            test_file.save(test_path)
            text1 = read_file(test_path)

            if not folder:
                flash('请选择参考模板库！')
            elif text1:
                # 查询DB
                db_results = get_templates_from_db(folder)  # folder=category
                print(f"调试：db_results长度 = {len(db_results)}")
                if db_results:
                    batch_results = []
                    for title, content in db_results:
                        score = compute_similarity(text1, content)
                        judgment = judge_plagiarism(score, threshold)
                        batch_results.append((title, score, judgment))  # 用title替换basename
                    batch_results.sort(key=lambda x: x[1], reverse=True)
                    results = batch_results

                    # 统计计算
                    stats = {'原创': 0, '中等相似': 0, '疑似抄袭': 0}
                    for _, score, judgment in batch_results:
                        if '原创' in judgment:
                            stats['原创'] += 1
                        elif '中等相似' in judgment:
                            stats['中等相似'] += 1
                        elif '疑似抄袭' in judgment:
                            stats['疑似抄袭'] += 1

                else:
                    flash('模板库无数据！检查DB')
            else:
                flash('无效文件夹或测试文件！')
        else:
            flash('请上传txt文件！')

    return render_template('index.html', results=results, stats=stats, current_user=current_user, csrf_token=csrf_token)


if __name__ == '__main__':
    app.run(debug=True)
