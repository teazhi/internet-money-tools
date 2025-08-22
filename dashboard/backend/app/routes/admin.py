"""
Admin Routes

Handles administrative functions
"""

from flask import Blueprint
import logging

logger = logging.getLogger(__name__)

admin_bp = Blueprint('admin', __name__)


# TODO: Move admin endpoints from main app.py here