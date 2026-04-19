#!/usr/bin/env python3
"""
Server-side authentication for Master Data write routes.

Phase 2 SSOT migration (2026-04-19):
  Adds a session-cookie-based auth gate so POST/PUT/DELETE on /api/<entity>
  require a logged-in admin. The client-side JS password (DASHBOARD_PASSWORD)
  remains for the read-only dashboard viewer; this module protects the API.

Usage in db_dashboard.py:
    from auth import require_admin, setup_auth
    setup_auth(app)           # registers /api/auth/* routes + secret key

    @app.route('/api/<entity>', methods=['POST'])
    @require_admin
    def api_create(entity): ...
"""

from __future__ import annotations

import logging
import os
from functools import wraps

from flask import Flask, request, session, jsonify

log = logging.getLogger(__name__)

# Admin password — override via env var for prod
MD_ADMIN_PASSWORD = os.environ.get('MD_ADMIN_PASSWORD', 'raito2026')


def require_admin(f):
    """Decorator: reject requests without a valid admin session."""
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('md_admin'):
            return jsonify({'error': 'Authentication required. POST to /api/auth/login first.'}), 401
        return f(*args, **kwargs)
    return decorated


def setup_auth(app: Flask) -> None:
    """Register auth routes and configure Flask secret key."""
    # Secret key for signing session cookies
    app.secret_key = os.environ.get(
        'FLASK_SECRET_KEY',
        'raito-dev-secret-change-in-prod'
    )

    @app.route('/api/auth/login', methods=['POST'])
    def auth_login():
        """Authenticate with the admin password. Sets a session cookie."""
        data = request.get_json(force=True) or {}
        password = data.get('password', '')
        if password == MD_ADMIN_PASSWORD:
            session['md_admin'] = True
            session['md_user'] = data.get('user', 'anonymous')
            log.info("Admin login: %s", session['md_user'])
            return jsonify({'status': 'ok', 'user': session['md_user']})
        log.warning("Failed admin login attempt")
        return jsonify({'error': 'Invalid password'}), 403

    @app.route('/api/auth/logout', methods=['POST'])
    def auth_logout():
        """Clear the admin session."""
        session.pop('md_admin', None)
        session.pop('md_user', None)
        return jsonify({'status': 'ok'})

    @app.route('/api/auth/status', methods=['GET'])
    def auth_status():
        """Check if the current session is authenticated."""
        return jsonify({
            'authenticated': bool(session.get('md_admin')),
            'user': session.get('md_user', ''),
        })
