import re
import jieba
import argparse
import glob
import os
import sys
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity
from flask import Flask, render_template, request, flash


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


@app.route('/', methods=['GET', 'POST'])
def index():
    results = None
    stats = None  # 统计
    if request.method == 'POST':
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

            if text1 and os.path.exists(folder):
                # 批量检测（复用步骤6逻辑）
                ref_files = glob.glob(os.path.join(folder, "*.txt"))
                if ref_files:
                    batch_results = []
                    for ref_file in ref_files:
                        text2 = read_file(ref_file)
                        if text2:
                            score = compute_similarity(text1, text2)
                            judgment = judge_plagiarism(score, threshold)
                            batch_results.append((os.path.basename(ref_file), score, judgment))
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
                    flash('参考文件夹无txt文件！')
            else:
                flash('无效文件夹或测试文件！')
        else:
            flash('请上传txt文件！')

    return render_template('index.html', results=results, stats=stats)


if __name__ == '__main__':
    app.run(debug=True)
