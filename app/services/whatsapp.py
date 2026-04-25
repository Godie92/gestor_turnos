"""
Cliente para WhatsApp Business Cloud API (Meta).
Todos los envíos se hacen en threads separados para no bloquear el request.
"""
import logging
from threading import Thread

import httpx

logger = logging.getLogger(__name__)

WA_API_URL = 'https://graph.facebook.com/v19.0/{phone_number_id}/messages'


class WhatsAppClient:
    def __init__(self, phone_number_id: str, token: str):
        self.url = WA_API_URL.format(phone_number_id=phone_number_id)
        self.headers = {
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        }

    def send_template(self, to: str, template_name: str, components: list) -> dict:
        """Envía un mensaje template aprobado por Meta."""
        # Normalizar número: quitar + inicial
        to = to.lstrip('+').replace(' ', '').replace('-', '')
        payload = {
            'messaging_product': 'whatsapp',
            'to': to,
            'type': 'template',
            'template': {
                'name': template_name,
                'language': {'code': 'es_AR'},
                'components': components,
            },
        }
        resp = httpx.post(self.url, json=payload, headers=self.headers, timeout=10)
        resp.raise_for_status()
        return resp.json()

    def send_text(self, to: str, body: str) -> dict:
        """Envía texto libre (solo dentro de la ventana de 24h del cliente)."""
        to = to.lstrip('+').replace(' ', '').replace('-', '')
        payload = {
            'messaging_product': 'whatsapp',
            'to': to,
            'type': 'text',
            'text': {'body': body},
        }
        resp = httpx.post(self.url, json=payload, headers=self.headers, timeout=10)
        resp.raise_for_status()
        return resp.json()


def _async_send(app, fn, *args, **kwargs):
    """Ejecuta fn en un thread con app context. Nunca propaga excepciones."""
    def run():
        with app.app_context():
            try:
                fn(*args, **kwargs)
            except Exception as e:
                logger.error('WhatsApp send failed: %s', e)
    Thread(target=run, daemon=True).start()


def send_booking_confirmation(app, tenant, appointment, cancel_url: str):
    """Template: booking_confirmation"""
    if not tenant.wa_phone_id or not tenant.wa_token:
        return
    client = WhatsAppClient(tenant.wa_phone_id, tenant.wa_token)
    scheduled = appointment.scheduled_at.strftime('%d/%m/%Y')
    hour = appointment.scheduled_at.strftime('%H:%M')

    def _send():
        client.send_template(
            to=appointment.client_phone,
            template_name='booking_confirmation',
            components=[{
                'type': 'body',
                'parameters': [
                    {'type': 'text', 'text': appointment.client_name},
                    {'type': 'text', 'text': tenant.name},
                    {'type': 'text', 'text': scheduled},
                    {'type': 'text', 'text': hour},
                    {'type': 'text', 'text': appointment.service.name},
                    {'type': 'text', 'text': cancel_url},
                ],
            }],
        )

    _async_send(app, _send)


def send_appointment_reminder(app, tenant, appointment):
    """Template: appointment_reminder (30 min antes)"""
    if not tenant.wa_phone_id or not tenant.wa_token:
        return
    client = WhatsAppClient(tenant.wa_phone_id, tenant.wa_token)
    hour = appointment.scheduled_at.strftime('%H:%M')

    def _send():
        client.send_template(
            to=appointment.client_phone,
            template_name='appointment_reminder',
            components=[{
                'type': 'body',
                'parameters': [
                    {'type': 'text', 'text': appointment.client_name},
                    {'type': 'text', 'text': tenant.name},
                    {'type': 'text', 'text': hour},
                ],
            }],
        )

    _async_send(app, _send)


def send_day_before_reminder(app, tenant, appointment):
    """Template: day_before_reminder (recordatorio día anterior)"""
    if not tenant.wa_phone_id or not tenant.wa_token:
        return
    client = WhatsAppClient(tenant.wa_phone_id, tenant.wa_token)
    hour = appointment.scheduled_at.strftime('%H:%M')
    day = appointment.scheduled_at.strftime('%d/%m/%Y')

    def _send():
        client.send_template(
            to=appointment.client_phone,
            template_name='day_before_reminder',
            components=[{
                'type': 'body',
                'parameters': [
                    {'type': 'text', 'text': appointment.client_name},
                    {'type': 'text', 'text': tenant.name},
                    {'type': 'text', 'text': day},
                    {'type': 'text', 'text': hour},
                    {'type': 'text', 'text': appointment.service.name},
                ],
            }],
        )

    _async_send(app, _send)


def send_turn_approaching(app, tenant, queue_entry):
    """Template: turn_approaching (es casi tu turno)"""
    if not tenant.wa_phone_id or not tenant.wa_token:
        return
    if not queue_entry.client_phone:
        return
    client = WhatsAppClient(tenant.wa_phone_id, tenant.wa_token)

    def _send():
        client.send_template(
            to=queue_entry.client_phone,
            template_name='turn_approaching',
            components=[{
                'type': 'body',
                'parameters': [
                    {'type': 'text', 'text': queue_entry.client_name},
                    {'type': 'text', 'text': tenant.name},
                ],
            }],
        )

    _async_send(app, _send)
