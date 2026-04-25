from datetime import datetime
from app.extensions import db


class QueueEntry(db.Model):
    """
    Representa un cliente físicamente presente en la cola del día.
    Walk-ins: appointment_id = None.
    Reservas: se crea al hacer click en "Llegó" en el admin.
    """
    __tablename__ = 'queue_entries'

    id              = db.Column(db.Integer, primary_key=True)
    tenant_id       = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    appointment_id  = db.Column(db.Integer, db.ForeignKey('appointments.id'), nullable=True)
    professional_id = db.Column(db.Integer, db.ForeignKey('professionals.id'), nullable=True)
    client_name     = db.Column(db.String(120), nullable=False)
    client_phone    = db.Column(db.String(20))
    service_name    = db.Column(db.String(120))
    position        = db.Column(db.Integer, nullable=False)
    status          = db.Column(db.String(20), default='waiting')
    # waiting | called | in_service | done | cancelled
    called_at       = db.Column(db.DateTime)
    started_at      = db.Column(db.DateTime)
    finished_at     = db.Column(db.DateTime)
    turn_notif_sent = db.Column(db.Boolean, default=False)
    created_at      = db.Column(db.DateTime, default=datetime.utcnow)

    tenant          = db.relationship('Tenant', back_populates='queue_entries')
    appointment     = db.relationship('Appointment', back_populates='queue_entry')
    professional    = db.relationship('Professional')

    STATUSES = {
        'waiting':    'Esperando',
        'called':     'Llamado',
        'in_service': 'En atención',
        'done':       'Finalizado',
        'cancelled':  'Cancelado',
    }

    @property
    def status_label(self):
        return self.STATUSES.get(self.status, self.status)

    def __repr__(self):
        return f'<QueueEntry #{self.position} {self.client_name}>'
