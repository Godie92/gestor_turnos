from datetime import datetime
from app.extensions import db


class PushSubscription(db.Model):
    __tablename__ = 'push_subscriptions'

    id         = db.Column(db.Integer, primary_key=True)
    tenant_id  = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    user_id    = db.Column(db.Integer, db.ForeignKey('staff_users.id'), nullable=False)
    endpoint   = db.Column(db.Text, nullable=False, unique=True)
    p256dh     = db.Column(db.Text, nullable=False)
    auth       = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, default=datetime.utcnow)

    tenant = db.relationship('Tenant', back_populates='push_subscriptions')
    user   = db.relationship('StaffUser')
