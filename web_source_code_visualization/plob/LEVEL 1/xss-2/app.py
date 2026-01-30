#!/usr/bin/python3
from flask import Flask, request, render_template

app = Flask(__name__)

try:
    FLAG = open('./flag.txt', 'r').read()
except:
    FLAG = '[**FLAG**]'

@app.route('/')
def index():
    return render_template('index.html')

@app.route('/vuln')
def vuln():
    return render_template('vuln.html')

@app.route('/flag', methods=['GET', 'POST'])
def flag():
    if request.method == 'GET':
        return render_template('flag.html')
    elif request.method == 'POST':
        param = request.form.get('param')
        return '<script>alert("bot passed");</script>'

@app.route('/memo')
def memo():
    text = request.args.get('memo', '')
    return text

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8000)
