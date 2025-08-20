import requests, time, math

BASE = "https://www.instagram.com"

# 로그인 세션 정보들을 모두 준비 함 그래야 API 호출 가능 
def selenium_cookies_to_session(driver):
    sess = requests.Session()
    ua = driver.execute_script("return navigator.userAgent")
    sess.headers.update({
        "User-Agent": ua,
        "Accept": "*/*",
        "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
        "X-Requested-With": "XMLHttpRequest",
        "Referer": "https://www.instagram.com/",
    })
    for c in driver.get_cookies():
        sess.cookies.set(
            c["name"],
            c["value"],
            domain=c.get("domain") or ".instagram.com",
            path=c.get("path") or "/"
        )
    return sess


def _build_headers(sess):
    h = dict(sess.headers)
    csrf = sess.cookies.get("csrftoken")
    if csrf:
        h["X-CSRFToken"] = csrf
    # 내부에서 자주 보이는 헤더 (없어도 동작하지만 일치도 위해)
    h["X-IG-App-ID"] = "936619743392459"
    h["X-ASBD-ID"] = "129477"
    return h


def _fetch_page(session, user_id, kind, max_id=None, count=50, pause=0.5, retry=3):
    params = {"count": count}
    if max_id:
        params["max_id"] = max_id
    url = f"{BASE}/api/v1/friendships/{user_id}/{kind}/"
    for attempt in range(retry):
        r = session.get(url, params=params, headers=_build_headers(session))
        if r.status_code == 200:
            data = r.json()
            time.sleep(pause)
            return data
        if attempt < retry - 1:
            sleep_for = 1.5 * (attempt + 1)
            time.sleep(sleep_for)
            continue
        raise RuntimeError(f"{kind} 요청 실패 {r.status_code}: {r.text[:250]}")
    return {}



def fetch_all(session, user_id, kind, limit=None, verbose=False):
    collected = []
    max_id = None
    round_idx = 0
    # 안전 상한 (필요시 조정)
    hard_cap = limit if limit else 20000
    while True:
        round_idx += 1
        data = _fetch_page(session, user_id, kind, max_id)
        users_batch = data.get("users", [])
        collected.extend(users_batch)
        if verbose:
            print(f"[{kind}] batch {round_idx} 수집 {len(users_batch)} 누적 {len(collected)}")
        if limit and len(collected) >= limit:
            collected = collected[:limit]
            break
        next_max_id = data.get("next_max_id")
        has_more = data.get("has_more")
        # 종료 조건
        if not next_max_id:
            break
        # 일부 응답은 has_more False라도 next_max_id 한 번 더 줌 → 한 번은 진행
        if has_more is False and next_max_id == max_id:
            break
        if len(collected) >= hard_cap:
            break
        max_id = next_max_id
    usernames = {u.get("username") for u in collected if u.get("username")}
    return usernames

def get_non_mutual_via_api(session, limit_followers=None, limit_following=None, verbose=False):
    my_id = session.cookies.get("ds_user_id")
    if not my_id:
        raise RuntimeError("ds_user_id 쿠키 없음 (로그인 실패)")
    followers = fetch_all(session, my_id, "followers", limit_followers, verbose)
    following = fetch_all(session, my_id, "following", limit_following, verbose)
    return {
        "followers": followers,
        "following": following,
        "not_following_back": following - followers,
        "not_followed_by_me": followers - following
    }