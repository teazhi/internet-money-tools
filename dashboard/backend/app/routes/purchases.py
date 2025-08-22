"""
Purchase Management Routes

Handles purchase requests and management
"""

from flask import Blueprint
import logging

logger = logging.getLogger(__name__)

purchases_bp = Blueprint('purchases', __name__)


# TODO: Move purchase endpoints from main app.py here