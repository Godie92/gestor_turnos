from django.core.mail import send_mail
from django.template.loader import render_to_string
from django.conf import settings
from django.utils import timezone


def send_booking_confirmation(booking):
    client_email = None
    if booking.client and booking.client.email:
        client_email = booking.client.email
    if not client_email:
        return

    app = settings.APP_CONFIG
    local_start = timezone.localtime(booking.start_time)
    subject = f"Confirmación de turno — {booking.service_name} | {local_start.strftime('%d/%m/%Y %H:%M')}"

    body = render_to_string('bookings/emails/confirmation.txt', {
        'booking': booking,
        'app': app,
        'tenant_name': booking.tenant.name,
        'local_start': local_start,
    })

    try:
        send_mail(
            subject=subject,
            message=body,
            from_email=settings.DEFAULT_FROM_EMAIL,
            recipient_list=[client_email],
            fail_silently=True,
        )
    except Exception:
        pass
