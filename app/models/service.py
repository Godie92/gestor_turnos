from app.extensions import db

professional_services = db.Table(
    'professional_services',
    db.Column('professional_id', db.Integer, db.ForeignKey('professionals.id'), primary_key=True),
    db.Column('service_id', db.Integer, db.ForeignKey('services.id'), primary_key=True),
)


class Service(db.Model):
    __tablename__ = 'services'

    id           = db.Column(db.Integer, primary_key=True)
    tenant_id    = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    name         = db.Column(db.String(120), nullable=False)
    duration_min = db.Column(db.Integer, nullable=False, default=30)
    price        = db.Column(db.Numeric(10, 2))
    is_active    = db.Column(db.Boolean, default=True)

    tenant       = db.relationship('Tenant', back_populates='services')

    def __repr__(self):
        return f'<Service {self.name}>'


class Professional(db.Model):
    __tablename__ = 'professionals'

    id        = db.Column(db.Integer, primary_key=True)
    tenant_id = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    name      = db.Column(db.String(120), nullable=False)
    is_active = db.Column(db.Boolean, default=True)

    tenant    = db.relationship('Tenant', back_populates='professionals')
    services  = db.relationship('Service', secondary=professional_services, lazy='dynamic')

    def __repr__(self):
        return f'<Professional {self.name}>'
