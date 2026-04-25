"""
Lógica central de la cola de turnos del día.
Todas las funciones esperan estar dentro de un app context con DB disponible.
"""
from datetime import datetime

from app.extensions import db
from app.models.queue_entry import QueueEntry


def _next_position(tenant_id: int) -> int:
    last = (
        QueueEntry.query
        .filter_by(tenant_id=tenant_id)
        .filter(QueueEntry.status.in_(['waiting', 'called', 'in_service']))
        .order_by(QueueEntry.position.desc())
        .first()
    )
    return (last.position + 1) if last else 1


def _renumber(tenant_id: int):
    """Re-numera contiguamente los entries en espera después de done/cancel."""
    entries = (
        QueueEntry.query
        .filter_by(tenant_id=tenant_id)
        .filter(QueueEntry.status.in_(['waiting', 'called']))
        .order_by(QueueEntry.position)
        .all()
    )
    for i, entry in enumerate(entries, start=1):
        entry.position = i
    db.session.commit()


def add_walkin(tenant_id: int, client_name: str, client_phone: str = None,
               service_name: str = None, professional_id: int = None) -> QueueEntry:
    """Agrega un cliente walk-in a la cola."""
    entry = QueueEntry(
        tenant_id=tenant_id,
        client_name=client_name,
        client_phone=client_phone or '',
        service_name=service_name or '',
        professional_id=professional_id,
        position=_next_position(tenant_id),
        status='waiting',
    )
    db.session.add(entry)
    db.session.commit()
    return entry


def add_from_appointment(appointment) -> QueueEntry:
    """Crea un QueueEntry a partir de una reserva confirmada que llegó."""
    entry = QueueEntry(
        tenant_id=appointment.tenant_id,
        appointment_id=appointment.id,
        client_name=appointment.client_name,
        client_phone=appointment.client_phone,
        service_name=appointment.service.name if appointment.service else '',
        professional_id=appointment.professional_id,
        position=_next_position(appointment.tenant_id),
        status='waiting',
    )
    db.session.add(entry)
    appointment.status = 'arrived'
    db.session.commit()
    return entry


def call_entry(entry_id: int) -> QueueEntry:
    """Llama a un cliente específico (lo marca como 'called')."""
    entry = db.get_or_404(QueueEntry, entry_id)
    entry.status = 'called'
    entry.called_at = datetime.utcnow()
    db.session.commit()
    return entry


def mark_in_service(entry_id: int) -> QueueEntry:
    entry = db.get_or_404(QueueEntry, entry_id)
    entry.status = 'in_service'
    entry.started_at = datetime.utcnow()
    if entry.appointment:
        entry.appointment.status = 'in_service'
    db.session.commit()
    return entry


def mark_done(entry_id: int) -> QueueEntry:
    entry = db.get_or_404(QueueEntry, entry_id)
    entry.status = 'done'
    entry.finished_at = datetime.utcnow()
    if entry.appointment:
        entry.appointment.status = 'done'
    db.session.commit()
    _renumber(entry.tenant_id)
    return entry


def cancel_entry(entry_id: int) -> QueueEntry:
    entry = db.get_or_404(QueueEntry, entry_id)
    entry.status = 'cancelled'
    if entry.appointment and entry.appointment.status not in ('done', 'cancelled'):
        entry.appointment.status = 'cancelled'
    db.session.commit()
    _renumber(entry.tenant_id)
    return entry


def _avg_service_minutes(tenant_id: int) -> int:
    """Promedio de duración real de atención de los últimos 20 turnos finalizados."""
    from sqlalchemy import func
    done = (
        QueueEntry.query
        .filter_by(tenant_id=tenant_id, status='done')
        .filter(QueueEntry.started_at.isnot(None), QueueEntry.finished_at.isnot(None))
        .order_by(QueueEntry.finished_at.desc())
        .limit(20)
        .all()
    )
    if done:
        durations = [(e.finished_at - e.started_at).total_seconds() / 60 for e in done]
        return max(5, int(sum(durations) / len(durations)))
    return 15  # fallback: 15 minutos


def get_queue_snapshot(tenant_id: int) -> dict:
    """Devuelve el estado actual de la cola para la pantalla TV y el admin."""
    current = (
        QueueEntry.query
        .filter_by(tenant_id=tenant_id, status='in_service')
        .first()
    )
    called = (
        QueueEntry.query
        .filter_by(tenant_id=tenant_id, status='called')
        .order_by(QueueEntry.position)
        .first()
    )
    next_entry = (
        QueueEntry.query
        .filter_by(tenant_id=tenant_id, status='waiting')
        .order_by(QueueEntry.position)
        .first()
    )
    waiting_list = (
        QueueEntry.query
        .filter_by(tenant_id=tenant_id, status='waiting')
        .order_by(QueueEntry.position)
        .all()
    )

    avg_min = _avg_service_minutes(tenant_id)

    def entry_dict(e, wait_pos=0):
        if not e:
            return None
        est_wait = wait_pos * avg_min
        return {
            'id': e.id,
            'position': e.position,
            'client_name': e.client_name,
            'service_name': e.service_name,
            'client_phone': e.client_phone or '',
            'professional_name': e.professional.name if e.professional else '',
            'status': e.status,
            'status_label': e.status_label,
            'est_wait_min': est_wait,
        }

    # Armar lista con posición de espera para calcular tiempo
    waiting_dicts = [entry_dict(e, i) for i, e in enumerate(waiting_list)]

    return {
        'current': entry_dict(current),
        'called': entry_dict(called),
        'next': entry_dict(next_entry, 0),
        'waiting_count': len(waiting_list),
        'waiting_list': waiting_dicts,
        'avg_service_min': avg_min,
    }
