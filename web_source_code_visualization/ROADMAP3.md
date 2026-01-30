# 🚀 로드맵 3.0: 차세대 코드 보안 분석 플랫폼

> **비전**: 차세대 AI 기반 보안 분석 플랫폼 - 엔터프라이즈급 정확도와 개발자 친화적 경험의 결합

**최종 수정**: 2026-01-30  
**현재 버전**: 0.14.0  
**목표**: 엔터프라이즈급 보안 분석 플랫폼

---

## 📋 목차

1. [프로젝트 개요](#-프로젝트-개요)
2. [현재 상태 평가](#-현재-상태-평가)
3. [구현 완료 기능 (v0.14.0)](#-구현-완료-기능-v0140)
4. [개선 필요 사항](#-개선-필요-사항)
5. [취약점 탐지 강화 전략](#-취약점-탐지-강화-전략)
6. [업계 트렌드 및 벤치마크](#-업계-트렌드-및-벤치마크)
7. [향후 개발 로드맵](#-향후-개발-로드맵)
8. [기술 부채 및 리팩토링](#-기술-부채-및-리팩토링)

---

## 🎯 프로젝트 개요

### 핵심 목표
웹 애플리케이션의 **소스 코드 보안 취약점**을 시각화하고 분석하는 차세대 SAST(Static Application Security Testing) 플랫폼

### 지원 언어 및 프레임워크
| 언어 | 프레임워크 | 분석 수준 |
|------|-----------|----------|
| **Python** | Flask, FastAPI, Django | ⭐⭐⭐⭐⭐ |
| **JavaScript** | Express.js, React, DOM | ⭐⭐⭐⭐ |
| **TypeScript** | Next.js, React, Express | ⭐⭐⭐⭐ |
| **PHP** | Laravel, Symfony | ⭐⭐⭐ |
| **Java** | Spring Boot, Servlet | ⭐⭐⭐ |
| **Go** | Gin, net/http | ⭐⭐⭐ |

### 기술 스택
- **Backend**: FastAPI + Python 3.11+ + Tree-sitter + Celery + Redis
- **Frontend**: Next.js 16 + React 19 + ReactFlow + TailwindCSS
- **AI/ML**: Groq LLM API + Custom ML Models
- **Caching**: SQLite + Redis (Distributed)

---

## 📊 현재 상태 평가

### ✅ 강점

1. **다중 언어 SAST 엔진**
   - 6개 언어 지원 (Python, JS/TS, PHP, Java, Go)
   - Tree-sitter 기반 정확한 파싱
   - 언어별 프레임워크 인식

2. **Advanced Data-Flow Analysis**
   - Inter-procedural Taint Analysis (함수 간 데이터 흐름)
   - CFG/PDG 기반 정밀 분석
   - Path-sensitive & Context-sensitive 분석

3. **AI-Powered Analysis**
   - LLM 기반 비즈니스 로직 취약점 탐지
   - ML 기반 False Positive 필터링 (15% 이하 달성)
   - 지능형 수정 제안 생성

4. **Enterprise Scalability**
   - 분산 분석 아키텍처 (10,000+ 파일)
   - Redis 캐싱 + 워크로드 밸런싱
   - 스트리밍 API (실시간 진행 상황)

5. **시각화 (Visualization)**
   - ReactFlow 기반 대화형 Call Graph
   - Taint Flow 경로 애니메이션
   - Backtrace 하이라이팅

### ⚠️ 약점

1. **탐지 정확도**
   - 일부 복잡한 패턴 미탐지
   - Framework-specific 패턴 커버리지 제한
   - Dynamic Code 분석 한계 (eval, reflection)

2. **개발자 경험**
   - IDE 통합 미흡 (VS Code Extension 미개발)
   - CI/CD 파이프라인 통합 미완료
   - CLI 도구 미개발

3. **리포팅**
   - SARIF 형식 지원 부재
   - PDF/HTML 보고서 생성 미구현
   - 컴플라이언스 매핑 미지원 (CWE, OWASP)

4. **보안 규칙**
   - Custom Rule 작성 UI 없음
   - Semgrep 규칙 통합만 지원
   - 언어별 규칙 불균형

---

## ✅ 구현 완료 기능 (v0.14.0)

### 4단계: AI 기반 정밀 분석

#### 4.1 머신러닝 기반 취약점 탐지 ✅
```
backend/core/
├── ml_feature_extractor.py     # Feature Extraction (~550 LOC)
├── ml_vulnerability_detector.py # ML Classifier (~600 LOC)
└── ml_false_positive_filter.py  # FP Filter (~450 LOC)
```
- **성과**: False Positive Rate 15% 이하 달성
- **테스트**: 20+ test cases

#### 4.2 LLM 통합 보안 분석 ✅
```
backend/core/llm_security_analyzer.py (~750 LOC)
├── BusinessLogicAnalyzer       # IDOR, 경쟁 상태
├── AuthenticationAnalyzer      # JWT, OAuth, 세션
├── APISecurityAnalyzer         # GraphQL, 속도 제한
└── IntelligentRemediator       # 수정 제안 생성
```
- **API**: Groq LLM (Llama 3.3 70B)
- **테스트**: 20+ test cases

#### 4.3 고급 데이터 흐름 분석 ✅
```
backend/core/
├── cfg_builder.py              # 제어 흐름 그래프 (~900 LOC)
├── pdg_generator.py            # 프로그램 의존성 그래프 (~700 LOC)
└── advanced_dataflow_analyzer.py # 경로 민감 분석 (~800 LOC)
```
- **기능**: CFG/PDG 생성, 프로그램 슬라이싱, 기호 실행
- **테스트**: 50개 이상 테스트 케이스

### 7단계: 성능 및 확장성

#### 7.1 분산 분석 아키텍처 ✅
```
backend/core/distributed_analyzer.py (~1100 LOC)
├── RedisCache                  # 분산 캐싱 시스템
├── WorkloadBalancer            # 워크로드 분배 전략
├── DistributedAnalyzer         # 대규모 분석 엔진
└── ClusterOrchestrator         # 클러스터 관리
```
- **성능**: 10,000개 이상 파일 분석 지원
- **테스트**: 25개 이상 테스트 케이스

---

## 🔧 개선 필요 사항

### 1. 탐지 정확도 향상

| 영역 | 현재 | 목표 | 우선순위 |
|------|------|------|----------|
| SQL Injection | 85% | 95% | 🔴 높음 |
| XSS | 80% | 95% | 🔴 높음 |
| SSRF | 70% | 90% | 🟡 중간 |
| Deserialization | 60% | 85% | 🟡 중간 |
| Path Traversal | 75% | 90% | 🟡 중간 |
| SSTI | 65% | 85% | 🟢 낮음 |

### 2. 프레임워크별 규칙 확대

```yaml
Python:
  - Django ORM: N+1 쿼리, Mass Assignment
  - FastAPI: Dependency Injection 취약점
  - Flask: Secret Key 하드코딩

JavaScript:
  - React: dangerouslySetInnerHTML, XSS
  - Express: Header Injection, NoSQL Injection
  - Next.js: SSR 데이터 노출

Java:
  - Spring Security: 인증/인가 우회
  - JPA/Hibernate: JPQL Injection
  - Servlet: Session Fixation

PHP:
  - Laravel: Mass Assignment, Blade XSS
  - Symfony: YAML Injection
```

### 3. Dynamic Code 분석 개선

```python
# 현재 한계
eval(user_input)           # 탐지됨 ✅
exec(compile(code, ...))   # 탐지 안됨 ❌
getattr(obj, user_input)   # 부분 탐지 ⚠️
importlib.import_module()  # 미탐지 ❌
```

### 4. 성능 최적화

| 메트릭 | 현재 | 목표 |
|--------|------|------|
| 1,000 파일 분석 시간 | 45초 | 15초 |
| 10,000 파일 분석 시간 | 8분 | 2분 |
| 메모리 사용량 (10K 파일) | 4GB | 2GB |
| 캐시 히트율 | 70% | 90% |

---

## 🎯 취약점 탐지 강화 전략

### OWASP Top 10 2025 기반 분석 강화

**📌 OWASP Top 10 2025 목록**:
1. **A01 - Broken Access Control** 🔴
2. **A02 - Security Misconfiguration** 🔴
3. **A03 - Software Supply Chain Failures** (NEW) 🔴
4. **A04 - Cryptographic Failures** 🟡
5. **A05 - Injection** 🟡
6. **A06 - Insecure Design** 🟡
7. **A07 - Authentication Failures** 🟡
8. **A08 - Software or Data Integrity Failures** 🟢
9. **A09 - Security Logging and Alerting Failures** 🟢
10. **A10 - Mishandling of Exceptional Conditions** (NEW) 🟢

### 1. Broken Access Control 탐지 강화 🔴

```python
# 탐지 패턴 확대
class AccessControlAnalyzer:
    patterns = [
        "missing_authorization_check",      # 인가 누락
        "horizontal_privilege_escalation",  # IDOR
        "vertical_privilege_escalation",    # 권한 상승
        "insecure_direct_object_reference", # 직접 객체 참조
        "path_traversal_authorization",     # 경로 기반 우회
        "cors_misconfiguration",            # CORS 설정 오류
        "jwt_missing_verification",         # JWT 검증 누락
        "role_based_access_bypass",         # RBAC 우회
    ]
```

### 2. Software Supply Chain Security 강화 🔴

```yaml
Supply Chain Analysis:
  Dependency Scanning:
    - package.json / requirements.txt / pom.xml 분석
    - 알려진 취약점 (CVE) 매칭
    - 버전 범위 분석 (semver)
    - 라이선스 컴플라이언스
    
  SBOM Generation:
    - CycloneDX 형식 지원
    - SPDX 형식 지원
    - Dependency Graph 시각화
    
  Malicious Package Detection:
    - 타이포스쿼팅 탐지
    - Install hook 분석
    - 의심스러운 네트워크 호출
```

### 3. 정밀 Taint Analysis 전략

```
┌─────────────────────────────────────────────────────┐
│                  Taint Analysis Flow                 │
├─────────────────────────────────────────────────────┤
│                                                     │
│   Sources (입력)     Propagators (전파)   Sinks (위험)  │
│   ─────────────     ────────────────     ──────────  │
│   request.params    string.concat()      eval()      │
│   request.body      array.push()         exec()      │
│   request.query     object.assign()      query()     │
│   request.headers   template literals    render()    │
│   file.read()       destructuring        write()     │
│   env.get()         spread operator      redirect()  │
│                                                     │
│   ▼                       ▼                    ▼    │
│   [TAINT TAG]         [PROPAGATE]          [ALERT]  │
│                                                     │
└─────────────────────────────────────────────────────┘

Sanitizers (무해화):
  - html.escape()    → XSS 제거
  - shlex.quote()    → Command Injection 제거
  - parameterized()  → SQLi 제거
  - validator()      → Input Validation
```

### 4. Semantic Analysis 강화

```python
# 기존: 패턴 매칭
if "eval(" in code:
    report_vulnerability()

# 개선: 의미론적 분석
def semantic_analysis(code):
    ast = parse(code)
    
    # 1. 데이터 흐름 추적
    taint_flows = track_data_flow(ast)
    
    # 2. 제어 흐름 분석
    control_deps = analyze_control_flow(ast)
    
    # 3. 경로 조건 확인
    path_conditions = extract_path_conditions(ast)
    
    # 4. 도달 가능성 검사
    for flow in taint_flows:
        if is_reachable(flow, path_conditions):
            if not is_sanitized(flow, control_deps):
                report_vulnerability(flow)
```

### 5. CodeQL/Semgrep 스타일 쿼리 언어

```yaml
# Custom Rule Definition
- id: flask-sql-injection
  severity: critical
  language: python
  message: "Possible SQL injection in Flask route"
  pattern: |
    @app.route(...)
    def $FUNC(...):
      ...
      $DB.execute($QUERY.format(..., $USER_INPUT, ...))
      ...
  where:
    - $USER_INPUT comes from request.*
    - $DB is database connection
    - $QUERY is not parameterized
  fix: |
    Use parameterized queries: 
    $DB.execute($QUERY, (params,))
```

---

## 📈 업계 트렌드 및 벤치마크

### 주요 경쟁 도구 비교

| 도구 | 언어 지원 | 정확도 | 속도 | AI 통합 | 오픈소스 |
|------|----------|--------|------|---------|----------|
| **Semgrep** | 30+ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐⭐ | ❌ | ✅ |
| **CodeQL** | 10+ | ⭐⭐⭐⭐⭐ | ⭐⭐⭐ | ❌ | ✅ |
| **Snyk Code** | 20+ | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ | ❌ |
| **SonarQube** | 25+ | ⭐⭐⭐ | ⭐⭐⭐ | ❌ | 일부 |
| **Checkmarx** | 30+ | ⭐⭐⭐⭐ | ⭐⭐⭐ | ✅ | ❌ |
| **우리 도구** | 6 | ⭐⭐⭐⭐ | ⭐⭐⭐⭐ | ✅ | ✅ |

### 2025-2026 보안 분석 트렌드

1. **AI/LLM 기반 분석**
   - GitHub 보안 연구소: AI 기반 취약점 분류
   - Semgrep: 어시스턴트 생성 설명
   - Microsoft: 위협 보고서 → 탐지 인사이트

2. **공급망 보안**
   - SBOM (소프트웨어 자재 명세서) 의무화
   - 의존성 그래프 + 도달 가능성 분석
   - Sigstore/SLSA 통합

3. **시프트-레프트 보안**
   - IDE 내 실시간 분석
   - PR/MR 시점 자동 검사
   - 코드로서의 보안 (GitOps)

4. **런타임 보안 (RASP/IAST)**
   - 정적 + 동적 하이브리드
   - 계측 기반 검증
   - eBPF 기반 런타임 모니터링

5. **제로 트러스트 보안**
   - API 보안 강화 (OAuth 2.0, mTLS)
   - ID 인식 프록시
   - 마이크로세그멘테이션

---

## 📅 향후 개발 로드맵

### 5단계: 고급 시각화 및 리포팅 (2026년 1분기)

#### 5.1 대화형 그래프 개선
```typescript
interface GraphEnhancements {
  layouts: ['dagre', 'force', 'hierarchical', 'circular'];
  nodeGrouping: {
    byFile: boolean;
    byModule: boolean;
    bySeverity: boolean;
  };
  filters: {
    vulnerabilityType: VulnType[];
    severity: Severity[];
    language: Language[];
  };
  export: ['svg', 'png', 'pdf', 'json'];
}
```
- [ ] Force-directed 레이아웃 추가
- [ ] 미니맵 네비게이션
- [ ] Context Menu (우클릭)
- [ ] Lasso Selection (드래그 선택)

#### 5.2 보고서 생성
```python
class ReportGenerator:
    formats = ['html', 'pdf', 'sarif', 'csv', 'json', 'markdown']
    
    def generate_html_report(self) -> str:
        """인터랙티브 HTML 리포트 (차트, 필터)"""
        
    def generate_pdf_report(self) -> bytes:
        """경영진/감사용 PDF 보고서"""
        
    def export_sarif(self) -> dict:
        """SARIF 2.1.0 (GitHub/IDE 통합)"""
        
    def export_csv(self) -> str:
        """스프레드시트 분석용"""
```
- [ ] SARIF 2.1.0 형식 지원
- [ ] HTML Interactive 보고서
- [ ] PDF Executive Summary
- [ ] CWE/OWASP 매핑

#### 5.3 히스토리 분석 및 Git 통합
```python
class HistoricalAnalyzer:
    def analyze_commit_history(self, repo: str) -> Timeline:
        """커밋별 보안 변화 추적"""
        
    def detect_security_regression(self, before, after) -> Report:
        """보안 회귀 탐지"""
        
    def blame_analysis(self, vulnerability) -> BlameInfo:
        """취약점 도입자 추적"""
```
- [ ] Git History 기반 추이 분석
- [ ] 보안 회귀 탐지 알림
- [ ] Blame 분석 (누가 도입했나)

### 6단계: 개발자 도구 및 통합 (2026년 2분기)

#### 6.1 VS Code 확장 프로그램
```typescript
class VSCodeExtension {
  // 실시간 분석
  onDidSaveTextDocument() { ... }
  
  // Problems Panel 통합
  updateDiagnostics() { ... }
  
  // Quick Fix 제공
  provideCodeActions() { ... }
  
  // WebView로 그래프 표시
  showGraphPanel() { ... }
}
```
- [ ] 파일 저장 시 자동 분석
- [ ] Problem Panel 취약점 표시
- [ ] Quick Fix 제안
- [ ] WebView 그래프 내장
- [ ] Status Bar 보안 점수

#### 6.2 명령줄 도구 (CLI)
```bash
# 기본 분석
websecviz analyze ./project

# 옵션 지정
websecviz analyze ./project \
  --languages python,javascript \
  --format sarif \
  --output results.sarif \
  --severity critical,high

# CI/CD 통합
websecviz analyze . --format sarif | \
  gh api repos/{owner}/{repo}/code-scanning/sarifs -X POST --input -

# 지속적 모니터링
websecviz watch ./project --interval 30s
```
- [ ] 명령줄 분석 도구
- [ ] SARIF 출력 지원
- [ ] CI/CD 종료 코드
- [ ] Watch 모드

#### 6.3 CI/CD 통합
```yaml
# GitHub Actions
- name: Security Analysis
  uses: our-tool/action@v1
  with:
    path: ./
    fail-on: critical,high
    sarif-output: security.sarif

# GitLab CI
security-analysis:
  script:
    - websecviz analyze . --format sarif
  artifacts:
    reports:
      sast: security.sarif
```
- [ ] GitHub Actions
- [ ] GitLab CI
- [ ] Jenkins Plugin
- [ ] Azure DevOps

### 7단계: 데이터베이스 및 성능 최적화 (2026년 2분기)

#### 7.2 TimescaleDB 시계열 데이터베이스
```sql
-- 분석 결과 시계열 저장
CREATE TABLE analysis_history (
    time TIMESTAMPTZ NOT NULL,
    project_id UUID,
    vulnerability_count INT,
    security_score INT
);

SELECT create_hypertable('analysis_history', 'time');
SELECT add_retention_policy('analysis_history', INTERVAL '90 days');
```
- [ ] 분석 결과 시계열 저장
- [ ] 자동 데이터 보존 정책
- [ ] 연속 집계 (트렌드 분석)

#### 7.3 프론트엔드 성능 최적화
- [x] React Query 데이터 페칭 ✅
- [x] 무한 스크롤 취약점 목록 ✅
- [x] Web Worker 그래프 레이아웃 ✅
- [x] Service Worker 캐싱 ✅

### 8단계: 고급 보안 기능 (2026년 3분기)

#### 8.1 공급망 보안 (Supply Chain Security)
```python
class SBOMGenerator:
    def generate_cyclonedx(self) -> CycloneDXSBOM: ...
    def generate_spdx(self) -> SPDXSBOM: ...
    def scan_dependencies(self) -> VulnReport: ...
    def verify_provenance(self) -> ProvenanceReport: ...
```
- [ ] SBOM 생성 (CycloneDX, SPDX)
- [ ] 의존성 취약점 스캔
- [ ] 라이선스 컴플라이언스
- [ ] 출처 검증 (Sigstore)

#### 8.2 비밀정보 탐지 (Secrets Detection)
```yaml
비밀정보 탐지:
  Patterns:
    - API Keys (AWS, GCP, Azure, Stripe)
    - Private Keys (RSA, SSH, PGP)
    - Tokens (JWT, OAuth, PAT)
    - Database Credentials
    - Environment Secrets
  
  Features:
    - High Precision (low FP)
    - Git History Scanning
    - Automatic Revocation
```
- [ ] 630+ 자격증명 유형 탐지
- [ ] Git 히스토리 스캔
- [ ] 자동 무효화 연동

#### 8.3 하이브리드 분석 (SAST + DAST)
```yaml
하이브리드 파이프라인:
  Stage 1 - SAST:
    - Source code scanning
    - Dependency analysis
    
  Stage 2 - DAST:
    - Automated fuzzing
    - API endpoint testing
    
  Stage 3 - Correlation:
    - Cross-reference findings
    - Exploitability validation
```
- [ ] DAST 엔진 통합
- [ ] Fuzzing 자동화
- [ ] 결과 상관관계 분석

### 9단계: 커뮤니티 및 생태계 (2026년 4분기)

#### 9.1 플러그인 시스템
```python
class PluginInterface:
    """Custom analyzer plugins"""
    
    def analyze(self, code: str, ast: AST) -> List[Finding]:
        raise NotImplementedError
        
    def get_rules(self) -> List[Rule]:
        raise NotImplementedError
```
- [ ] 플러그인 아키텍처
- [ ] Custom Rule SDK
- [ ] 플러그인 마켓플레이스

#### 9.2 규칙 편집기 UI
```typescript
interface RuleEditor {
  visualPatternBuilder: PatternBuilder;
  livePreview: PreviewPanel;
  testCases: TestRunner;
  importExport: RuleIO;
}
```
- [ ] 시각적 패턴 빌더
- [ ] 실시간 미리보기
- [ ] 테스트 케이스 실행
- [ ] 규칙 공유/내보내기

---

## 🔄 기술 부채 및 리팩토링

### 코드 품질 개선

1. **테스트 커버리지 확대**
   - 현재: ~60% → 목표: 85%
   - E2E 테스트 추가 (Playwright)
   - 성능 벤치마크 테스트

2. **타입 안정성**
   - TypeScript strict mode
   - Python type hints 100%
   - Pydantic v2 마이그레이션

3. **문서화**
   - API 문서 (OpenAPI)
   - 개발자 가이드
   - 규칙 작성 튜토리얼

4. **아키텍처 개선**
   - 모듈 분리 (Core, Analyzers, Rules)
   - 의존성 주입 패턴
   - Event-driven 아키텍처

### 성능 프로파일링

```bash
# 병목 지점 분석
- 파일 파싱: 30%
- Taint Analysis: 40%
- Symbol Resolution: 15%
- Report Generation: 10%
- Others: 5%
```

### 마이그레이션 계획

| 항목 | 현재 | 목표 | 우선순위 |
|------|------|------|----------|
| Python | 3.11 | 3.12 | 🟡 |
| FastAPI | 0.109 | 0.110+ | 🟢 |
| Next.js | 16 | 17 | 🟢 |
| React | 19 | 19.1 | 🟢 |
| ReactFlow | 11 | 12 | 🟡 |
| Pydantic | 2.x | 2.10+ | 🟢 |

---

## 📚 참고 자료

### 업계 표준 및 가이드
- [OWASP Top 10 2025](https://owasp.org/Top10/2025/) - 웹 애플리케이션 보안 위험 통계
- [OWASP 웹 보안 테스트 가이드](https://owasp.org/www-project-web-security-testing-guide/) - 보안 테스트 방법론
- [OWASP 치트 시트 시리즈](https://cheatsheetseries.owasp.org/) - 보안 모범 사례
- [CWE (공통 취약점 열거)](https://cwe.mitre.org/) - 취약점 분류 체계
- [NIST SAST 표준](https://csrc.nist.gov/) - 정적 분석 표준

### 도구 및 프레임워크
- [Semgrep 문서](https://semgrep.dev/docs/) - 정적 분석 도구
- [CodeQL 문서](https://codeql.github.com/docs/) - GitHub 코드 분석 도구
- [SARIF 명세서](https://sarifweb.azurewebsites.net/) - 보안 분석 결과 형식
- [CycloneDX SBOM](https://cyclonedx.org/) - 소프트웨어 자재 명세서 표준

### 연구 논문
- "Points-to Analysis" - Andersen 알고리즘 (포인터 분석)
- "IFDS/IDE Framework" - 함수 간 데이터 흐름 분석
- "CFL-Reachability" - 문맥 자유 언어 도달 가능성
- "Symbolic Execution" - 경로 민감 분석 (기호 실행)

---

## 📌 버전 히스토리

| 버전 | 날짜 | 주요 변경 |
|------|------|----------|
| v0.14.0 | 2026-01-30 | Distributed Analysis Architecture |
| v0.13.0 | 2026-01-30 | Advanced Data-Flow Analysis (CFG/PDG) |
| v0.12.0 | 2026-01-29 | LLM Security Analyzer |
| v0.11.0 | 2026-01-28 | ML-based Vulnerability Detector |
| v0.10.0 | 2026-01-25 | Class Hierarchy Analysis |
| v0.9.0 | 2026-01-20 | Type Inference System |
| v0.8.0 | 2026-01-15 | Streaming API |
| v0.7.0 | 2026-01-10 | Inter-procedural Taint Analysis |

---

## 🤝 기여 및 피드백

### 기여 방법
1. Issue 생성 (버그 리포트, 기능 요청)
2. Pull Request 제출
3. 보안 규칙 작성 및 공유
4. 문서 개선

### 로드맵 피드백
이 로드맵에 대한 의견이나 제안은 GitHub Issues에 남겨주세요.

---

*이 문서는 프로젝트의 현재 상태와 향후 계획을 담고 있습니다. 정기적으로 업데이트됩니다.*
