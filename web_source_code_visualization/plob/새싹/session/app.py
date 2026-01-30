from flask import Flask, request, render_template, make_response
import os

app = Flask(__name__)

# 세션 저장소
session_storage = {}

@app.route('/')
def index():
    session_id = request.cookies.get('sessionid', None)
    if session_id in session_storage:
        return f'Hello, {session_storage[session_id]}'
    return 'Hello, Guest'

@app.route('/login', methods=['GET'])
def login():
    # 취약점: 세션 ID 생성 시 엔트로피 부족 (1바이트 = 256가지 경우의 수)
    session_id = os.urandom(1).hex()
    session_storage[session_id] = 'admin'
    
    resp = make_response('Logged in as admin')
    resp.set_cookie('sessionid', session_id)
    return resp

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
