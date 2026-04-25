from flask import render_template, redirect, url_for, request, flash
from flask_login import login_user, logout_user, login_required, current_user

from app.extensions import limiter
from app.models.user import StaffUser
from app.models.tenant import Tenant
from . import auth_bp


@auth_bp.route('/login', methods=['GET', 'POST'])
@limiter.limit('10 per minute', methods=['POST'])
def login():
    if current_user.is_authenticated:
        return _redirect_after_login(current_user)

    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        user = StaffUser.query.filter_by(email=email, is_active=True).first()

        if user and user.check_password(password):
            login_user(user, remember=True)
            next_url = request.args.get('next')
            return redirect(next_url) if next_url else _redirect_after_login(user)

        flash('Email o contraseña incorrectos.', 'danger')

    return render_template('auth/login.html')


@auth_bp.route('/demo-login')
def demo_login():
    if current_user.is_authenticated:
        logout_user()

    demo_tenant = Tenant.query.filter_by(slug='demo', is_active=True).first()
    if not demo_tenant:
        flash('El acceso demo no está disponible en este momento.', 'warning')
        return redirect(url_for('auth.login'))

    demo_user = StaffUser.query.filter_by(tenant_id=demo_tenant.id, is_active=True).first()
    if not demo_user:
        flash('El acceso demo no está disponible en este momento.', 'warning')
        return redirect(url_for('auth.login'))

    login_user(demo_user, remember=False)
    return redirect(url_for('admin.dashboard', slug=demo_tenant.slug))


@auth_bp.route('/logout')
@login_required
def logout():
    logout_user()
    return redirect(url_for('auth.login'))


def _redirect_after_login(user):
    if user.role == 'superadmin':
        return redirect(url_for('platform.dashboard'))
    return redirect(url_for('admin.dashboard', slug=user.tenant.slug))
