# Cookie Manipulation & Broken Access Control

## 취약점 정보
- **유형**: Broken Access Control (Insecure Direct Object References via Cookie)
- **위치**: Cookie 'username'
- **파라미터**: username
- **CVSS**: 9.1 (Critical) - Admin 권한 획득 가능

## 공격 벡터
1.  **쿠키 변조**: 서버가 `username` 쿠키를 신뢰하여 신원을 확인합니다.
2.  **권한 상승**: `username=admin`으로 쿠키를 설정하면 관리자 권한을 획득하고 플래그를 볼 수 있습니다.

## 기대 탐지
- **패턴**: 
    - 응답에 "flag is" 문자열이 포함되면 성공.
    - `Set-Cookie` 헤더 분석을 통해 민감한 정보(username)가 평문으로 저장되는지 확인.
- **시나리오**:
    1. BaseReq: `GET /` (username 쿠키 없음) -> "Welcome !"
    2. Fuzzing: `Cookie: username=admin` -> "Hello admin, flag is DH{...}"

## 테스트 결과
- [ ] 탐지 성공: 퍼저가 `username` 쿠키에 `admin` 페이로드를 주입하여 플래그를 획득.
