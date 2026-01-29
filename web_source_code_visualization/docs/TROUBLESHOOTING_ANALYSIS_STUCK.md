# 분석 멈춤 문제 해결 가이드

## 문제 증상
- 프론트엔드에서 "분석 중..." 메시지가 계속 표시됨
- 분석 결과가 나오지 않음
- 특히 한글 경로(`새싹` 등)를 포함한 디렉토리 분석 시 발생

## 해결된 문제들

### 1. 한글 경로 처리 개선 ✅
- 경로 정규화(`os.path.normpath`) 추가
- Unicode 인코딩 에러 핸들링 개선
- 파일 접근성 검증 추가

### 2. 에러 핸들링 강화 ✅
- 파일 읽기 실패 시 건너뛰기
- 상세한 에러 로깅
- 무한 대기 방지

### 3. 파일 접근 검증 ✅
- `os.access()` 로 읽기 권한 확인
- `os.path.isfile()` 로 파일 존재 확인
- 접근 불가능한 파일 자동 건너뛰기

## 문제 진단 방법

### 1. 진단 도구 실행
```bash
cd backend
python diagnose_directory.py
```

이 도구는 다음을 확인합니다:
- 경로 유효성
- 파일 발견
- 파서 초기화
- 심볼 스캔
- 전체 파싱
- 에러 리포트

### 2. 백엔드 서버 상태 확인
```bash
# 백엔드 서버 실행 확인
curl http://localhost:8000/api/health

# 또는
python check_backend.py
```

### 3. 개별 파일 테스트
```bash
python test_cookie_parse.py
```

## 빠른 해결 방법

### 방법 1: 백엔드 재시작
```bash
cd backend
# 기존 서버 종료 (Ctrl+C)
python main.py
```

### 방법 2: 캐시 삭제
```bash
# 캐시 삭제 API 호출
curl -X DELETE http://localhost:8000/api/cache

# 또는 프론트엔드에서 캐시 비활성화
```

### 방법 3: 스트리밍 모드 사용
프론트엔드에서:
1. "Use Streaming" 체크박스 활성화
2. 분석 시작
3. 실시간 진행상황 확인

### 방법 4: 직접 API 호출
```bash
# PowerShell
$body = @{
    path = "c:\Users\dntmd\OneDrive\Desktop\my\Project\web_source_code_visualization\plob\새싹\cookie"
    cluster = $false
    use_parallel = $false
} | ConvertTo-Json

Invoke-RestMethod -Uri "http://localhost:8000/api/analyze" `
    -Method POST `
    -ContentType "application/json" `
    -Body $body
```

## 개선된 기능

### 1. 경로 정규화
```python
# Before
with open(file_path, "r", encoding="utf-8") as f:
    content = f.read()

# After  
normalized_path = os.path.normpath(file_path)
with open(normalized_path, "r", encoding="utf-8", errors="ignore") as f:
    content = f.read()
```

### 2. 에러 핸들링
```python
# Before
except Exception as e:
    print(f"Error: {e}")

# After
except (UnicodeDecodeError, IOError, OSError) as file_err:
    print(f"[WARN] File read error: {file_path}: {file_err}")
    continue
except Exception as e:
    print(f"[ERROR] Parse error: {file_path}: {e}")
    traceback.print_exc()
```

### 3. 파일 접근성 검증
```python
# Before
for file in files:
    all_files.append(os.path.join(root, file))

# After
for file in files:
    file_path = os.path.join(root, file)
    if os.path.isfile(file_path) and os.access(file_path, os.R_OK):
        all_files.append(file_path)
```

## 로그 확인

### 백엔드 로그
```bash
# 백엔드 실행 시 콘솔 출력 확인
cd backend
python main.py

# 출력 예시:
# [WARN] File read error: ...
# [ERROR] Parse error: ...
# [INFO] Analysis complete: 2 files, 0 errors
```

### 프론트엔드 로그
브라우저 개발자 도구(F12) 콘솔에서:
- Network 탭: API 요청/응답 확인
- Console 탭: JavaScript 에러 확인

## 알려진 제한사항

1. **매우 큰 파일 (>10MB)**
   - 파싱 시간이 오래 걸릴 수 있음
   - 스트리밍 모드 사용 권장

2. **특수 문자 경로**
   - 한글, 이모지 등 포함된 경로도 이제 지원됨
   - Windows 경로 길이 제한(260자) 주의

3. **동시 분석**
   - 여러 프로젝트 동시 분석 시 리소스 부족 가능
   - 하나씩 분석 권장

## 추가 도구

### check_backend.py
백엔드 서버 상태를 확인하는 도구:
```bash
python check_backend.py
```

### test_cookie_parse.py  
특정 파일 파싱 테스트:
```bash
python test_cookie_parse.py
```

### diagnose_directory.py
디렉토리 전체 진단:
```bash
python diagnose_directory.py
```

## 문의

문제가 계속되면 다음 정보와 함께 이슈 등록:
1. 분석하려는 디렉토리 경로
2. 백엔드 로그 출력
3. 브라우저 콘솔 에러
4. `diagnose_directory.py` 실행 결과
