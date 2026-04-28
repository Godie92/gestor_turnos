"""
Corre antes de gunicorn. Espera la DB y sincroniza migraciones.
"""
import os
import sys
import time
import logging
from sqlalchemy import text, inspect
from sqlalchemy.exc import OperationalError

logging.basicConfig(level=logging.INFO, format='%(message)s')
log = logging.getLogger(__name__)

os.environ.setdefault('FLASK_ENV', 'production')

from app import create_app
from app.extensions import db
from flask_migrate import upgrade, stamp

app = create_app('production')

with app.app_context():
    # 1. Esperar DB (hasta 60s)
    for attempt in range(20):
        try:
            db.session.execute(text('SELECT 1'))
            db.session.rollback()
            log.info('✓ DB conectada.')
            break
        except OperationalError:
            log.info('  Esperando DB... (%d/20)', attempt + 1)
            time.sleep(3)
    else:
        log.error('✗ No se pudo conectar a la DB. Abortando.')
        sys.exit(1)

    # 2. Detectar estado de la DB
    existing_tables = inspect(db.engine).get_table_names()

    try:
        version_row = db.session.execute(
            text('SELECT version_num FROM alembic_version LIMIT 1')
        ).fetchone()
        has_version = version_row is not None
    except Exception:
        has_version = False

    # 3. Sincronizar según el estado
    if not existing_tables:
        log.info('Base nueva — creando todas las tablas...')
        db.create_all()
        stamp('head')
        log.info('✓ Tablas creadas y migraciones marcadas.')

    elif not has_version:
        log.info('Tablas existentes sin control Alembic — sincronizando...')
        stamp('head')
        log.info('✓ Sincronizado.')

    else:
        log.info('Aplicando migraciones pendientes...')
        upgrade()
        log.info('✓ Migraciones aplicadas.')
