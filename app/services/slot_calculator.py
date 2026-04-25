"""
Calcula los horarios disponibles para reservar un turno.
"""
from datetime import datetime, date, time, timedelta

from app.models.schedule import WorkingHours, BlockedSlot
from app.models.appointment import Appointment


def get_available_slots(tenant_id: int, target_date: date,
                        duration_min: int, professional_id: int = None) -> list[dict]:
    """
    Retorna lista de dicts {"time": "10:30", "iso": "2026-04-13T10:30:00"} disponibles.
    """
    weekday = target_date.weekday()  # 0=Lunes
    wh = WorkingHours.query.filter_by(tenant_id=tenant_id, weekday=weekday).first()
    if not wh or not wh.is_open:
        return []

    # Generar todos los slots posibles
    slots = []
    current = datetime.combine(target_date, wh.open_time)
    close_dt = datetime.combine(target_date, wh.close_time)
    delta = timedelta(minutes=duration_min)

    while current + delta <= close_dt:
        slots.append(current)
        current += delta

    if not slots:
        return []

    # Cargar reservas existentes para ese día
    day_start = datetime.combine(target_date, time.min)
    day_end = datetime.combine(target_date, time.max)

    appt_query = Appointment.query.filter(
        Appointment.tenant_id == tenant_id,
        Appointment.scheduled_at >= day_start,
        Appointment.scheduled_at <= day_end,
        Appointment.status.notin_(['cancelled', 'no_show']),
    )
    if professional_id:
        appt_query = appt_query.filter_by(professional_id=professional_id)

    appointments = appt_query.all()
    occupied = []
    for appt in appointments:
        occupied.append((appt.scheduled_at,
                         appt.scheduled_at + timedelta(minutes=appt.duration_min)))

    # Cargar bloqueos
    blocked = BlockedSlot.query.filter(
        BlockedSlot.tenant_id == tenant_id,
        BlockedSlot.start_dt < day_end,
        BlockedSlot.end_dt > day_start,
    ).all()
    for b in blocked:
        occupied.append((b.start_dt, b.end_dt))

    now = datetime.now()

    available = []
    for slot_start in slots:
        slot_end = slot_start + timedelta(minutes=duration_min)

        # Filtrar slots pasados (si es hoy)
        if target_date == date.today() and slot_start <= now:
            continue

        # Verificar superposición con ocupados
        conflict = any(
            slot_start < occ_end and slot_end > occ_start
            for occ_start, occ_end in occupied
        )
        if not conflict:
            available.append({
                'time': slot_start.strftime('%H:%M'),
                'iso': slot_start.isoformat(),
            })

    return available
