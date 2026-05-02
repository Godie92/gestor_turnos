"""
Envío de emails transaccionales usando la config SMTP del tenant.
No lanza excepciones — si no está configurado simplemente no envía.
"""
import logging
import smtplib
import ssl
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from threading import Thread

logger = logging.getLogger(__name__)


def _send_smtp(host, port, user, password, from_addr, to, subject, html):
    try:
        msg = MIMEMultipart('alternative')
        msg['Subject'] = subject
        msg['From'] = from_addr
        msg['To'] = to
        msg.attach(MIMEText(html, 'html', 'utf-8'))

        context = ssl.create_default_context()
        with smtplib.SMTP(host, port, timeout=10) as server:
            server.starttls(context=context)
            server.login(user, password)
            server.sendmail(from_addr, to, msg.as_string())
        logger.info('Email enviado a %s', to)
    except Exception as e:
        logger.warning('Email no enviado a %s: %s', to, e)


def send_tenant_email(tenant, to: str, subject: str, html: str):
    """Envía email usando la config SMTP del tenant. No hace nada si no está configurado."""
    if not tenant.email_user or not tenant.email_password:
        return
    if not to or '@' not in to:
        return
    Thread(
        target=_send_smtp,
        args=(
            tenant.email_host or 'smtp.gmail.com',
            tenant.email_port or 587,
            tenant.email_user,
            tenant.email_password,
            tenant.email_from or tenant.email_user,
            to, subject, html,
        ),
        daemon=True,
    ).start()


def send_booking_confirmation_email(tenant, appointment, cancel_url: str):
    to = getattr(appointment, 'client_email', None)
    if not to:
        return
    subject = f'Turno confirmado en {tenant.name}'
    prof = f'<tr><td style="color:#666;padding:.3rem 0">👤 Profesional:</td><td><strong>{appointment.professional.name}</strong></td></tr>' if appointment.professional else ''
    html = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:0 auto;padding:1rem">
      <h2 style="color:#6C63FF;margin-bottom:1rem">✅ Turno confirmado</h2>
      <p>Hola <strong>{appointment.client_name}</strong>, tu turno fue confirmado.</p>
      <table style="background:#f8f9fa;border-radius:10px;padding:1rem 1.25rem;width:100%;margin:1rem 0;border-collapse:collapse">
        <tr><td style="color:#666;padding:.3rem 0">📅 Fecha:</td>
            <td><strong>{appointment.scheduled_at.strftime('%d/%m/%Y %H:%M')}</strong></td></tr>
        <tr><td style="color:#666;padding:.3rem 0">💅 Servicio:</td>
            <td>{appointment.service.name if appointment.service else '—'}</td></tr>
        {prof}
        <tr><td style="color:#666;padding:.3rem 0">📍 Negocio:</td>
            <td>{tenant.name}</td></tr>
      </table>
      <p style="margin-top:1.5rem">
        <a href="{cancel_url}"
           style="color:#e74c3c;font-size:.9rem">¿No podés ir? Cancelar turno →</a>
      </p>
      <hr style="border:none;border-top:1px solid #eee;margin:1.5rem 0">
      <p style="color:#aaa;font-size:.8rem">{tenant.name}</p>
    </div>
    """
    send_tenant_email(tenant, to, subject, html)


def send_new_booking_admin_email(tenant, appointment):
    """Notifica al dueño del negocio cuando llega un turno nuevo."""
    to = tenant.email_user
    if not to:
        return
    subject = f'Nuevo turno: {appointment.client_name} — {appointment.scheduled_at.strftime("%d/%m %H:%M")}'
    prof = f'<tr><td style="color:#666;padding:.3rem 0">👤 Profesional:</td><td><strong>{appointment.professional.name}</strong></td></tr>' if appointment.professional else ''
    email_str = f'<tr><td style="color:#666;padding:.3rem 0">📧 Email:</td><td>{appointment.client_email}</td></tr>' if appointment.client_email else ''
    html = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:0 auto;padding:1rem">
      <h2 style="color:#6C63FF;margin-bottom:1rem">📅 Nuevo turno reservado</h2>
      <p>Llegó una reserva nueva en <strong>{tenant.name}</strong>.</p>
      <table style="background:#f8f9fa;border-radius:10px;padding:1rem 1.25rem;width:100%;margin:1rem 0;border-collapse:collapse">
        <tr><td style="color:#666;padding:.3rem 0">👤 Cliente:</td>
            <td><strong>{appointment.client_name}</strong></td></tr>
        <tr><td style="color:#666;padding:.3rem 0">📞 Teléfono:</td>
            <td>{appointment.client_phone}</td></tr>
        {email_str}
        <tr><td style="color:#666;padding:.3rem 0">💅 Servicio:</td>
            <td>{appointment.service.name if appointment.service else '—'}</td></tr>
        {prof}
        <tr><td style="color:#666;padding:.3rem 0">📅 Fecha:</td>
            <td><strong>{appointment.scheduled_at.strftime('%d/%m/%Y %H:%M')}</strong></td></tr>
      </table>
      <hr style="border:none;border-top:1px solid #eee;margin:1.5rem 0">
      <p style="color:#aaa;font-size:.8rem">{tenant.name}</p>
    </div>
    """
    send_tenant_email(tenant, to, subject, html)


def send_reminder_email(tenant, appointment):
    to = getattr(appointment, 'client_email', None)
    if not to:
        return
    subject = f'Recordatorio: tu turno mañana en {tenant.name}'
    html = f"""
    <div style="font-family:sans-serif;max-width:520px;margin:0 auto;padding:1rem">
      <h2 style="color:#6C63FF;margin-bottom:1rem">⏰ Recordatorio de turno</h2>
      <p>Hola <strong>{appointment.client_name}</strong>, mañana tenés turno.</p>
      <table style="background:#f8f9fa;border-radius:10px;padding:1rem 1.25rem;width:100%;margin:1rem 0;border-collapse:collapse">
        <tr><td style="color:#666;padding:.3rem 0">📅 Fecha:</td>
            <td><strong>{appointment.scheduled_at.strftime('%d/%m/%Y %H:%M')}</strong></td></tr>
        <tr><td style="color:#666;padding:.3rem 0">💅 Servicio:</td>
            <td>{appointment.service.name if appointment.service else '—'}</td></tr>
        <tr><td style="color:#666;padding:.3rem 0">📍 Negocio:</td>
            <td>{tenant.name}</td></tr>
      </table>
      <hr style="border:none;border-top:1px solid #eee;margin:1.5rem 0">
      <p style="color:#aaa;font-size:.8rem">{tenant.name}</p>
    </div>
    """
    send_tenant_email(tenant, to, subject, html)
