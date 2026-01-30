# FluxFuzzer 학습 및 테스트 규칙

## 🎯 목적

CTF 문제, 1-day 취약점 분석 보고서, Wargame 파일을 활용하여 FluxFuzzer의 탐지 능력을 학습하고 테스트합니다.

---

## 📋 워크플로우

### 1단계: 정보 분석

사용자가 제공하는 정보를 분석합니다:

| 정보 유형 | 설명 |
|-----------|------|
| 취약점 보고서 | 1-day 분석, CVE 상세 |
| 문제 파일 | 소스코드, 바이너리, 설정 |
| 풀이집 | 공격 벡터, 페이로드, PoC |
| 환경 정보 | 언어, 프레임워크, 버전 |

### 2단계: 환경 구축

> ⚠️ **원칙: 최소 코드 수정**

**바로 실행 가능한 경우:**
- Docker Compose가 있으면 → `docker-compose up`
- 실행 스크립트가 있으면 → 그대로 실행
- 코드 수정 없이 환경 변수만 설정

**환경 구축이 필요한 경우:**

1. **프론트엔드 없음** → 필요시 최소 HTML 생성
2. **Docker 없음** → Dockerfile 생성
3. **의존성 누락** → requirements.txt / package.json 생성
4. **DB 필요** → docker-compose에 DB 서비스 추가

```
smart web fuzzer/
└── test_environments/
    └── [문제명]/
        ├── original/          # 원본 파일 (수정 금지)
        ├── docker-compose.yml # 환경 구성
        ├── Dockerfile         # 필요시 생성
        ├── README.md          # 문제 설명
        └── solution.md        # 풀이집 요약
```

### 3단계: 퍼저 테스트

**테스트 절차:**

1. **환경 초기화 및 시작 (Clean Start)**
   - 기존 컨테이너 간섭을 막기 위해 강제로 재생성하여 시작합니다.
   - 컨테이너가 종료되면 자동으로 삭제되도록 관리합니다.
   ```bash
   cd test_environments/[문제명]
   docker-compose down -v  # 기존 잔여물 제거
   docker-compose up -d --force-recreate
   ```

2. **퍼저 실행**
   ```bash
   fluxfuzzer --target http://localhost:[PORT] --config fuzzer.yaml
   ```

3. **환경 정리 (Clean Up)**
   - 테스트 완료 후 컨테이너와 리소스를 즉시 삭제합니다.
   - 불필요한 리소스 점유를 방지하고 다음 테스트를 위해 초기화합니다.
   ```bash
   docker-compose down -v
   ```

4. **결과 검증**
   - 풀이집의 취약점을 탐지했는지 확인
   - 오탐/미탐 분석
   - 탐지 규칙 개선

---

## 🔧 환경 구축 가이드

### Python (Flask/Django)

```dockerfile
FROM python:3.9-slim
WORKDIR /app
COPY . .
RUN pip install -r requirements.txt
EXPOSE 5000
CMD ["python", "app.py"]
```

### Node.js (Express)

```dockerfile
FROM node:18-alpine
WORKDIR /app
COPY package*.json ./
RUN npm install
COPY . .
EXPOSE 3000
CMD ["node", "app.js"]
```

### PHP

```dockerfile
FROM php:8.0-apache
COPY . /var/www/html/
EXPOSE 80
```

### 데이터베이스 포함

```yaml
version: '3.8'
services:
  app:
    build: .
    ports:
      - "8080:8080"
    depends_on:
      - db
  db:
    image: mysql:8.0
    environment:
      MYSQL_ROOT_PASSWORD: root
      MYSQL_DATABASE: app
```

---

## 📝 풀이집 분석 템플릿

```markdown
# [문제명] 분석

## 취약점 정보
- **유형**: SQL Injection / XSS / SSRF / ...
- **위치**: /api/user?id=
- **파라미터**: id
- **CVSS**: 9.8

## 공격 벡터
1. [공격 단계 설명]
2. [페이로드 예시]

## 기대 탐지
- FluxFuzzer가 탐지해야 할 패턴
- 응답에서 확인할 지표

## 테스트 결과
- [ ] 탐지 성공
- [ ] 오탐 발생
- [ ] 미탐 (규칙 추가 필요)
```

---

## ✅ 체크리스트

**환경 구축 전:**
- [ ] 원본 파일 백업 (original/ 폴더)
- [ ] 필요한 언어/프레임워크 확인
- [ ] 의존성 파일 확인

**환경 구축 시:**
- [ ] 원본 코드 수정 최소화
- [ ] 환경 변수로 설정 분리
- [ ] 포트 충돌 확인

**테스트 시:**
- [ ] 풀이집 기반 예상 결과 정의
- [ ] 퍼저 실행 및 로그 저장
- [ ] 탐지 성공/실패 기록

---

## 🚫 금지 사항

1. **원본 취약점 코드 수정 금지** - 취약점을 그대로 유지
2. **보안 패치 적용 금지** - 테스트 목적이므로 취약한 상태 유지
3. **외부 서버 연결 금지** - 로컬 환경에서만 테스트
4. **민감 정보 커밋 금지** - API 키, 비밀번호 등

---

## 📊 결과 기록

| 날짜 | 문제명 | 취약점 | 탐지 여부 | 비고 |
|------|--------|--------|----------|------|
| YYYY-MM-DD | [문제명] | SQLi | ✅/❌ | 메모 |

---

*이 규칙은 FluxFuzzer 학습 및 테스트 시 에이전트가 자동으로 참조합니다.*
