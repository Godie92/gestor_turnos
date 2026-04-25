import os
from flask import Flask
from dotenv import load_dotenv

load_dotenv()

from app.config import config
from app.extensions import db, migrate, login_manager, csrf, limiter


def create_app(config_name=None):
    if config_name is None:
        config_name = os.environ.get('FLASK_ENV', 'default')

    app = Flask(__name__, static_folder='static', template_folder='templates')
    app.config.from_object(config[config_name])

    # Extensions
    db.init_app(app)
    migrate.init_app(app, db)
    login_manager.init_app(app)
    csrf.init_app(app)
    limiter.init_app(app)

    # Import models so Flask-Migrate detects them
    from app.models import (  # noqa
        Tenant, StaffUser, Service, Professional,
        WorkingHours, BlockedSlot, Appointment, QueueEntry,
    )
    from app.models.push_subscription import PushSubscription  # noqa

    # Blueprints
    from app.blueprints.auth import auth_bp
    from app.blueprints.public import public_bp
    from app.blueprints.display import display_bp
    from app.blueprints.admin import admin_bp
    from app.blueprints.api import api_bp
    from app.blueprints.platform import platform_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(public_bp)
    app.register_blueprint(display_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(platform_bp)

    # Root redirect
    @app.route('/')
    def index():
        from flask import redirect, url_for
        return redirect(url_for('auth.login'))

    # Health check
    @app.route('/health')
    def health():
        return {'status': 'ok'}

    # Service Worker desde raíz
    @app.route('/sw.js')
    def service_worker():
        from flask import send_from_directory
        return send_from_directory(app.static_folder, 'sw.js',
                                   mimetype='application/javascript')

    # Error handlers
    @app.errorhandler(403)
    def forbidden(e):
        from flask import render_template
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        from flask import render_template
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        from flask import render_template
        return render_template('errors/500.html'), 500

    @app.errorhandler(429)
    def too_many_requests(e):
        from flask import render_template
        return render_template('errors/429.html'), 429

    # Scheduler (solo en producción o si está explícitamente habilitado)
    if not app.debug or os.environ.get('ENABLE_SCHEDULER'):
        from app.services.scheduler import init_scheduler
        init_scheduler(app)

    return app
