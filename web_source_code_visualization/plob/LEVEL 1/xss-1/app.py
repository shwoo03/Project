#!/usr/bin/python3
from flask import Flask, request, render_template, make_response

app = Flask(__name__)

try:
    FLAG = open('./flag.txt', 'r').read()
except:
    FLAG = '[**FLAG**]'

def check_xss(param, cookie={"name": "name", "value": "value"}):
    # This is a dummy implementation of the check_xss function found in Dreamhack challenges
    # In a real environment, this might simulate a bot visiting the page
    return False 

@app.route("/")
def index():
    return render_template("index.html")

@app.route("/vuln")
def vuln():
    # 취약한 페이지임
    # param 변수에 입력값을 받고 return 함 
    param = request.args.get("param", "")
    return param

@app.route("/flag", methods=["GET", "POST"])
def flag():
    if request.method == "GET":
        return render_template("flag.html")
    # POST 방식일 때 flag를 확인하는 코드
    elif request.method == "POST":
        # param이라는 이름으로 전달된 값을 받아옴
        param = request.form.get("param")
        # 쿠키 값의 value 로 flag를 전달함 
        if not check_xss(param, {"name": "flag", "value": FLAG.strip()}):
            return '<script>alert("wrong??");history.go(-1);</script>'

        return '<script>alert("good");history.go(-1);</script>'

@app.route("/memo")
def memo():
    global memo_text
    text = request.args.get("memo", "")
    memo_text += text + "\n"
    return render_template("memo.html", memo=memo_text)

memo_text = ""

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000)
