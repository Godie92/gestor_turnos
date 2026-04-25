import re
from datetime import datetime, date, time
from flask import render_template, redirect, url_for, request, flash, current_app, abort
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

        # Horarios por defecto: Lunes-Viernes 9-18
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
        from app.services.email_service import send_booking_confirmation_email
        send_booking_confirmation_email(tenant, appt, cancel_url)
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
    return render_template('public/confirmation.html', tenant=tenant, appointment=appt)


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
