from flask import Blueprint
from app.extensions import csrf

api_bp = Blueprint('api', __name__, url_prefix='/api/v1')
csrf.exempt(api_bp)

from . import routes  # noqa
