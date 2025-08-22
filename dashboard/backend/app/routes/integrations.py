"""
Integration Routes

Handles external service integrations
"""

from flask import Blueprint
import logging

logger = logging.getLogger(__name__)

integrations_bp = Blueprint('integrations', __name__)


# TODO: Move integration endpoints from main app.py here