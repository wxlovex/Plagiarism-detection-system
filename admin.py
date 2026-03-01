from flask import Blueprint, render_template, request, redirect, url_for, flash
from flask_wtf import FlaskForm
from wtforms import StringField, TextAreaField, SelectField
from wtforms.validators import DataRequired
from models import Template, db
from functools import wraps
from flask_jwt_extended import jwt_required, get_jwt_identity

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')

# ====================== 权限装饰器 ======================
def admin_required(f):
    @wraps(f)
    @jwt_required()
    def decorated(*args, **kwargs):
        current_user = get_jwt_identity()
        from models import User
        user = User.query.filter_by(username=current_user).first()
        if not user or user.role != 'admin':
            flash('❌ 无管理员权限！')
            return redirect(url_for('index'))
        return f(*args, **kwargs)
    return decorated

# ====================== 表单 ======================
class TemplateForm(FlaskForm):
    title = StringField('标题', validators=[DataRequired()])
    content = TextAreaField('内容', validators=[DataRequired()])
    category = SelectField('分类', choices=[('general', '通用致谢'), ('computer', '计算机专业')], validators=[DataRequired()])

# ====================== 路由 ======================
@admin_bp.route('/templates')
@admin_required
def templates_list():
    page = request.args.get('page', 1, type=int)
    search = request.args.get('search', '')
    category = request.args.get('category', '')

    query = Template.query
    if search:
        query = query.filter(Template.title.like(f'%{search}%'))
    if category:
        query = query.filter_by(category=category)

    pagination = query.order_by(Template.created_at.desc()).paginate(page=page, per_page=15)
    return render_template('admin/templates_list.html',
                           templates=pagination,
                           search=search,
                           category=category)

@admin_bp.route('/template/add', methods=['GET', 'POST'])
@admin_required
def template_add():
    form = TemplateForm()
    if form.validate_on_submit():
        tpl = Template(
            title=form.title.data,
            content=form.content.data,
            category=form.category.data
        )
        db.session.add(tpl)
        db.session.commit()
        flash('✅ 模板添加成功！')
        return redirect(url_for('admin.templates_list'))
    return render_template('admin/template_form.html', form=form, title='新增模板')

@admin_bp.route('/template/edit/<int:id>', methods=['GET', 'POST'])
@admin_required
def template_edit(id):
    tpl = Template.query.get_or_404(id)
    form = TemplateForm(obj=tpl)
    if form.validate_on_submit():
        tpl.title = form.title.data
        tpl.content = form.content.data
        tpl.category = form.category.data
        db.session.commit()
        flash('✅ 模板更新成功！')
        return redirect(url_for('admin.templates_list'))
    return render_template('admin/template_form.html', form=form, title='编辑模板', template=tpl)

@admin_bp.route('/template/delete/<int:id>')
@admin_required
def template_delete(id):
    tpl = Template.query.get_or_404(id)
    db.session.delete(tpl)
    db.session.commit()
    flash('✅ 模板已删除！')
    return redirect(url_for('admin.templates_list'))

# 批量导入（保留你原来的功能并优化）
@admin_bp.route('/templates/batch_import', methods=['POST'])
@admin_required
def batch_import():
    files = request.files.getlist('files')
    category = request.form.get('category')
    sub_category = request.form.get('sub_category', '本科')
    school = request.form.get('school', '通用')

    count = 0
    for file in files:
        if file and file.filename.endswith('.txt'):
            content = file.read().decode('utf-8')
            title = file.filename.replace('.txt', '')
            tpl = Template(
                title=title,
                content=content,
                category=category,
                # 如果你 models 加了 sub_category 和 school 字段就放这里
            )
            db.session.add(tpl)
            count += 1
    db.session.commit()
    flash(f'✅ 成功批量导入 {count} 条模板！')
    return redirect(url_for('admin.templates_list'))