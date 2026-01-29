import os
import re
import subprocess
from flask import Flask, render_template, request, jsonify

app = Flask(__name__)
app.secret_key = os.urandom(32)

FILTERED_CHARS = [' ', ';', '|', '&', '>', '<', '(', ')', '[', ']', '{', '}', '\n', '\r']

def is_valid_ip(ip):
    ip_pattern = r'^(\d{1,3}\.){3}\d{1,3}$'
    return bool(re.match(ip_pattern, ip))

def filter_input(user_input):
    for char in FILTERED_CHARS:
        if char in user_input:
            return False, f"Invalid character detected: {char}"
    return True, "OK"

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/ping', methods=['POST'])
def ping():
    ip = request.form.get('ip', '').strip()
    
    if not ip:
        return jsonify({'error': 'IP address is required'}), 400
    
    is_valid, message = filter_input(ip)
    if not is_valid:
        return jsonify({'error': message}), 400
    
    try:
        cmd = f"ping -c 4 {ip}"
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True, timeout=10)
        
        return jsonify({
            'command': cmd,
            'stdout': result.stdout,
            'stderr': result.stderr,
            'returncode': result.returncode
        })
    
    except subprocess.TimeoutExpired:
        return jsonify({'error': 'Command timed out'}), 500
    except Exception as e:
        return jsonify({'error': str(e)}), 500


if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000, debug=False)