#!/usr/bin/env python3
"""
Minimal Flask app for Railway deployment testing
"""
import os
from flask import Flask, jsonify
from datetime import datetime

# Create Flask app
app = Flask(__name__)

@app.route('/', methods=['GET'])
def root():
    return jsonify({
        'message': 'Internet Money Tools Backend API - Minimal Version',
        'status': 'running',
        'timestamp': datetime.utcnow().isoformat()
    })

@app.route('/health', methods=['GET'])
def health():
    return {'status': 'ok', 'timestamp': datetime.utcnow().isoformat()}

@app.route('/ping', methods=['GET'])
def ping():
    return 'pong'

@app.route('/status', methods=['GET'])
def status():
    return 'OK'

if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print(f"Starting minimal Flask app on port {port}")
    app.run(host='0.0.0.0', port=port, debug=False)