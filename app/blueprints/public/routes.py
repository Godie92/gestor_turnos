import re
from datetime import datetime, date, time
from flask import render_template, redirect, url_for, request, flash, current_app, abort, jsonify
from itsdangerous import URLSafeTimedSerializer, BadSignature, SignatureExpired

from app.extensions import db
from app.models.tenant import Tenant
from app.models.user import StaffUser
from app.models.service import Service, Professional
from app.models.schedule import WorkingHours
from app.models.appointment import Appointment
from app.services.whatsapp import send_booking_confirmation
from . import public_bp


def _get_tenant(slug):
    return Tenant.query.filter_by(slug=slug, is_active=True).first_or_404()


def _make_token(appointment_id):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return s.dumps(appointment_id, salt='booking')


def _load_token(token, max_age=60 * 60 * 24 * 30):
    s = URLSafeTimedSerializer(current_app.config['SECRET_KEY'])
    return s.loads(token, salt='booking', max_age=max_age)


@public_bp.route('/registro', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        slug = request.form.get('slug', '').strip().lower()
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        business_type = request.form.get('business_type', 'general')

        errors = []
        if not name:
            errors.append('El nombre del negocio es requerido.')
        if not slug or not re.match(r'^[a-z0-9-]+$', slug):
            errors.append('El slug solo puede tener letras minúsculas, números y guiones.')
        if not email or '@' not in email:
            errors.append('Email inválido.')
        if len(password) < 6:
            errors.append('La contraseña debe tener al menos 6 caracteres.')
        if Tenant.query.filter_by(slug=slug).first():
            errors.append(f'El slug "{slug}" ya está en uso, elegí otro.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('public/register.html', form=request.form)

        tenant = Tenant(slug=slug, name=name, business_type=business_type)
        db.session.add(tenant)
        db.session.flush()

        user = StaffUser(tenant_id=tenant.id, email=email, role='owner')
        user.set_password(password)
        db.session.add(user)

        for weekday in range(5):
            db.session.add(WorkingHours(
                tenant_id=tenant.id, weekday=weekday,
                open_time=time(9, 0), close_time=time(18, 0), is_open=True,
            ))
        for weekday in [5, 6]:
            db.session.add(WorkingHours(
                tenant_id=tenant.id, weekday=weekday,
                open_time=time(9, 0), close_time=time(18, 0), is_open=False,
            ))

        db.session.commit()
        flash(f'¡Negocio creado! Iniciá sesión con {email}.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('public/register.html', form={})


@public_bp.route('/<slug>/')
def landing(slug):
    return redirect(url_for('public.booking', slug=slug))


@public_bp.route('/<slug>/reservar', methods=['GET', 'POST'])
def booking(slug):
    tenant = _get_tenant(slug)
    services = Service.query.filter_by(tenant_id=tenant.id, is_active=True).all()
    professionals = Professional.query.filter_by(tenant_id=tenant.id, is_active=True).all()

    if request.method == 'POST':
        service_id = request.form.get('service_id', type=int)
        professional_id = request.form.get('professional_id', type=int) or None
        client_name = request.form.get('client_name', '').strip()
        client_phone = request.form.get('client_phone', '').strip()
        client_email = request.form.get('client_email', '').strip().lower() or None
        date_str = request.form.get('date', '').strip()
        time_str = request.form.get('time', '').strip()

        errors = []
        if not service_id:
            errors.append('Seleccioná un servicio.')
        if not client_name:
            errors.append('Ingresá tu nombre.')
        if not client_phone:
            errors.append('Ingresá tu teléfono.')
        if not date_str or not time_str:
            errors.append('Seleccioná fecha y horario.')

        if not errors:
            service = Service.query.filter_by(id=service_id, tenant_id=tenant.id).first()
            if not service:
                errors.append('Servicio no encontrado.')

        if errors:
            for e in errors:
                flash(e, 'danger')
            return render_template('public/booking.html', tenant=tenant,
                                   services=services, professionals=professionals)

        try:
            scheduled_at = datetime.fromisoformat(f'{date_str}T{time_str}')
        except ValueError:
            flash('Fecha u hora inválida.', 'danger')
            return render_template('public/booking.html', tenant=tenant,
                                   services=services, professionals=professionals)

        # Verificar disponibilidad real del slot
        from app.services.slot_calculator import get_available_slots
        available_isos = {s['iso'] for s in get_available_slots(
            tenant.id, scheduled_at.date(), service.duration_min, professional_id
        )}
        if scheduled_at.isoformat() not in available_isos:
            flash('Ese horario ya no está disponible, por favor elegí otro.', 'danger')
            return render_template('public/booking.html', tenant=tenant,
                                   services=services, professionals=professionals)

        appt = Appointment(
            tenant_id=tenant.id,
            service_id=service_id,
            professional_id=professional_id,
            client_name=client_name,
            client_phone=client_phone,
            client_email=client_email,
            scheduled_at=scheduled_at,
            duration_min=service.duration_min,
            status='confirmed',
        )
        db.session.add(appt)
        db.session.commit()

        token = _make_token(appt.id)
        cancel_url = url_for('public.cancel_booking', slug=slug, token=token, _external=True)
        send_booking_confirmation(current_app._get_current_object(), tenant, appt, cancel_url)
        from app.services.email_service import send_booking_confirmation_email, send_new_booking_admin_email
        send_booking_confirmation_email(tenant, appt, cancel_url)
        send_new_booking_admin_email(tenant, appt)
        appt.confirmation_sent = True
        db.session.commit()

        return redirect(url_for('public.booking_confirmation', slug=slug, token=token))

    return render_template('public/booking.html', tenant=tenant,
                           services=services, professionals=professionals)


@public_bp.route('/<slug>/reservar/confirmacion/<token>')
def booking_confirmation(slug, token):
    tenant = _get_tenant(slug)
    try:
        appt_id = _load_token(token)
    except (BadSignature, SignatureExpired):
        abort(404)
    appt = Appointment.query.filter_by(id=appt_id, tenant_id=tenant.id).first_or_404()
    return render_template('public/confirmation.html', tenant=tenant, appointment=appt, token=token)


@public_bp.route('/<slug>/reservar/cancelar/<token>', methods=['GET', 'POST'])
def cancel_booking(slug, token):
    tenant = _get_tenant(slug)
    try:
        appt_id = _load_token(token)
    except (BadSignature, SignatureExpired):
        abort(404)
    appt = Appointment.query.filter_by(id=appt_id, tenant_id=tenant.id).first_or_404()

    if appt.status in ('done', 'cancelled'):
        return render_template('public/cancel.html', tenant=tenant, appointment=appt,
                               already_done=True)

    if request.method == 'POST':
        appt.status = 'cancelled'
        db.session.commit()
        flash('Tu turno fue cancelado.', 'info')
        return render_template('public/cancel.html', tenant=tenant, appointment=appt,
                               cancelled=True)

    return render_template('public/cancel.html', tenant=tenant, appointment=appt)


# ─── Historial del cliente ────────────────────────────────────────────────────

@public_bp.route('/<slug>/mis-turnos', methods=['GET', 'POST'])
def my_appointments(slug):
    tenant = _get_tenant(slug)
    appts = []
    phone = ''

    if request.method == 'POST':
        phone = request.form.get('phone', '').strip()
        if phone:
            appts = (Appointment.query
                     .filter_by(tenant_id=tenant.id, client_phone=phone)
                     .order_by(Appointment.scheduled_at.desc())
                     .limit(20).all())
            if not appts:
                flash('No encontramos turnos con ese teléfono.', 'warning')

    return render_template('public/my_appointments.html', tenant=tenant,
                           appointments=appts, phone=phone, now=datetime.now())


@public_bp.route('/<slug>/mis-turnos/cancelar/<int:appt_id>', methods=['POST'])
def my_appointments_cancel(slug, appt_id):
    tenant = _get_tenant(slug)
    phone = request.form.get('phone', '').strip()
    appt = Appointment.query.filter_by(
        id=appt_id, tenant_id=tenant.id, client_phone=phone
    ).first_or_404()

    if appt.status == 'confirmed' and appt.scheduled_at > datetime.now():
        appt.status = 'cancelled'
        db.session.commit()
        flash('Turno cancelado correctamente.', 'info')
    else:
        flash('No se puede cancelar este turno.', 'warning')

    return redirect(url_for('public.my_appointments', slug=slug))


# ─── MercadoPago ─────────────────────────────────────────────────────────────

@public_bp.route('/<slug>/pagar/<token>', methods=['POST'])
def mp_pay(slug, token):
    tenant = _get_tenant(slug)
    try:
        appt_id = _load_token(token)
    except (BadSignature, SignatureExpired):
        abort(404)
    appt = Appointment.query.filter_by(id=appt_id, tenant_id=tenant.id).first_or_404()

    if not tenant.mp_access_token:
        abort(404)

    price = float(appt.service.price) if appt.service and appt.service.price else None
    if not price:
        flash('Este servicio no tiene precio configurado.', 'warning')
        return redirect(url_for('public.booking_confirmation', slug=slug, token=token))

    try:
        import mercadopago
        sdk = mercadopago.SDK(tenant.mp_access_token)
        preference_data = {
            'items': [{
                'title': f'Turno - {appt.service.name}',
                'quantity': 1,
                'unit_price': price,
                'currency_id': 'ARS',
            }],
            'back_urls': {
                'success': url_for('public.mp_return', slug=slug, token=token,
                                   status='ok', _external=True),
                'failure': url_for('public.mp_return', slug=slug, token=token,
                                   status='fail', _external=True),
                'pending': url_for('public.mp_return', slug=slug, token=token,
                                   status='pending', _external=True),
            },
            'auto_return': 'approved',
            'notification_url': url_for('public.mp_webhook', slug=slug, _external=True),
            'external_reference': str(appt.id),
        }
        result = sdk.preference().create(preference_data)
        checkout_url = result['response'].get('init_point')
        if not checkout_url:
            raise ValueError('No init_point en respuesta de MP')
        return redirect(checkout_url)
    except Exception as e:
        current_app.logger.error('MP error tenant %s: %s', slug, e)
        flash('Error al conectar con MercadoPago. Intentá más tarde.', 'danger')
        return redirect(url_for('public.booking_confirmation', slug=slug, token=token))


@public_bp.route('/<slug>/pago/resultado')
def mp_return(slug):
    tenant = _get_tenant(slug)
    status = request.args.get('status', '')
    token = request.args.get('token', '')
    return render_template('public/mp_return.html', tenant=tenant,
                           status=status, token=token)


@public_bp.route('/<slug>/mp/webhook', methods=['POST'])
def mp_webhook(slug):
    tenant = _get_tenant(slug)
    data = request.get_json(silent=True) or {}

    payment_id = data.get('data', {}).get('id')
    topic = data.get('type', '')

    if topic == 'payment' and payment_id and tenant.mp_access_token:
        try:
            import mercadopago
            sdk = mercadopago.SDK(tenant.mp_access_token)
            payment = sdk.payment().get(payment_id)
            payment_data = payment['response']
            appt_id = int(payment_data.get('external_reference', 0))
            payment_status = payment_data.get('status')

            appt = Appointment.query.filter_by(id=appt_id, tenant_id=tenant.id).first()
            if appt:
                appt.payment_status = 'paid' if payment_status == 'approved' else payment_status
                db.session.commit()
        except Exception as e:
            current_app.logger.error('MP webhook error: %s', e)

    return jsonify({'ok': True})
