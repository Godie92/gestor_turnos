from flask import render_template, g

from app.models.tenant import Tenant
from . import display_bp


def _load_tenant(slug):
    return Tenant.query.filter_by(slug=slug, is_active=True).first_or_404()


@display_bp.route('/<slug>/pantalla')
def screen(slug):
    tenant = _load_tenant(slug)
    return render_template('display/screen.html', tenant=tenant)
