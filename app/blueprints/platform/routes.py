from functools import wraps
from datetime import datetime

from flask import render_template, redirect, url_for, request, flash, abort
from flask_login import login_required, current_user

from app.extensions import db
from app.models.tenant import Tenant
from app.models.user import StaffUser
from . import platform_bp


def superadmin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not current_user.is_authenticated or current_user.role != 'superadmin':
            abort(403)
        return f(*args, **kwargs)
    return decorated


@platform_bp.route('/')
@login_required
@superadmin_required
def dashboard():
    status_filter = request.args.get('status', '')
    q = Tenant.query.filter(Tenant.slug != '__platform__')
    if status_filter:
        q = q.filter_by(membership_status=status_filter)
    tenants = q.order_by(Tenant.created_at.desc()).all()

    counts = {
        'total':     Tenant.query.filter(Tenant.slug != '__platform__').count(),
        'active':    Tenant.query.filter_by(membership_status='active').count(),
        'trial':     Tenant.query.filter_by(membership_status='trial').count(),
        'expired':   Tenant.query.filter_by(membership_status='expired').count(),
    }
    total_users = StaffUser.query.filter(StaffUser.role != 'superadmin').count()
    return render_template('platform/dashboard.html',
                           tenants=tenants, counts=counts,
                           total_users=total_users,
                           status_filter=status_filter)


@platform_bp.route('/tenants/<int:tenant_id>/membership', methods=['POST'])
@login_required
@superadmin_required
def update_membership(tenant_id):
    tenant = db.get_or_404(Tenant, tenant_id)
    status = request.form.get('membership_status', tenant.membership_status)
    expires_str = request.form.get('membership_expires_at', '').strip()
    mp_link = request.form.get('mp_payment_link', '').strip()

    if status in ('trial', 'active', 'expired', 'cancelled'):
        tenant.membership_status = status

    if expires_str:
        try:
            tenant.membership_expires_at = datetime.fromisoformat(expires_str)
        except ValueError:
            flash('Fecha de vencimiento inválida.', 'danger')
            return redirect(url_for('platform.dashboard'))
    else:
        tenant.membership_expires_at = None

    tenant.mp_payment_link = mp_link or None
    db.session.commit()
    flash(f'Membresía de "{tenant.name}" actualizada.', 'success')
    return redirect(url_for('platform.dashboard'))


@platform_bp.route('/tenants/<int:tenant_id>/toggle', methods=['POST'])
@login_required
@superadmin_required
def toggle_tenant(tenant_id):
    tenant = db.get_or_404(Tenant, tenant_id)
    tenant.is_active = not tenant.is_active
    db.session.commit()
    estado = 'activado' if tenant.is_active else 'desactivado'
    flash(f'Negocio "{tenant.name}" {estado}.', 'success')
    return redirect(url_for('platform.dashboard'))


@platform_bp.route('/tenants/<int:tenant_id>/delete', methods=['POST'])
@login_required
@superadmin_required
def delete_tenant(tenant_id):
    tenant = db.get_or_404(Tenant, tenant_id)
    name = tenant.name
    db.session.delete(tenant)
    db.session.commit()
    flash(f'Negocio "{name}" eliminado.', 'info')
    return redirect(url_for('platform.dashboard'))
