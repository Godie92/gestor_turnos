"""
Web Push notifications via VAPID.
"""
import json
import logging
from threading import Thread

from pywebpush import webpush, WebPushException

logger = logging.getLogger(__name__)


def _send_push(subscription, payload: dict, vapid_private_key: str, vapid_claims: dict):
    try:
        webpush(
            subscription_info={
                'endpoint': subscription.endpoint,
                'keys': {'p256dh': subscription.p256dh, 'auth': subscription.auth},
            },
            data=json.dumps(payload),
            vapid_private_key=vapid_private_key,
            vapid_claims=vapid_claims,
        )
    except WebPushException as e:
        logger.warning('Push failed for %s: %s', subscription.endpoint[:40], e)
        # Suscripción inválida — eliminar
        if e.response and e.response.status_code in (404, 410):
            from app.extensions import db
            db.session.delete(subscription)
            db.session.commit()
    except Exception as e:
        logger.error('Push error: %s', e)


def notify_tenant_staff(app, tenant_id: int, title: str, body: str, url: str = '/'):
    """Envía push a todo el staff de un tenant."""
    from app.models.push_subscription import PushSubscription

    with app.app_context():
        subs = PushSubscription.query.filter_by(tenant_id=tenant_id).all()
        if not subs:
            return

        private_key = app.config.get('VAPID_PRIVATE_KEY', '')
        email = app.config.get('VAPID_CLAIMS_EMAIL', 'admin@example.com')
        if not private_key:
            return

        payload = {'title': title, 'body': body, 'url': url}
        claims = {'sub': f'mailto:{email}'}

        for sub in subs:
            Thread(
                target=_send_push,
                args=(sub, payload, private_key, claims),
                daemon=True,
            ).start()


def notify_async(app, tenant_id: int, title: str, body: str, url: str = '/'):
    """Wrapper para llamar desde fuera del app context."""
    Thread(
        target=notify_tenant_staff,
        args=(app, tenant_id, title, body, url),
        daemon=True,
    ).start()
