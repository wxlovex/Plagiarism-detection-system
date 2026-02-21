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