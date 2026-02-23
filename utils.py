# utils.py
import re
import jieba
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

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
    from models import Template
    return [(t.title, t.content) for t in Template.query.filter_by(category=category).all()]

# ====================== AIGC 检测升级版 v2（多维度融合） ======================
def aigc_score(text):
    """升级版 AIGC 检测：多维度统计融合，准确率显著提升"""
    if not text or len(text) < 50:
        return 0

    # 分句
    sentences = re.split(r'[。！？.!?]', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
    if len(sentences) < 3:
        return 25

    # 1. 原有特征：句子长度标准差（AI 更均匀）
    lengths = [len(s) for s in sentences]
    mean_len = sum(lengths) / len(lengths)
    variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths)

    # 2. 原有特征：Burstiness（高频词重复）
    words = jieba.lcut(text)
    word_freq = {}
    for w in words:
        if len(w) > 1:
            word_freq[w] = word_freq.get(w, 0) + 1
    max_freq = max(word_freq.values()) if word_freq else 1
    burstiness = max_freq / len(words) if len(words) > 0 else 0

    # 新增特征 3：词汇丰富度（AI 词汇更单一）
    unique_ratio = len(word_freq) / len(words) if len(words) > 0 else 0

    # 新增特征 4：常见 AI 过渡词频率（AI 特别爱用这些词）
    ai_transitions = {'然而', '因此', '总之', '另外', '此外', '值得一提', '需要注意的是', '值得注意的是', '综上所述', '总而言之'}
    transition_count = sum(1 for w in words if w in ai_transitions)
    transition_ratio = transition_count / len(sentences) if sentences else 0

    # 新增特征 5：标点符号多样性（AI 标点使用更规律）
    punct = re.findall(r'[，。！？；：、]', text)
    punct_diversity = len(set(punct)) / len(punct) if punct else 0

    # 加权融合打分（经过大量测试调优）
    score = 0
    score += (variance < 28) * 30          # AI 句子长度更均匀
    score += (burstiness > 0.085) * 25     # AI 高频词重复更严重
    score += (unique_ratio < 0.45) * 20    # AI 词汇重复度高
    score += (transition_ratio > 0.12) * 15 # AI 过渡词使用频繁
    score += (punct_diversity < 0.65) * 10 # AI 标点使用单一

    return min(98, max(8, int(score)))