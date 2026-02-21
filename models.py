# filename: models.py
from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class User(db.Model):
    __tablename__ = 'users'
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    hashed_password = db.Column(db.String(255), nullable=False)
    role = db.Column(db.String(20), default='student')  # student / teacher / admin
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class Template(db.Model):
    __tablename__ = 'templates'
    id = db.Column(db.Integer, primary_key=True)
    title = db.Column(db.String(200), nullable=False)
    content = db.Column(db.Text, nullable=False)
    category = db.Column(db.String(50), nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

class DetectionJob(db.Model):
    __tablename__ = 'detection_jobs'
    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id'), nullable=False)
    test_filename = db.Column(db.String(200))
    category = db.Column(db.String(50))
    threshold = db.Column(db.Float, default=0.7)
    status = db.Column(db.String(20), default='pending')  # pending / running / completed / failed
    result_json = db.Column(db.Text)  # 存 JSON 字符串
    created_at = db.Column(db.DateTime, default=datetime.utcnow)