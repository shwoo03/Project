#!/usr/bin/python3
from flask import Flask, request, render_template, g
import sqlite3
import os

app = Flask(__name__)
app.secret_key = os.urandom(32)

try:
    FLAG = open('./flag.txt', 'r').read()
except:
    FLAG = '[**FLAG**]'

DATABASE = "users.db"

def get_db():
    db = getattr(g, '_database', None)
    if db is None:
        db = g._database = sqlite3.connect(DATABASE)
    return db

@app.teardown_appcontext
def close_connection(exception):
    db = getattr(g, '_database', None)
    if db is not None:
        db.close()

def query_db(query, one=True):
    cur = get_db().execute(query)
    rv = cur.fetchall()
    cur.close()
    return (rv[0] if rv else None) if one else rv

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'GET':
        return render_template('login.html')
    else:
        userid = request.form.get('userid')
        userpassword = request.form.get('userpassword')
        # Vulnerability: F-string injection directly into SQL query
        res = query_db(f'select * from users where userid="{userid}" and userpassword="{userpassword}"')
        if res:
            db_userid = res[0]
            if db_userid == 'admin':
                return f'hello {db_userid} flag is {FLAG}'
            return f'<script>alert("hello {db_userid}");history.go(-1);</script>'
        return '<script>alert("wrong");history.go(-1);</script>'

def init_db():
    with app.app_context():
        db = get_db()
        db.execute('CREATE TABLE IF NOT EXISTS users (userid TEXT, userpassword TEXT)')
        db.execute('INSERT INTO users (userid, userpassword) VALUES ("admin", "secret_admin_pw")')
        db.execute('INSERT INTO users (userid, userpassword) VALUES ("guest", "guest")')
        db.commit()

if __name__ == '__main__':
    if not os.path.exists(DATABASE):
        init_db()
    app.run(host='0.0.0.0', port=8000)
