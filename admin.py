# admin.py
from flask import Blueprint, render_template, request, redirect, url_for, flash, abort
from flask_jwt_extended import jwt_required, get_jwt_identity
from models import db, Template, User
from werkzeug.utils import secure_filename
import os

admin_bp = Blueprint('admin', __name__, url_prefix='/admin', template_folder='templates/admin')

@admin_bp.route('/templates')
@jwt_required()
def templates_list():
    current_user = get_jwt_identity()
    user = User.query.filter_by(username=current_user).first()
    if not user or user.role != 'admin':
        abort(403)  # 普通用户无权访问

    templates = Template.query.order_by(Template.created_at.desc()).all()
    return render_template('admin/templates_list.html', templates=templates)

@admin_bp.route('/templates/upload', methods=['POST'])
@jwt_required()
def upload_templates():
    current_user = get_jwt_identity()
    user = User.query.filter_by(username=current_user).first()
    if not user or user.role != 'admin':
        abort(403)

    if 'files' not in request.files:
        flash('没有选择文件')
        return redirect(url_for('admin.templates_list'))

    files = request.files.getlist('files')
    category = request.form.get('category', 'general')
    sub_category = request.form.get('sub_category', '本科')
    school = request.form.get('school', '通用')

    count = 0
    for file in files:
        if file and file.filename.endswith('.txt'):
            content = file.read().decode('utf-8', errors='ignore').strip()
            if not content:
                continue
            title = secure_filename(file.filename).replace('.txt', '')
            template = Template(
                title=title or f"模板_{count+1}",
                content=content,
                category=category,
                sub_category=sub_category,
                school=school
            )
            db.session.add(template)
            count += 1

    db.session.commit()
    flash(f'✅ 成功导入 {count} 条模板！')
    return redirect(url_for('admin.templates_list'))