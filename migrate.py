import time
import logging
from app import create_app
from app.extensions import db
from flask_migrate import upgrade, stamp
from sqlalchemy import inspect, text
from sqlalchemy.exc import OperationalError

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = create_app('production')

with app.app_context():
    # Esperar a que la DB esté lista (hasta 30s)
    for attempt in range(10):
        try:
            db.session.execute(text('SELECT 1'))
            log.info('Base de datos lista.')
            break
        except OperationalError:
            log.info('Esperando base de datos... intento %d/10', attempt + 1)
            time.sleep(3)
    else:
        log.error('No se pudo conectar a la base de datos.')
        raise SystemExit(1)

    inspector = inspect(db.engine)
    existing_tables = inspector.get_table_names()

    if not existing_tables:
        log.info('Base nueva — creando tablas...')
        db.create_all()
        stamp('head')
        log.info('Tablas creadas.')
    else:
        log.info('Base existente — aplicando migraciones...')
        upgrade()
        log.info('Migraciones aplicadas.')
