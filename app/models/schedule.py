from app.extensions import db

WEEKDAY_NAMES = ['Lunes', 'Martes', 'Miércoles', 'Jueves', 'Viernes', 'Sábado', 'Domingo']


class WorkingHours(db.Model):
    """Un registro por día de la semana por tenant."""
    __tablename__ = 'working_hours'

    id         = db.Column(db.Integer, primary_key=True)
    tenant_id  = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    weekday    = db.Column(db.Integer, nullable=False)  # 0=Lunes ... 6=Domingo
    open_time  = db.Column(db.Time, nullable=False)
    close_time = db.Column(db.Time, nullable=False)
    is_open    = db.Column(db.Boolean, default=True)

    tenant     = db.relationship('Tenant', back_populates='working_hours')

    __table_args__ = (db.UniqueConstraint('tenant_id', 'weekday'),)

    @property
    def weekday_name(self):
        return WEEKDAY_NAMES[self.weekday]


class BlockedSlot(db.Model):
    """Cierres puntuales: feriados, pausas, etc."""
    __tablename__ = 'blocked_slots'

    id        = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    start_dt  = db.Column(db.DateTime, nullable=False)
    end_dt    = db.Column(db.DateTime, nullable=False)
    reason    = db.Column(db.String(120))

    tenant    = db.relationship('Tenant', back_populates='blocked_slots')
