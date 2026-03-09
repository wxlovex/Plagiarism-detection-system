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
    """高级 AIGC 检测报告 - 返回详细多维度数据"""
    if not text or len(text) < 50:
        return {
            'total_score': 0,
            'confidence': 0,
            'dimensions': {},
            'conclusion': '文本过短，无法准确判断'
        }

    sentences = re.split(r'[。！？.!?]', text)
    sentences = [s.strip() for s in sentences if len(s.strip()) > 5]
    words = jieba.lcut(text)

    # ==================== 5个核心维度计算 ====================
    lengths = [len(s) for s in sentences]
    mean_len = sum(lengths) / len(lengths) if lengths else 0
    variance = sum((l - mean_len) ** 2 for l in lengths) / len(lengths) if lengths else 0

    word_freq = {}
    for w in words:
        if len(w) > 1:
            word_freq[w] = word_freq.get(w, 0) + 1
    max_freq = max(word_freq.values()) if word_freq else 1
    burstiness = max_freq / len(words) if words else 0

    unique_ratio = len(word_freq) / len(words) if words else 0

    ai_transitions = {'然而', '因此', '总之', '另外', '此外', '值得一提', '需要注意的是', '值得注意的是', '综上所述', '总而言之'}
    transition_count = sum(1 for w in words if w in ai_transitions)
    transition_ratio = transition_count / len(sentences) if sentences else 0

    punct = re.findall(r'[，。！？；：、]', text)
    punct_diversity = len(set(punct)) / len(punct) if punct else 0

    # ==================== 维度打分（0-100） ====================
    dim_sentence_uniformity = max(0, 100 - variance * 2)          # 句子长度均匀度
    dim_burstiness = min(100, burstiness * 800)                   # 高频词重复度
    dim_vocabulary_richness = max(0, (unique_ratio - 0.3) * 200)  # 词汇丰富度
    dim_transition_words = min(100, transition_ratio * 600)       # AI过渡词
    dim_punctuation = max(0, (punct_diversity - 0.4) * 200)       # 标点多样性

    dimensions = {
        'sentence_uniformity': round(dim_sentence_uniformity, 1),
        'burstiness': round(dim_burstiness, 1),
        'vocabulary_richness': round(dim_vocabulary_richness, 1),
        'transition_words': round(dim_transition_words, 1),
        'punctuation_diversity': round(dim_punctuation, 1)
    }

    # ==================== 总体分数与置信度 ====================
    total_score = int(0.25*dim_sentence_uniformity +
                      0.25*dim_burstiness +
                      0.2*dim_vocabulary_richness +
                      0.2*dim_transition_words +
                      0.1*dim_punctuation)

    confidence = min(95, max(40, 100 - abs(total_score - 50) * 0.8))

    conclusion = "高度疑似AI生成" if total_score > 75 else \
                 "可能为AI辅助写作" if total_score > 55 else \
                 "更可能是人工撰写"

    return {
        'total_score': total_score,
        'confidence': confidence,
        'dimensions': dimensions,
        'conclusion': conclusion
    }