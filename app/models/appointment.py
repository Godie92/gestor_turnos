from datetime import datetime
from app.extensions import db


class Appointment(db.Model):
    __tablename__ = 'appointments'

    id               = db.Column(db.Integer, primary_key=True)
    tenant_id        = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    service_id       = db.Column(db.Integer, db.ForeignKey('services.id'), nullable=False)
    professional_id  = db.Column(db.Integer, db.ForeignKey('professionals.id'), nullable=True)
    client_name      = db.Column(db.String(120), nullable=False)
    client_phone     = db.Column(db.String(20), nullable=False)
    client_email     = db.Column(db.String(120))
    scheduled_at     = db.Column(db.DateTime, nullable=False)
    duration_min     = db.Column(db.Integer, nullable=False)
    status           = db.Column(db.String(20), default='confirmed')
    # confirmed | arrived | in_service | done | cancelled | no_show
    confirmation_sent  = db.Column(db.Boolean, default=False)
    reminder_sent      = db.Column(db.Boolean, default=False)
    day_reminder_sent  = db.Column(db.Boolean, default=False)
    notes            = db.Column(db.Text)
    payment_status   = db.Column(db.String(20), nullable=True)
    # None = sin cobro | 'pending' | 'paid' | 'rejected'
    created_at       = db.Column(db.DateTime, default=datetime.utcnow)

    tenant           = db.relationship('Tenant', back_populates='appointments')
    service          = db.relationship('Service')
    professional     = db.relationship('Professional')
    queue_entry      = db.relationship('QueueEntry', back_populates='appointment', uselist=False)

    STATUSES = {
        'confirmed': 'Confirmado',
        'arrived':   'Llegó',
        'in_service': 'En atención',
        'done':      'Finalizado',
        'cancelled': 'Cancelado',
        'no_show':   'No se presentó',
    }

    @property
    def status_label(self):
        return self.STATUSES.get(self.status, self.status)

    def __repr__(self):
        return f'<Appointment {self.client_name} @ {self.scheduled_at}>'
