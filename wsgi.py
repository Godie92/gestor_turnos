import os
import time
import logging
from app import create_app

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = create_app(os.environ.get('FLASK_ENV', 'production'))

# Correr migraciones al iniciar en producción
if os.environ.get('FLASK_ENV') == 'production':
    from sqlalchemy import text, inspect
    from sqlalchemy.exc import OperationalError
    from app.extensions import db
    from flask_migrate import upgrade, stamp

    with app.app_context():
        for attempt in range(10):
            try:
                db.session.execute(text('SELECT 1'))
                log.info('DB lista.')
                break
            except OperationalError:
                log.info('Esperando DB... %d/10', attempt + 1)
                time.sleep(3)
        else:
            log.error('No se pudo conectar a la DB.')
            raise SystemExit(1)

        existing = inspect(db.engine).get_table_names()
        if not existing:
            log.info('Creando tablas...')
            db.create_all()
            stamp('head')
        else:
            log.info('Aplicando migraciones...')
            upgrade()
        log.info('DB lista para usar.')

if __name__ == '__main__':
    app.run()
