# filename: models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    hashed_password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='student')  # student / teacher / admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Template(db.Model):
    __tablename__ = 'templates'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)      # general / computer
    sub_category = db.Column(db.String(50), default='本科')  # 新增：本科/硕士/博士
    school = db.Column(db.String(100), default='通用')       # 新增：学校/专业标签
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DetectionJob(db.Model):
    __tablename__ = 'detection_jobs'
    __table_args__ = {'extend_existing': True}
    id = db.Column(db.String(36), primary_key=True)   # ← 改成 String，支持 UUID
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    test_filename = db.Column(db.String(200))
    category = db.Column(db.String(50))
    threshold = db.Column(db.Float, default=0.7)
    status = db.Column(db.String(20), default='pending')
    result_json = db.Column(db.Text)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

