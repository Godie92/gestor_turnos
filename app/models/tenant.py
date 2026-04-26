from datetime import datetime
from app.extensions import db


class Tenant(db.Model):
    __tablename__ = 'tenants'

    id             = db.Column(db.Integer, primary_key=True)
    slug           = db.Column(db.String(60), unique=True, nullable=False, index=True)
    name           = db.Column(db.String(120), nullable=False)
    business_type  = db.Column(db.String(80), default='general')
    logo_url       = db.Column(db.String(255))
    primary_color  = db.Column(db.String(7), default='#6C63FF')
    phone_number   = db.Column(db.String(20))
    wa_phone_id    = db.Column(db.String(60))
    wa_token       = db.Column(db.Text)
    timezone       = db.Column(db.String(50), default='America/Argentina/Buenos_Aires')
    is_active      = db.Column(db.Boolean, default=True)
    created_at     = db.Column(db.DateTime, default=datetime.utcnow)

    # Email (SMTP por tenant)
    email_host     = db.Column(db.String(120))
    email_port     = db.Column(db.Integer, default=587)
    email_user     = db.Column(db.String(120))
    email_password = db.Column(db.Text)
    email_from     = db.Column(db.String(120))

    # MercadoPago (por tenant)
    mp_access_token  = db.Column(db.Text, nullable=True)

    # Membresía
    membership_status     = db.Column(db.String(20), default='trial')
    # 'trial' | 'active' | 'expired' | 'cancelled'
    membership_expires_at = db.Column(db.DateTime, nullable=True)
    mp_payment_link       = db.Column(db.String(500), nullable=True)

    staff               = db.relationship('StaffUser', back_populates='tenant', lazy='dynamic', cascade='all, delete-orphan')
    services            = db.relationship('Service', back_populates='tenant', lazy='dynamic', cascade='all, delete-orphan')
    professionals       = db.relationship('Professional', back_populates='tenant', lazy='dynamic', cascade='all, delete-orphan')
    working_hours       = db.relationship('WorkingHours', back_populates='tenant', lazy='dynamic', cascade='all, delete-orphan')
    blocked_slots       = db.relationship('BlockedSlot', back_populates='tenant', lazy='dynamic', cascade='all, delete-orphan')
    appointments        = db.relationship('Appointment', back_populates='tenant', lazy='dynamic', cascade='all, delete-orphan')
    queue_entries       = db.relationship('QueueEntry', back_populates='tenant', lazy='dynamic', cascade='all, delete-orphan')
    push_subscriptions  = db.relationship('PushSubscription', back_populates='tenant', lazy='dynamic', cascade='all, delete-orphan')

    BUSINESS_TYPES = {
        'nail_salon': 'Peluquería de Uñas',
        'hair_salon': 'Peluquería',
        'pet_groomer': 'Peluquería de Mascotas',
        'general': 'Negocio',
    }

    MEMBERSHIP_STATUSES = {
        'trial':     ('Prueba',    'badge-called'),
        'active':    ('Activa',    'badge-in_service'),
        'expired':   ('Vencida',   'badge-cancelled'),
        'cancelled': ('Cancelada', 'badge-done'),
    }

    @property
    def _mem_status(self):
        return self.membership_status or 'trial'

    @property
    def membership_label(self):
        return self.MEMBERSHIP_STATUSES.get(self._mem_status, ('—', ''))[0]

    @property
    def membership_badge(self):
        return self.MEMBERSHIP_STATUSES.get(self._mem_status, ('—', ''))[1]

    @property
    def membership_needs_payment(self):
        return self._mem_status in ('expired', 'trial')

    def __repr__(self):
        return f'<Tenant {self.slug}>'
