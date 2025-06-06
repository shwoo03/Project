# 인스타그램 팔로워/ 팔로잉 정리 프로그램 
인스타그램에서 맞팔(상호 팔로우) 여부를 자동 분석하고,      
나를 팔로우하지 않는 계정을 찾는 Python 기반 자동화 도구입니다.            
<br>

## 사용 방법 
main.py 실행하고 ID, PW 값 넣으시면 됩니다.         
requirements.txt에 필요한 라이브러리 설치하시면 됩니다        
<br>

## 주요 기능 
| 기능 번호 | 설명                   |
| ----- | -------------------- |
| 1     | 인스타그램 계정 로그인 자동화     |
| 2     | 팔로워 목록 수집            |
| 3     | 팔로잉 목록 수집            |
| 4     | 상호 팔로우/비팔로우 분석       |
| 5     | 결과 출력 (콘솔 또는 CSV 가능) |
<br>

## 구조 
![image](https://github.com/user-attachments/assets/aac61be2-9c29-4cdd-a2ed-86d8ad9006cf)
<br>



## 기술 접근 
- Selenium으로 자동 로그인 → 세션 쿠키 확보       
- 개발자 도구 Network 탭 분석으로 팔로워 API 추출     
- https://www.instagram.com/api/v1/friendships/{user_id}/{follow_type}/ 형식의 API 호출     
- CSRF Token, User-Agent, SessionID 등 헤더 조작을 통해 API 우회 성공   
- JSON 응답을 파싱하여 사용자 리스트 추출    
<br>

## 결과
![image](https://github.com/user-attachments/assets/7082ccb9-4464-4b4a-a9ef-1408b487d394)
<br>

## 기타
해당 프로그램에서는 사용자 ID, PW 값을 로컬에서 처리하므로 개인정보 유출에대한 위험이 없습니다.      
2FA 계정은 사용이 힘들 수 있습니다.     
<br>
