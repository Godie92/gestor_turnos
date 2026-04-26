"""
APScheduler — recordatorios 30 min antes y día anterior.
"""
import logging
from datetime import datetime, timedelta, date

from apscheduler.schedulers.background import BackgroundScheduler

logger = logging.getLogger(__name__)
_scheduler = BackgroundScheduler(timezone='UTC')


def init_scheduler(app):
    _scheduler.add_job(
        func=_send_due_reminders,
        args=[app],
        trigger='interval',
        minutes=1,
        id='reminder_scan',
        replace_existing=True,
    )
    _scheduler.add_job(
        func=_send_day_before_reminders,
        args=[app],
        trigger='interval',
        minutes=30,
        id='day_before_scan',
        replace_existing=True,
    )
    _scheduler.start()
    logger.info('Scheduler iniciado')


def _send_due_reminders(app):
    """Envía recordatorios a turnos que empiezan en ~30 minutos."""
    from app.extensions import db
    from app.models.appointment import Appointment
    from app.models.tenant import Tenant
    from app.services.whatsapp import send_appointment_reminder

    with app.app_context():
        now = datetime.now()
        window_start = now + timedelta(minutes=28)
        window_end = now + timedelta(minutes=32)

        due = Appointment.query.filter(
            Appointment.scheduled_at >= window_start,
            Appointment.scheduled_at <= window_end,
            Appointment.reminder_sent == False,
            Appointment.status == 'confirmed',
        ).all()

        for appt in due:
            try:
                tenant = db.session.get(Tenant, appt.tenant_id)
                send_appointment_reminder(app, tenant, appt)
                from app.services.email_service import send_reminder_email
                send_reminder_email(tenant, appt)
                appt.reminder_sent = True
                db.session.commit()
            except Exception as e:
                logger.error('Error enviando recordatorio para appointment %s: %s', appt.id, e)


def _send_day_before_reminders(app):
    """Envía recordatorio el día anterior al turno (entre las 18 y 20 hs)."""
    from app.extensions import db
    from app.models.appointment import Appointment
    from app.models.tenant import Tenant
    from app.services.whatsapp import send_day_before_reminder

    with app.app_context():
        now = datetime.now()
        # Solo enviar entre las 18:00 y 20:00
        if not (18 <= now.hour < 20):
            return

        tomorrow_start = datetime.combine(date.today() + timedelta(days=1),
                                          __import__('datetime').time.min)
        tomorrow_end = datetime.combine(date.today() + timedelta(days=1),
                                        __import__('datetime').time.max)

        due = Appointment.query.filter(
            Appointment.scheduled_at >= tomorrow_start,
            Appointment.scheduled_at <= tomorrow_end,
            Appointment.day_reminder_sent == False,
            Appointment.status == 'confirmed',
        ).all()

        for appt in due:
            try:
                tenant = db.session.get(Tenant, appt.tenant_id)
                send_day_before_reminder(app, tenant, appt)
                from app.services.email_service import send_reminder_email
                send_reminder_email(tenant, appt)
                appt.day_reminder_sent = True
                db.session.commit()
            except Exception as e:
                logger.error('Error recordatorio día anterior appointment %s: %s', appt.id, e)
