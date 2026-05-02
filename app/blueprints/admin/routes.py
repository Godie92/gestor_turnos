import os
from datetime import date, time, datetime, timedelta
from functools import wraps

from flask import (render_template, redirect, url_for, request, flash,
                   jsonify, current_app, g, abort)
from flask_login import login_required, current_user
from werkzeug.utils import secure_filename

from app.extensions import db
from app.models.tenant import Tenant
from app.models.service import Service, Professional
from app.models.schedule import WorkingHours, BlockedSlot, WEEKDAY_NAMES
from app.models.user import StaffUser
import csv
import io
from app.models.appointment import Appointment
from app.models.queue_entry import QueueEntry
from app.services import queue_manager
from . import admin_bp
from flask import Response

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}


def _allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS


def tenant_required(f):
    """Carga el tenant del slug y verifica que el usuario pertenece a él."""
    @wraps(f)
    def decorated(*args, **kwargs):
        slug = kwargs.get('slug')
        tenant = Tenant.query.filter_by(slug=slug, is_active=True).first_or_404()
        if current_user.tenant_id != tenant.id:
            abort(403)
        g.tenant = tenant
        return f(*args, **kwargs)
    return decorated


# ─── Dashboard ──────────────────────────────────────────────────────────────

@admin_bp.route('/<slug>/admin/')
@login_required
@tenant_required
def dashboard(slug):
    tenant = g.tenant
    today = date.today()
    now = datetime.now()
    today_appts = (Appointment.query
                   .filter_by(tenant_id=tenant.id)
                   .filter(db.func.date(Appointment.scheduled_at) == today)
                   .filter(Appointment.status.notin_(['cancelled', 'no_show']))
                   .count())
    waiting = QueueEntry.query.filter_by(tenant_id=tenant.id, status='waiting').count()
    in_service = QueueEntry.query.filter_by(tenant_id=tenant.id, status='in_service').first()
    upcoming = (Appointment.query
                .filter_by(tenant_id=tenant.id)
                .filter(db.func.date(Appointment.scheduled_at) == today)
                .filter(Appointment.scheduled_at >= now)
                .filter(Appointment.status.in_(['confirmed']))
                .order_by(Appointment.scheduled_at)
                .limit(5)
                .all())
    return render_template('admin/dashboard.html', tenant=tenant,
                           today_appts=today_appts, waiting=waiting,
                           in_service=in_service, upcoming=upcoming)


# ─── Cola ────────────────────────────────────────────────────────────────────

@admin_bp.route('/<slug>/admin/cola')
@login_required
@tenant_required
def queue(slug):
    tenant = g.tenant
    services = Service.query.filter_by(tenant_id=tenant.id, is_active=True).all()
    professionals = Professional.query.filter_by(tenant_id=tenant.id, is_active=True).all()
    snapshot = queue_manager.get_queue_snapshot(tenant.id)

    active = (QueueEntry.query
              .filter_by(tenant_id=tenant.id)
              .filter(QueueEntry.status.in_(['waiting', 'called', 'in_service']))
              .order_by(QueueEntry.position)
              .all())

    return render_template('admin/queue.html', tenant=tenant, active=active,
                           services=services, professionals=professionals, snapshot=snapshot)


@admin_bp.route('/<slug>/admin/cola/agregar', methods=['POST'])
@login_required
@tenant_required
def queue_add(slug):
    tenant = g.tenant
    client_name = request.form.get('client_name', '').strip()
    client_phone = request.form.get('client_phone', '').strip()
    service_name = request.form.get('service_name', '').strip()
    professional_id = request.form.get('professional_id', type=int) or None

    if not client_name:
        flash('El nombre es requerido.', 'danger')
        return redirect(url_for('admin.queue', slug=slug))

    queue_manager.add_walkin(tenant.id, client_name, client_phone, service_name, professional_id)
    flash(f'{client_name} agregado a la cola.', 'success')
    from app.services.push_notifications import notify_async
    notify_async(current_app._get_current_object(), tenant.id,
                 '🔢 Nuevo cliente en cola',
                 f'{client_name} está esperando{" — " + service_name if service_name else ""}',
                 url_for('admin.queue', slug=slug))
    return redirect(url_for('admin.queue', slug=slug))


@admin_bp.route('/<slug>/admin/cola/<int:entry_id>/llamar', methods=['POST'])
@login_required
@tenant_required
def queue_call(slug, entry_id):
    tenant = g.tenant
    entry = QueueEntry.query.filter_by(id=entry_id, tenant_id=tenant.id).first_or_404()
    queue_manager.call_entry(entry.id)

    # Enviar notificación WA si tiene teléfono
    from app.services.whatsapp import send_turn_approaching
    send_turn_approaching(current_app._get_current_object(), tenant, entry)
    entry.turn_notif_sent = True
    db.session.commit()

    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True})
    return redirect(url_for('admin.queue', slug=slug))


@admin_bp.route('/<slug>/admin/cola/<int:entry_id>/iniciar', methods=['POST'])
@login_required
@tenant_required
def queue_start(slug, entry_id):
    tenant = g.tenant
    QueueEntry.query.filter_by(id=entry_id, tenant_id=tenant.id).first_or_404()
    queue_manager.mark_in_service(entry_id)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True})
    return redirect(url_for('admin.queue', slug=slug))


@admin_bp.route('/<slug>/admin/cola/<int:entry_id>/finalizar', methods=['POST'])
@login_required
@tenant_required
def queue_done(slug, entry_id):
    tenant = g.tenant
    QueueEntry.query.filter_by(id=entry_id, tenant_id=tenant.id).first_or_404()
    queue_manager.mark_done(entry_id)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True})
    return redirect(url_for('admin.queue', slug=slug))


@admin_bp.route('/<slug>/admin/cola/<int:entry_id>/cancelar', methods=['POST'])
@login_required
@tenant_required
def queue_cancel(slug, entry_id):
    tenant = g.tenant
    QueueEntry.query.filter_by(id=entry_id, tenant_id=tenant.id).first_or_404()
    queue_manager.cancel_entry(entry_id)
    if request.headers.get('X-Requested-With') == 'XMLHttpRequest':
        return jsonify({'ok': True})
    return redirect(url_for('admin.queue', slug=slug))


# ─── Turnos del día ──────────────────────────────────────────────────────────

@admin_bp.route('/<slug>/admin/turnos')
@login_required
@tenant_required
def appointments(slug):
    tenant = g.tenant
    date_str = request.args.get('date', '')
    search = request.args.get('q', '').strip()
    status_filter = request.args.get('status', '')

    try:
        selected_date = date.fromisoformat(date_str)
    except ValueError:
        selected_date = date.today()

    q = (Appointment.query
         .filter_by(tenant_id=tenant.id)
         .filter(db.func.date(Appointment.scheduled_at) == selected_date))

    if search:
        q = q.filter(
            db.or_(
                Appointment.client_name.ilike(f'%{search}%'),
                Appointment.client_phone.ilike(f'%{search}%'),
            )
        )
    if status_filter:
        q = q.filter_by(status=status_filter)

    appts = q.order_by(Appointment.scheduled_at).all()

    return render_template('admin/appointments.html', tenant=tenant,
                           appointments=appts,
                           selected_date=selected_date,
                           prev_date=(selected_date - timedelta(days=1)).isoformat(),
                           next_date=(selected_date + timedelta(days=1)).isoformat(),
                           today=date.today().isoformat(),
                           search=search,
                           status_filter=status_filter)


@admin_bp.route('/<slug>/admin/turnos/<int:appt_id>/llego', methods=['POST'])
@login_required
@tenant_required
def appointment_arrived(slug, appt_id):
    tenant = g.tenant
    appt = Appointment.query.filter_by(id=appt_id, tenant_id=tenant.id).first_or_404()
    if appt.status != 'confirmed':
        flash('Este turno no puede marcarse como llegado.', 'warning')
        return redirect(url_for('admin.appointments', slug=slug))
    queue_manager.add_from_appointment(appt)
    flash(f'{appt.client_name} agregado a la cola.', 'success')
    return redirect(url_for('admin.appointments', slug=slug))


@admin_bp.route('/<slug>/admin/turnos/<int:appt_id>/reagendar', methods=['POST'])
@login_required
@tenant_required
def appointment_reschedule(slug, appt_id):
    tenant = g.tenant
    appt = Appointment.query.filter_by(id=appt_id, tenant_id=tenant.id).first_or_404()
    if appt.status not in ('confirmed',):
        flash('Solo se pueden reagendar turnos confirmados.', 'warning')
        return redirect(url_for('admin.appointments', slug=slug))

    date_str = request.form.get('new_date', '').strip()
    time_str = request.form.get('new_time', '').strip()
    try:
        new_dt = datetime.fromisoformat(f'{date_str}T{time_str}')
    except ValueError:
        flash('Fecha u hora inválida.', 'danger')
        return redirect(url_for('admin.appointments', slug=slug,
                                date=appt.scheduled_at.date().isoformat()))

    old_date = appt.scheduled_at.date().isoformat()
    appt.scheduled_at = new_dt
    db.session.commit()
    flash(f'Turno de {appt.client_name} reagendado al {new_dt.strftime("%d/%m/%Y %H:%M")}.', 'success')
    return redirect(url_for('admin.appointments', slug=slug, date=old_date))


@admin_bp.route('/<slug>/admin/turnos/<int:appt_id>/notas', methods=['POST'])
@login_required
@tenant_required
def appointment_notes(slug, appt_id):
    tenant = g.tenant
    appt = Appointment.query.filter_by(id=appt_id, tenant_id=tenant.id).first_or_404()
    appt.notes = request.form.get('notes', '').strip() or None
    db.session.commit()
    flash('Notas guardadas.', 'success')
    return redirect(url_for('admin.appointments', slug=slug,
                            date=appt.scheduled_at.date().isoformat()))


@admin_bp.route('/<slug>/admin/turnos/<int:appt_id>/cancelar', methods=['POST'])
@login_required
@tenant_required
def appointment_cancel(slug, appt_id):
    tenant = g.tenant
    appt = Appointment.query.filter_by(id=appt_id, tenant_id=tenant.id).first_or_404()
    appt.status = 'cancelled'
    db.session.commit()
    flash('Turno cancelado.', 'info')
    return redirect(url_for('admin.appointments', slug=slug))


# ─── Configuración ───────────────────────────────────────────────────────────

@admin_bp.route('/<slug>/admin/calendario')
@login_required
@tenant_required
def calendar(slug):
    tenant = g.tenant
    professionals = Professional.query.filter_by(tenant_id=tenant.id, is_active=True).all()
    return render_template('admin/calendar.html', tenant=tenant, professionals=professionals)


@admin_bp.route('/<slug>/admin/calendario/eventos')
@login_required
@tenant_required
def calendar_events(slug):
    tenant = g.tenant
    start_str = request.args.get('start', '')
    end_str = request.args.get('end', '')
    professional_id = request.args.get('professional_id', type=int)

    try:
        start_dt = datetime.fromisoformat(start_str[:19]) if start_str else datetime.now().replace(day=1)
        end_dt = datetime.fromisoformat(end_str[:19]) if end_str else datetime.now()
    except ValueError:
        start_dt = datetime.now().replace(day=1)
        end_dt = datetime.now()

    q = (Appointment.query
         .filter_by(tenant_id=tenant.id)
         .filter(Appointment.scheduled_at >= start_dt)
         .filter(Appointment.scheduled_at <= end_dt)
         .filter(Appointment.status.notin_(['cancelled', 'no_show'])))
    if professional_id:
        q = q.filter_by(professional_id=professional_id)

    color_map = {
        'confirmed': '#6C63FF',
        'arrived':   '#3B82F6',
        'in_service': '#F59E0B',
        'done':      '#10B981',
    }

    events = []
    for appt in q.all():
        end_time = appt.scheduled_at + timedelta(minutes=appt.duration_min)
        events.append({
            'id': appt.id,
            'title': f'{appt.client_name} — {appt.service.name if appt.service else ""}',
            'start': appt.scheduled_at.isoformat(),
            'end': end_time.isoformat(),
            'color': color_map.get(appt.status, '#6C63FF'),
            'extendedProps': {
                'phone': appt.client_phone,
                'professional': appt.professional.name if appt.professional else '',
                'status': appt.status_label,
                'notes': appt.notes or '',
            },
        })

    return jsonify(events)


@admin_bp.route('/<slug>/admin/estadisticas')
@login_required
@tenant_required
def stats(slug):
    from sqlalchemy import func
    tenant = g.tenant

    # Rango: últimos 30 días
    end = date.today()
    start = end - timedelta(days=29)

    # Turnos por día (últimos 30)
    daily = (db.session.query(
                db.func.date(Appointment.scheduled_at).label('day'),
                db.func.count().label('total'))
             .filter(Appointment.tenant_id == tenant.id)
             .filter(Appointment.status.notin_(['cancelled', 'no_show']))
             .filter(db.func.date(Appointment.scheduled_at) >= start)
             .group_by('day').order_by('day').all())

    # Servicios más solicitados
    top_services = (db.session.query(
                        Service.name,
                        db.func.count(Appointment.id).label('total'))
                    .join(Appointment, Appointment.service_id == Service.id)
                    .filter(Appointment.tenant_id == tenant.id)
                    .filter(Appointment.status.notin_(['cancelled', 'no_show']))
                    .group_by(Service.name)
                    .order_by(db.func.count(Appointment.id).desc())
                    .limit(5).all())

    # Totales generales
    total_done     = Appointment.query.filter_by(tenant_id=tenant.id, status='done').count()
    total_cancelled= Appointment.query.filter_by(tenant_id=tenant.id, status='cancelled').count()
    total_confirmed= Appointment.query.filter_by(tenant_id=tenant.id, status='confirmed').count()

    # Clientes únicos
    unique_clients = (db.session.query(db.func.count(db.func.distinct(Appointment.client_phone)))
                      .filter(Appointment.tenant_id == tenant.id).scalar() or 0)

    # Stats por profesional (últimos 30 días)
    from app.models.service import Professional
    top_professionals = (db.session.query(
                            Professional.name,
                            db.func.count(Appointment.id).label('total'),
                        )
                        .join(Appointment, Appointment.professional_id == Professional.id)
                        .filter(Appointment.tenant_id == tenant.id)
                        .filter(Appointment.status.notin_(['cancelled', 'no_show']))
                        .filter(db.func.date(Appointment.scheduled_at) >= start)
                        .group_by(Professional.name)
                        .order_by(db.func.count(Appointment.id).desc())
                        .all())

    return render_template('admin/stats.html', tenant=tenant,
                           daily=daily, top_services=top_services,
                           top_professionals=top_professionals,
                           total_done=total_done, total_cancelled=total_cancelled,
                           total_confirmed=total_confirmed,
                           unique_clients=unique_clients,
                           start=start, end=end)


@admin_bp.route('/<slug>/admin/exportar')
@login_required
@tenant_required
def export_csv(slug):
    tenant = g.tenant
    date_from_str = request.args.get('from', '')
    date_to_str = request.args.get('to', '')
    try:
        date_from = date.fromisoformat(date_from_str)
    except ValueError:
        date_from = date.today().replace(day=1)
    try:
        date_to = date.fromisoformat(date_to_str)
    except ValueError:
        date_to = date.today()

    appts = (Appointment.query
             .filter_by(tenant_id=tenant.id)
             .filter(db.func.date(Appointment.scheduled_at) >= date_from)
             .filter(db.func.date(Appointment.scheduled_at) <= date_to)
             .order_by(Appointment.scheduled_at)
             .all())

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(['Fecha', 'Hora', 'Cliente', 'Teléfono', 'Servicio',
                     'Profesional', 'Estado', 'Notas'])
    for a in appts:
        writer.writerow([
            a.scheduled_at.strftime('%d/%m/%Y'),
            a.scheduled_at.strftime('%H:%M'),
            a.client_name, a.client_phone,
            a.service.name if a.service else '',
            a.professional.name if a.professional else '',
            a.status_label, a.notes or '',
        ])

    filename = f'turnos_{tenant.slug}_{date_from}_{date_to}.csv'
    return Response(
        '﻿' + output.getvalue(),  # BOM para Excel
        mimetype='text/csv; charset=utf-8',
        headers={'Content-Disposition': f'attachment; filename={filename}'},
    )


@admin_bp.route('/<slug>/admin/clientes')
@login_required
@tenant_required
def clients(slug):
    tenant = g.tenant
    page = request.args.get('page', 1, type=int)

    # Agrupar por teléfono
    subq = (db.session.query(
                Appointment.client_phone,
                Appointment.client_name,
                db.func.count(Appointment.id).label('total'),
                db.func.max(Appointment.scheduled_at).label('last_visit'),
            )
            .filter(Appointment.tenant_id == tenant.id)
            .filter(Appointment.status.notin_(['cancelled', 'no_show']))
            .group_by(Appointment.client_phone)
            .order_by(db.func.count(Appointment.id).desc()))

    # Paginación manual
    per_page = 20
    total = subq.count()
    clients_page = subq.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page

    return render_template('admin/clients.html', tenant=tenant,
                           clients=clients_page, page=page,
                           total_pages=total_pages, total=total)


@admin_bp.route('/<slug>/admin/clientes/<phone>')
@login_required
@tenant_required
def client_history(slug, phone):
    tenant = g.tenant
    page = request.args.get('page', 1, type=int)
    per_page = 15

    appts_q = (Appointment.query
               .filter_by(tenant_id=tenant.id, client_phone=phone)
               .order_by(Appointment.scheduled_at.desc()))
    total = appts_q.count()
    appts = appts_q.offset((page - 1) * per_page).limit(per_page).all()
    total_pages = (total + per_page - 1) // per_page
    client_name = appts[0].client_name if appts else phone

    return render_template('admin/client_history.html', tenant=tenant,
                           appts=appts, phone=phone, client_name=client_name,
                           page=page, total_pages=total_pages, total=total)


@admin_bp.route('/<slug>/admin/configuracion/staff', methods=['GET', 'POST'])
@login_required
@tenant_required
def settings_staff(slug):
    tenant = g.tenant
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            email = request.form.get('email', '').strip().lower()
            password = request.form.get('password', '')
            role = request.form.get('role', 'staff')
            if role not in ('owner', 'staff'):
                role = 'staff'

            if not email or '@' not in email:
                flash('Email inválido.', 'danger')
            elif len(password) < 6:
                flash('La contraseña debe tener al menos 6 caracteres.', 'danger')
            elif StaffUser.query.filter_by(tenant_id=tenant.id, email=email).first():
                flash('Ya existe un usuario con ese email.', 'danger')
            else:
                user = StaffUser(tenant_id=tenant.id, email=email, role=role)
                user.set_password(password)
                db.session.add(user)
                db.session.commit()
                flash(f'Usuario {email} agregado.', 'success')

        elif action == 'toggle':
            user_id = request.form.get('user_id', type=int)
            user = StaffUser.query.filter_by(id=user_id, tenant_id=tenant.id).first_or_404()
            if user.id == current_user.id:
                flash('No podés desactivarte a vos mismo.', 'warning')
            else:
                user.is_active = not user.is_active
                db.session.commit()

        elif action == 'delete':
            user_id = request.form.get('user_id', type=int)
            user = StaffUser.query.filter_by(id=user_id, tenant_id=tenant.id).first_or_404()
            if user.id == current_user.id:
                flash('No podés eliminar tu propio usuario.', 'warning')
            elif user.role == 'owner' and StaffUser.query.filter_by(tenant_id=tenant.id, role='owner', is_active=True).count() <= 1:
                flash('Debe quedar al menos un propietario activo.', 'warning')
            else:
                db.session.delete(user)
                db.session.commit()
                flash('Usuario eliminado.', 'info')

        return redirect(url_for('admin.settings_staff', slug=slug))

    staff = StaffUser.query.filter_by(tenant_id=tenant.id).order_by(StaffUser.role, StaffUser.email).all()
    return render_template('admin/settings/staff.html', tenant=tenant, staff=staff)


@admin_bp.route('/<slug>/admin/cuenta', methods=['GET', 'POST'])
@login_required
@tenant_required
def account(slug):
    tenant = g.tenant
    if request.method == 'POST':
        current_pw = request.form.get('current_password', '')
        new_pw = request.form.get('new_password', '')
        confirm_pw = request.form.get('confirm_password', '')

        if not current_user.check_password(current_pw):
            flash('La contraseña actual es incorrecta.', 'danger')
        elif len(new_pw) < 6:
            flash('La nueva contraseña debe tener al menos 6 caracteres.', 'danger')
        elif new_pw != confirm_pw:
            flash('Las contraseñas no coinciden.', 'danger')
        else:
            current_user.set_password(new_pw)
            db.session.commit()
            flash('Contraseña actualizada correctamente.', 'success')

        return redirect(url_for('admin.account', slug=slug))

    return render_template('admin/account.html', tenant=tenant)


@admin_bp.route('/<slug>/admin/configuracion')
@login_required
@tenant_required
def settings(slug):
    return redirect(url_for('admin.settings_general', slug=slug))


@admin_bp.route('/<slug>/admin/configuracion/general', methods=['GET', 'POST'])
@login_required
@tenant_required
def settings_general(slug):
    tenant = g.tenant
    if request.method == 'POST':
        tenant.name = request.form.get('name', tenant.name).strip()
        tenant.business_type = request.form.get('business_type', tenant.business_type)
        tenant.primary_color = request.form.get('primary_color', tenant.primary_color)
        tenant.phone_number = request.form.get('phone_number', '').strip()
        tenant.wa_number = request.form.get('wa_number', '').strip() or None
        tenant.wa_phone_id = request.form.get('wa_phone_id', '').strip()
        wa_token = request.form.get('wa_token', '').strip()
        if wa_token:
            tenant.wa_token = wa_token
        tenant.timezone = request.form.get('timezone', tenant.timezone)

        # MercadoPago
        mp_token = request.form.get('mp_access_token', '').strip()
        if mp_token:
            tenant.mp_access_token = mp_token if mp_token != '' else None

        # Email config
        email_user = request.form.get('email_user', '').strip()
        tenant.email_user = email_user or None
        tenant.email_host = request.form.get('email_host', 'smtp.gmail.com').strip() or 'smtp.gmail.com'
        tenant.email_port = int(request.form.get('email_port') or 587)
        email_pw = request.form.get('email_password', '').strip()
        if email_pw:
            tenant.email_password = email_pw
        tenant.email_from = email_user or None

        # Logo upload
        logo_file = request.files.get('logo')
        if logo_file and logo_file.filename and _allowed_file(logo_file.filename):
            filename = secure_filename(f'{tenant.slug}_{logo_file.filename}')
            upload_dir = current_app.config['UPLOAD_FOLDER']
            os.makedirs(upload_dir, exist_ok=True)
            logo_file.save(os.path.join(upload_dir, filename))
            tenant.logo_url = url_for('static', filename=f'uploads/logos/{filename}')

        db.session.commit()
        flash('Configuración guardada.', 'success')
        return redirect(url_for('admin.settings_general', slug=slug))

    return render_template('admin/settings/general.html', tenant=tenant)


@admin_bp.route('/<slug>/admin/configuracion/servicios', methods=['GET', 'POST'])
@login_required
@tenant_required
def settings_services(slug):
    tenant = g.tenant
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            name = request.form.get('name', '').strip()
            duration = request.form.get('duration_min', type=int, default=30)
            price = request.form.get('price') or None
            if name:
                svc = Service(tenant_id=tenant.id, name=name,
                              duration_min=duration, price=price)
                db.session.add(svc)
                db.session.commit()
                flash(f'Servicio "{name}" agregado.', 'success')

        elif action == 'toggle':
            svc_id = request.form.get('service_id', type=int)
            svc = Service.query.filter_by(id=svc_id, tenant_id=tenant.id).first_or_404()
            svc.is_active = not svc.is_active
            db.session.commit()

        elif action == 'delete':
            svc_id = request.form.get('service_id', type=int)
            svc = Service.query.filter_by(id=svc_id, tenant_id=tenant.id).first_or_404()
            db.session.delete(svc)
            db.session.commit()
            flash('Servicio eliminado.', 'info')

        return redirect(url_for('admin.settings_services', slug=slug))

    services = Service.query.filter_by(tenant_id=tenant.id).all()
    return render_template('admin/settings/services.html', tenant=tenant, services=services)


@admin_bp.route('/<slug>/admin/configuracion/profesionales', methods=['GET', 'POST'])
@login_required
@tenant_required
def settings_professionals(slug):
    tenant = g.tenant
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            name = request.form.get('name', '').strip()
            if name:
                pro = Professional(tenant_id=tenant.id, name=name)
                db.session.add(pro)
                db.session.commit()
                flash(f'Profesional "{name}" agregado.', 'success')

        elif action == 'delete':
            pro_id = request.form.get('professional_id', type=int)
            pro = Professional.query.filter_by(id=pro_id, tenant_id=tenant.id).first_or_404()
            db.session.delete(pro)
            db.session.commit()
            flash('Profesional eliminado.', 'info')

        elif action == 'assign_services':
            pro_id = request.form.get('professional_id', type=int)
            pro = Professional.query.filter_by(id=pro_id, tenant_id=tenant.id).first_or_404()
            service_ids = request.form.getlist('service_ids', type=int)
            services_sel = Service.query.filter(
                Service.id.in_(service_ids), Service.tenant_id == tenant.id
            ).all() if service_ids else []
            pro.services = services_sel
            db.session.commit()
            flash(f'Servicios de {pro.name} actualizados.', 'success')

        return redirect(url_for('admin.settings_professionals', slug=slug))

    professionals = Professional.query.filter_by(tenant_id=tenant.id).all()
    services = Service.query.filter_by(tenant_id=tenant.id, is_active=True).all()
    return render_template('admin/settings/professionals.html', tenant=tenant,
                           professionals=professionals, services=services)


@admin_bp.route('/<slug>/admin/configuracion/bloqueos', methods=['GET', 'POST'])
@login_required
@tenant_required
def settings_blocked(slug):
    tenant = g.tenant
    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'add':
            start_str = request.form.get('start_dt', '').strip()
            end_str = request.form.get('end_dt', '').strip()
            reason = request.form.get('reason', '').strip()
            try:
                start_dt = datetime.fromisoformat(start_str)
                end_dt = datetime.fromisoformat(end_str)
                if end_dt <= start_dt:
                    flash('La fecha de fin debe ser posterior al inicio.', 'danger')
                else:
                    db.session.add(BlockedSlot(
                        tenant_id=tenant.id,
                        start_dt=start_dt,
                        end_dt=end_dt,
                        reason=reason or None,
                    ))
                    db.session.commit()
                    flash('Bloqueo agregado.', 'success')
            except ValueError:
                flash('Fecha inválida.', 'danger')

        elif action == 'delete':
            block_id = request.form.get('block_id', type=int)
            block = BlockedSlot.query.filter_by(id=block_id, tenant_id=tenant.id).first_or_404()
            db.session.delete(block)
            db.session.commit()
            flash('Bloqueo eliminado.', 'info')

        return redirect(url_for('admin.settings_blocked', slug=slug))

    blocks = (BlockedSlot.query
              .filter_by(tenant_id=tenant.id)
              .order_by(BlockedSlot.start_dt)
              .all())
    return render_template('admin/settings/blocked.html', tenant=tenant, blocks=blocks)


@admin_bp.route('/<slug>/admin/configuracion/horarios', methods=['GET', 'POST'])
@login_required
@tenant_required
def settings_hours(slug):
    tenant = g.tenant
    if request.method == 'POST':
        for weekday in range(7):
            is_open = f'open_{weekday}' in request.form
            open_str = request.form.get(f'open_time_{weekday}', '09:00')
            close_str = request.form.get(f'close_time_{weekday}', '18:00')
            try:
                open_t = time.fromisoformat(open_str)
                close_t = time.fromisoformat(close_str)
            except ValueError:
                continue

            wh = WorkingHours.query.filter_by(
                tenant_id=tenant.id, weekday=weekday).first()
            if wh:
                wh.is_open = is_open
                wh.open_time = open_t
                wh.close_time = close_t
            else:
                wh = WorkingHours(tenant_id=tenant.id, weekday=weekday,
                                  open_time=open_t, close_time=close_t, is_open=is_open)
                db.session.add(wh)
        db.session.commit()
        flash('Horarios guardados.', 'success')
        return redirect(url_for('admin.settings_hours', slug=slug))

    hours = {wh.weekday: wh for wh in
             WorkingHours.query.filter_by(tenant_id=tenant.id).all()}
    return render_template('admin/settings/hours.html', tenant=tenant,
                           hours=hours, weekday_names=WEEKDAY_NAMES)
