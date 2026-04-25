from datetime import date
from flask import jsonify, request, abort, current_app
from flask_login import login_required, current_user

from app.extensions import db
from app.models.tenant import Tenant
from app.models.push_subscription import PushSubscription
from app.services.queue_manager import get_queue_snapshot
from app.services.slot_calculator import get_available_slots
from . import api_bp


def _get_tenant(slug):
    return Tenant.query.filter_by(slug=slug, is_active=True).first_or_404()


@api_bp.route('/<slug>/queue')
def queue_state(slug):
    tenant = _get_tenant(slug)
    return jsonify(get_queue_snapshot(tenant.id))


@api_bp.route('/<slug>/slots')
def available_slots(slug):
    tenant = _get_tenant(slug)
    service_id = request.args.get('service_id', type=int)
    professional_id = request.args.get('professional_id', type=int)
    date_str = request.args.get('date', '')

    if not service_id or not date_str:
        return jsonify({'slots': [], 'error': 'Faltan parámetros'}), 400

    from app.models.service import Service
    service = Service.query.filter_by(id=service_id, tenant_id=tenant.id, is_active=True).first()
    if not service:
        abort(404)

    try:
        target_date = date.fromisoformat(date_str)
    except ValueError:
        return jsonify({'slots': [], 'error': 'Fecha inválida'}), 400

    slots = get_available_slots(tenant.id, target_date, service.duration_min, professional_id)
    return jsonify({'slots': slots})


@api_bp.route('/push/vapid-key')
def vapid_public_key():
    return jsonify({'key': current_app.config.get('VAPID_PUBLIC_KEY', '')})


@api_bp.route('/push/subscribe', methods=['POST'])
@login_required
def push_subscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get('endpoint')
    p256dh = data.get('keys', {}).get('p256dh')
    auth = data.get('keys', {}).get('auth')
    if not all([endpoint, p256dh, auth]):
        return jsonify({'error': 'Datos incompletos'}), 400

    sub = PushSubscription.query.filter_by(endpoint=endpoint).first()
    if not sub:
        sub = PushSubscription(
            tenant_id=current_user.tenant_id,
            user_id=current_user.id,
            endpoint=endpoint, p256dh=p256dh, auth=auth,
        )
        db.session.add(sub)
        db.session.commit()
    return jsonify({'ok': True})


@api_bp.route('/push/unsubscribe', methods=['POST'])
@login_required
def push_unsubscribe():
    data = request.get_json(silent=True) or {}
    endpoint = data.get('endpoint')
    if endpoint:
        PushSubscription.query.filter_by(
            endpoint=endpoint, user_id=current_user.id
        ).delete()
        db.session.commit()
    return jsonify({'ok': True})
