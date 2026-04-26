from app import create_app
from app.extensions import db
from flask_migrate import upgrade, stamp
from sqlalchemy import inspect

app = create_app('production')

with app.app_context():
    inspector = inspect(db.engine)
    existing_tables = inspector.get_table_names()

    if not existing_tables:
        # Fresh database: create all tables from models, then mark migrations as done
        db.create_all()
        stamp('head')
    else:
        # Existing database: apply any pending migrations
        upgrade()
