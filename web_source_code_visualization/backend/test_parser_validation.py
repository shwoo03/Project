"""파서 정확도 테스트 - Parser Validation Tests"""
import os
import sys

# UTF-8 인코딩 설정
os.environ['PYTHONUTF8'] = '1'
os.environ['PYTHONIOENCODING'] = 'utf-8'

from core.parser.python import PythonParser


def test_chained_method_call():
    """체이닝된 메서드 호출에서 잘못된 입력 감지 방지"""
    code = '''
from flask import Flask, request
app = Flask(__name__)

@app.route('/upload', methods=['POST'])
def upload():
    content = request.form.get('content').encode('utf-8')
    filename = request.form.get('filename').strip()
    return "OK"
'''
    parser = PythonParser()
    endpoints = parser.parse("test.py", code)
    
    all_inputs = []
    for ep in endpoints:
        for child in ep.children:
            if child.type == 'input':
                all_inputs.append(child.path)
    
    # 올바른 입력만 감지되어야 함
    errors = []
    if 'content' not in all_inputs:
        errors.append("content 입력이 감지되어야 함")
    if 'filename' not in all_inputs:
        errors.append("filename 입력이 감지되어야 함")
    if 'utf-8' in all_inputs:
        errors.append("utf-8은 입력이 아님 (오탐)")
    
    unexpected = [x for x in all_inputs if x not in ['content', 'filename']]
    if unexpected:
        errors.append(f"예상치 못한 입력: {unexpected}")
    
    if errors:
        print("❌ 체이닝 메서드 테스트 실패:")
        for e in errors:
            print(f"   - {e}")
        return False
    
    print("✅ 체이닝 메서드 테스트 통과")
    print(f"   감지된 입력: {all_inputs}")
    return True


def test_source_type_classification():
    """소스 유형 분류 정확도"""
    code = '''
from flask import Flask, request
app = Flask(__name__)

@app.route('/test')
def test():
    get_param = request.args.get('query')
    post_param = request.form.get('data')
    cookie = request.cookies.get('session')
    header = request.headers.get('X-Token')
    return "OK"
'''
    parser = PythonParser()
    endpoints = parser.parse("test.py", code)
    
    source_map = {}
    for ep in endpoints:
        for child in ep.children:
            if child.type == 'input':
                source_map[child.path] = child.method
    
    errors = []
    expected = {
        'query': 'GET',
        'data': 'POST',
        'session': 'COOKIE',
        'X-Token': 'HEADER'
    }
    
    for param, expected_source in expected.items():
        actual = source_map.get(param)
        if actual != expected_source:
            errors.append(f"{param}: 기대 {expected_source}, 실제 {actual}")
    
    if errors:
        print("❌ 소스 유형 분류 테스트 실패:")
        for e in errors:
            print(f"   - {e}")
        return False
    
    print("✅ 소스 유형 분류 테스트 통과")
    print(f"   소스 맵: {source_map}")
    return True


def test_file_download_sample():
    """실제 샘플 파일 테스트 (plob/새싹/file-download-1)"""
    sample_path = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        'plob', '새싹', 'file-download-1', 'app.py'
    )
    
    if not os.path.exists(sample_path):
        print(f"⚠️ 샘플 파일 없음: {sample_path}")
        return None
    
    with open(sample_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    parser = PythonParser()
    endpoints = parser.parse(sample_path, content)
    
    all_inputs = []
    for ep in endpoints:
        for child in ep.children:
            if child.type == 'input':
                all_inputs.append(child.path)
    
    errors = []
    # 알려진 올바른 입력
    valid_inputs = ['filename', 'content', 'name']
    # 잘못된 입력 (오탐)
    invalid_inputs = ['utf-8', 'utf8', 'strict', 'ignore']
    
    for invalid in invalid_inputs:
        if invalid in all_inputs:
            errors.append(f"오탐: '{invalid}'이 입력으로 감지됨")
    
    if errors:
        print("❌ file-download-1 샘플 테스트 실패:")
        for e in errors:
            print(f"   - {e}")
        return False
    
    print("✅ file-download-1 샘플 테스트 통과")
    print(f"   감지된 입력: {all_inputs}")
    return True


if __name__ == "__main__":
    print("=" * 50)
    print("파서 검증 테스트 (Parser Validation Tests)")
    print("=" * 50)
    print()
    
    results = []
    
    results.append(("체이닝 메서드", test_chained_method_call()))
    print()
    
    results.append(("소스 유형 분류", test_source_type_classification()))
    print()
    
    result = test_file_download_sample()
    if result is not None:
        results.append(("file-download-1 샘플", result))
    print()
    
    print("=" * 50)
    print("테스트 결과 요약")
    print("=" * 50)
    
    passed = sum(1 for _, r in results if r)
    total = len(results)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status} - {name}")
    
    print()
    if passed == total:
        print(f"🎉 모든 테스트 통과! ({passed}/{total})")
        sys.exit(0)
    else:
        print(f"⚠️ 일부 테스트 실패 ({passed}/{total})")
        sys.exit(1)
