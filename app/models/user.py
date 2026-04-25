from datetime import datetime
from flask_login import UserMixin
from werkzeug.security import generate_password_hash, check_password_hash
from app.extensions import db, login_manager


class StaffUser(UserMixin, db.Model):
    __tablename__ = 'staff_users'

    id            = db.Column(db.Integer, primary_key=True)
    tenant_id     = db.Column(db.Integer, db.ForeignKey('tenants.id'), nullable=False)
    email         = db.Column(db.String(120), nullable=False)
    password_hash = db.Column(db.String(255), nullable=False)
    role          = db.Column(db.String(20), default='staff')  # 'owner' | 'staff'
    is_active     = db.Column(db.Boolean, default=True)
    created_at    = db.Column(db.DateTime, default=datetime.utcnow)

    tenant        = db.relationship('Tenant', back_populates='staff')

    __table_args__ = (db.UniqueConstraint('tenant_id', 'email'),)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def is_owner(self):
        return self.role == 'owner'

    def __repr__(self):
        return f'<StaffUser {self.email}>'


@login_manager.user_loader
def load_user(user_id):
    return db.session.get(StaffUser, int(user_id))
