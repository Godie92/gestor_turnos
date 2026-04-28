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
    from flask_migrate import upgrade, stamp

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

        # Verificar si alembic_version ya tiene registros
        try:
            version = db.session.execute(
                text('SELECT version_num FROM alembic_version LIMIT 1')
            ).fetchone()
            has_version = version is not None
        except Exception:
            has_version = False

        existing_tables = inspect(db.engine).get_table_names()

        if has_version:
            # DB rastreada por Alembic — aplicar migraciones pendientes
            log.info('Aplicando migraciones pendientes...')
            upgrade()
            log.info('Migraciones aplicadas.')
        elif existing_tables:
            # Tablas existen pero sin rastreo Alembic — marcar como al día
            log.info('Tablas existentes sin versión Alembic — marcando como head...')
            stamp('head')
            log.info('Listo.')
        else:
            # Base totalmente nueva
            log.info('Base nueva — creando tablas...')
            db.create_all()
            stamp('head')
            log.info('Tablas creadas.')

if __name__ == '__main__':
    app.run()
