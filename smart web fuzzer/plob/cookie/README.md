# Cookie 문제

## 설명
간단한 쿠키 인증 취약점 문제입니다.
`username` 쿠키를 조작하여 관리자(admin) 권한을 획득하고 플래그를 찾아보세요.

## 실행 방법
```bash
docker-compose up -d
```

## 접속 정보
- URL: http://localhost:8000
- Guest 계정: guest / guest

## 목표
- `admin` 계정으로 로그인한 척 속여서 플래그를 획득하세요.
