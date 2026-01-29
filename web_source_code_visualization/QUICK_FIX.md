# 빠른 해결 방법

## 문제: 분석이 멈춰있음

**원인**: 백엔드 서버가 실행되고 있지 않거나 응답하지 않습니다.

## 해결책

### 1. 백엔드 서버 시작

#### Windows PowerShell:
```powershell
cd "c:\Users\dntmd\OneDrive\Desktop\my\Project\web_source_code_visualization\backend"
python main.py
```

#### 또는 루트 디렉토리에서:
```powershell
cd "c:\Users\dntmd\OneDrive\Desktop\my\Project\web_source_code_visualization"
.\start_dev.ps1
```

### 2. 서버가 실행되었는지 확인

다른 터미널을 열고:
```powershell
cd backend
python check_backend.py
```

다음과 같은 출력이 나와야 합니다:
```
✅ Server is running (Status: 200)
✅ Server healthy
✅ Cache operational
✅ Analysis successful
```

### 3. 프론트엔드에서 다시 시도

1. 브라우저에서 http://localhost:3000 열기
2. 경로 입력: `c:\Users\dntmd\OneDrive\Desktop\my\Project\web_source_code_visualization\plob\새싹\cookie`
3. "분석 시작" 버튼 클릭

## 자주 묻는 질문

### Q: "Address already in use" 에러가 나요
A: 이미 다른 프로세스가 8000번 포트를 사용 중입니다.
```powershell
# 8000번 포트 사용 프로세스 찾기
netstat -ano | findstr :8000

# 프로세스 종료
taskkill /PID <PID번호> /F
```

### Q: 모듈을 찾을 수 없다고 나요
A: 의존성을 설치하세요:
```powershell
cd backend
pip install -r requirements.txt
```

### Q: 프론트엔드도 실행되지 않아요
A: 프론트엔드를 시작하세요:
```powershell
cd frontend
npm install
npm run dev
```

### Q: 여전히 "분석 중..." 에서 멈춰있어요
A: 브라우저 개발자 도구(F12)를 열고 Console 탭에서 에러를 확인하세요.

## 완전한 시작 순서

### 1단계: 백엔드 시작
```powershell
# 터미널 1
cd "c:\Users\dntmd\OneDrive\Desktop\my\Project\web_source_code_visualization\backend"
python main.py
```

출력 확인:
```
INFO:     Started server process
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://127.0.0.1:8000
```

### 2단계: 프론트엔드 시작
```powershell
# 터미널 2
cd "c:\Users\dntmd\OneDrive\Desktop\my\Project\web_source_code_visualization\frontend"
npm run dev
```

출력 확인:
```
  ▲ Next.js 15.x.x
  - Local:        http://localhost:3000
  ✓ Ready in X.Xs
```

### 3단계: 브라우저에서 접속
1. http://localhost:3000 열기
2. 경로 입력
3. 분석 시작

## 진단 도구

모든 것이 정상인지 확인:
```powershell
cd backend

# 1. 백엔드 서버 상태 확인
python check_backend.py

# 2. 특정 디렉토리 진단
python diagnose_directory.py

# 3. 단일 파일 파싱 테스트
python test_cookie_parse.py
```

## 개선 사항 (v0.11.1)

이번 업데이트로 수정된 내용:
- ✅ 한글 경로 처리 개선
- ✅ 파일 접근성 검증 추가
- ✅ 에러 핸들링 강화
- ✅ 상세한 로깅 추가
- ✅ 무한 대기 방지
- ✅ 진단 도구 추가

## 지원

문제가 계속되면:
1. [docs/TROUBLESHOOTING_ANALYSIS_STUCK.md](../docs/TROUBLESHOOTING_ANALYSIS_STUCK.md) 참조
2. 백엔드 로그 저장
3. `check_backend.py` 결과 저장
4. 이슈 등록
