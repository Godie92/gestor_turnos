"""
Script para crear tenants, usuarios y datos iniciales.

Uso básico:
  python seed.py                          # crea tenant de ejemplo
  python seed.py --superadmin             # crea el admin de plataforma
  python seed.py --demo                   # crea el tenant demo
  python seed.py --slug mi-negocio --name "Mi Negocio" --email admin@mi.com --password secreta

Opciones:
  --slug          slug del negocio  (default: mi-negocio)
  --name          nombre visible    (default: Mi Negocio)
  --email         email del admin   (default: admin@example.com)
  --password      contraseña        (default: admin123)
  --type          tipo de negocio   (default: Peluquería)
  --superadmin    crea el superadmin de plataforma
  --demo          crea el tenant demo
"""
import argparse
from datetime import time

from app import create_app
from app.extensions import db
from app.models.tenant import Tenant
from app.models.user import StaffUser
from app.models.service import Service
from app.models.schedule import WorkingHours


def _default_hours(tenant_id):
    for weekday in range(5):
        db.session.add(WorkingHours(
            tenant_id=tenant_id, weekday=weekday,
            open_time=time(9, 0), close_time=time(18, 0), is_open=True,
        ))
    db.session.add(WorkingHours(
        tenant_id=tenant_id, weekday=5,
        open_time=time(9, 0), close_time=time(13, 0), is_open=True,
    ))
    db.session.add(WorkingHours(
        tenant_id=tenant_id, weekday=6,
        open_time=time(9, 0), close_time=time(18, 0), is_open=False,
    ))


def create_superadmin(email, password):
    """Crea el usuario superadmin de plataforma (sin tenant)."""
    # El superadmin necesita un tenant placeholder — usamos uno especial
    platform = Tenant.query.filter_by(slug='__platform__').first()
    if not platform:
        platform = Tenant(slug='__platform__', name='Plataforma', is_active=False)
        db.session.add(platform)
        db.session.flush()

    existing = StaffUser.query.filter_by(email=email).first()
    if existing:
        print(f'[--] Superadmin "{email}" ya existe.')
        return

    user = StaffUser(tenant_id=platform.id, email=email, role='superadmin')
    user.set_password(password)
    db.session.add(user)
    db.session.commit()
    print(f'[OK] Superadmin "{email}" creado.')
    print(f'     Accedé en: http://localhost:5000/login')


def create_demo():
    """Crea el tenant demo con datos de ejemplo."""
    tenant = Tenant.query.filter_by(slug='demo').first()
    if not tenant:
        tenant = Tenant(
            slug='demo',
            name='Demo — Peluquería',
            business_type='Peluquería',
            primary_color='#6C63FF',
        )
        db.session.add(tenant)
        db.session.flush()
        print('[OK] Tenant demo creado.')
    else:
        print('[--] Tenant demo ya existe.')

    if StaffUser.query.filter_by(tenant_id=tenant.id).count() == 0:
        user = StaffUser(tenant_id=tenant.id, email='demo@demo.com', role='owner')
        user.set_password('demo123')
        db.session.add(user)
        print('[OK] Usuario demo@demo.com creado.')

    if Service.query.filter_by(tenant_id=tenant.id).count() == 0:
        for name, duration, price in [
            ('Corte de cabello', 30, 3500),
            ('Coloración', 90, 8000),
            ('Mechas', 120, 12000),
            ('Peinado', 45, 4500),
        ]:
            db.session.add(Service(tenant_id=tenant.id, name=name,
                                   duration_min=duration, price=price))
        print('[OK] Servicios demo creados.')

    if WorkingHours.query.filter_by(tenant_id=tenant.id).count() == 0:
        _default_hours(tenant.id)
        print('[OK] Horarios demo creados.')

    db.session.commit()
    print(f'     Demo disponible en: http://localhost:5000/demo-login')


def seed(slug, name, email, password, business_type):
    tenant = Tenant.query.filter_by(slug=slug).first()
    if not tenant:
        tenant = Tenant(
            slug=slug, name=name,
            business_type=business_type,
            primary_color='#6C63FF',
        )
        db.session.add(tenant)
        db.session.flush()
        print(f'[OK] Tenant "{name}" creado con slug "{slug}"')
    else:
        print(f'[--] Tenant "{slug}" ya existe, omitiendo.')

    existing = StaffUser.query.filter_by(tenant_id=tenant.id, email=email).first()
    if not existing:
        user = StaffUser(tenant_id=tenant.id, email=email, role='owner')
        user.set_password(password)
        db.session.add(user)
        print(f'[OK] Usuario "{email}" creado.')
    else:
        print(f'[--] Usuario "{email}" ya existe, omitiendo.')

    if Service.query.filter_by(tenant_id=tenant.id).count() == 0:
        for svc_name, duration, price in [
            ('Manicura', 30, 3500),
            ('Pedicura', 45, 4500),
            ('Manicura + Pedicura', 75, 7500),
        ]:
            db.session.add(Service(tenant_id=tenant.id, name=svc_name,
                                   duration_min=duration, price=price))
        print('[OK] Servicios de ejemplo creados.')

    if WorkingHours.query.filter_by(tenant_id=tenant.id).count() == 0:
        _default_hours(tenant.id)
        print('[OK] Horarios de ejemplo creados.')

    db.session.commit()
    print(f'\nListo! Accede al admin en: http://localhost:5000/{slug}/admin/')
    print(f'   Email: {email}')
    print(f'   Contraseña: {password}')


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument('--slug', default='mi-negocio')
    parser.add_argument('--name', default='Mi Negocio')
    parser.add_argument('--email', default='admin@example.com')
    parser.add_argument('--password', default='admin123')
    parser.add_argument('--type', dest='business_type', default='Peluquería')
    parser.add_argument('--superadmin', action='store_true',
                        help='Crear superadmin de plataforma')
    parser.add_argument('--superadmin-email', default='superadmin@platform.com')
    parser.add_argument('--superadmin-password', default='super123')
    parser.add_argument('--demo', action='store_true',
                        help='Crear tenant demo')
    args = parser.parse_args()

    app = create_app('development')
    with app.app_context():
        db.create_all()

        if args.superadmin:
            create_superadmin(args.superadmin_email, args.superadmin_password)
        elif args.demo:
            create_demo()
        else:
            seed(args.slug, args.name, args.email, args.password, args.business_type)
