# JOB

엔키 채용 페이지와 더오리(Theori) 채용 페이지를 크롤링해 노션 데이터베이스에 동기화하고, 신규 공고가 생기면 디스코드 웹훅으로 알려줍니다.

## 환경 변수
모든 스크립트는 `job/.env`(또는 동일한 키를 갖는 시스템 환경 변수)에서 값을 읽습니다.

```
NOTION_TOKEN=
NOTION_DATABASE_ID=
DISCORD_WEBHOOK_URL=
```

선택 속성 이름을 바꾸고 싶다면 아래 키로 덮어쓸 수 있습니다.

```
NOTION_LINK_PROP=Link
NOTION_COMPANY_PROP=회사
NOTION_TEAM_PROP=팀
NOTION_ROLE_PROP=직무
NOTION_EMPLOYMENT_PROP=고용형태
NOTION_EXPERIENCE_PROP=경력
NOTION_LOCATION_PROP=근무지
NOTION_DETAIL_LOCATION_PROP=상세 근무지
NOTION_DEADLINE_PROP=마감일
NOTION_TAGS_PROP=태그
NOTION_JOB_ID_PROP=Job ID
NOTION_SOURCE_PROP=선택        # 소스(엔키/티오리)를 담을 select 속성 이름 (예: 선택, 플랫폼 등)
```

## 실행 방법
### Enki (엔키)
```bash
cd job
python enki.py           # 실제 동기화
python enki.py --dry-run # 노션/디스코드 호출 없이 확인
```

추가 옵션
```
ENKI_GUIDE_URL=https://enki.career.greetinghr.com/ko/guide?employments=INTERN_WORKER
ENKI_SOURCE_LABEL=엔키      # 노션 select 값
ENKI_DRY_RUN=true          # 항상 드라이런
```

### Theori (티오리)
```bash
cd job
python theori.py           # 실제 동기화
python theori.py --dry-run # 노션/디스코드 호출 없이 확인
```

추가 옵션
```
THEORI_API_URL=https://theori.io/api/service/position
THEORI_COMPANY_NAME=Theori
THEORI_SOURCE_LABEL=티오리
THEORI_DRY_RUN=false
```

## 동작 방식
1. `.env`를 읽어 노션/디스코드 자격 증명을 확보합니다.
2. 각 소스에서 최신 채용 공고를 가져와 `JobPosting` 객체로 정규화합니다.
3. 노션 데이터베이스를 조회해 기존 링크·타이틀·외부 ID를 인덱싱하고, 중복이 없을 때만 새 페이지를 생성합니다.
4. 신규 공고가 존재하면 소스 이름을 포함한 메시지로 디스코드 웹훅에 알립니다.
