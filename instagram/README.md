# 인스타그램 팔로워/ 팔로잉 정리 프로그램 
인스타그램에서 맞팔(상호 팔로우) 여부를 자동 분석하고,      
나를 팔로우하지 않는 계정을 찾는 Python 기반 자동화 도구입니다.     


## 주요 기능 
| 기능 번호 | 설명                   |
| ----- | -------------------- |
| 1     | 인스타그램 계정 로그인 자동화     |
| 2     | 팔로워 목록 수집            |
| 3     | 팔로잉 목록 수집            |
| 4     | 상호 팔로우/비팔로우 분석       |
| 5     | 결과 출력 (콘솔 또는 CSV 가능) |


## 구조 
instagram/
├── login.py                     # 로그인 자동화 및 쿠키 관리
├── get_follow_list_requests.py  # API를 활용한 팔로워/팔로잉 수집
├── main.py                      # 전체 실행 흐름 및 출력
├── requirements.txt             # 필요 패키지 목록
├── install.sh / install.bat     # 자동 설치 스크립트 (선택)
└── README.md                    # 설명 문서



## 기술 접근 
Selenium으로 자동 로그인 → 세션 쿠키 확보       
개발자 도구 Network 탭 분석으로 팔로워 API 추출     
https://www.instagram.com/api/v1/friendships/{user_id}/{follow_type}/ 형식의 API 호출     
CSRF Token, User-Agent, SessionID 등 헤더 조작을 통해 API 우회 성공   
JSON 응답을 파싱하여 사용자 리스트 추출    
