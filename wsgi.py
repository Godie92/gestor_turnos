import os
import time
import logging
from app import create_app

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)

app = create_app(os.environ.get('FLASK_ENV', 'production'))

if os.environ.get('FLASK_ENV') == 'production':
    from sqlalchemy import text, inspect
    from sqlalchemy.exc import OperationalError
    from app.extensions import db
    from flask_migrate import upgrade

    with app.app_context():
        # Esperar hasta 30s a que la DB esté lista
        for attempt in range(10):
            try:
                db.session.execute(text('SELECT 1'))
                db.session.rollback()
                log.info('DB lista.')
                break
            except OperationalError:
                log.info('Esperando DB... %d/10', attempt + 1)
                time.sleep(3)
        else:
            log.error('No se pudo conectar a la DB.')
            raise SystemExit(1)

        # Always run upgrade() — it handles all cases:
        # - If alembic_version exists, it applies pending migrations
        # - If tables exist but no alembic_version, it will fail gracefully
        # - If no tables exist, it creates them
        log.info('Aplicando migraciones...')
        try:
            upgrade()
            log.info('Migraciones aplicadas.')
        except Exception as e:
            log.error('Error en migraciones: %s', e)
            raise

if __name__ == '__main__':
    app.run()
