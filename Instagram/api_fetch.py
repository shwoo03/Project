import time

import requests

BASE = "https://www.instagram.com"


def selenium_cookies_to_session(driver):
    sess = requests.Session()
    ua = driver.execute_script("return navigator.userAgent")
    sess.headers.update(
        {
            "User-Agent": ua,
            "Accept": "*/*",
            "Accept-Language": "ko-KR,ko;q=0.9,en-US;q=0.8",
            "X-Requested-With": "XMLHttpRequest",
            "Referer": "https://www.instagram.com/",
        }
    )
    for c in driver.get_cookies():
        sess.cookies.set(
            c["name"],
            c["value"],
            domain=c.get("domain") or ".instagram.com",
            path=c.get("path") or "/",
        )
    return sess


def _build_headers(sess):
    headers = dict(sess.headers)
    csrf = sess.cookies.get("csrftoken")
    if csrf:
        headers["X-CSRFToken"] = csrf
    headers["X-IG-App-ID"] = "936619743392459"
    headers["X-ASBD-ID"] = "129477"
    return headers


def _fetch_page(session, user_id, kind, max_id=None, count=200, pause=0.5, retry=10):
    params = {"count": count}
    if max_id:
        params["max_id"] = max_id
    url = f"{BASE}/api/v1/friendships/{user_id}/{kind}/"
    for attempt in range(retry):
        response = session.get(url, params=params, headers=_build_headers(session))
        if response.status_code == 200:
            data = response.json()
            time.sleep(pause)
            return data
        if attempt < retry - 1:
            time.sleep(1.5 * (attempt + 1))
            continue
        raise RuntimeError(
            f"{kind} request failed {response.status_code}: {response.text[:250]}"
        )
    return {}


def fetch_all(session, user_id, kind, limit=1000, page_size=200, verbose=False):
    if limit is not None and limit <= 0:
        return set()

    collected = []
    max_id = None
    round_idx = 0
    page_size = max(1, min(200, page_size))

    while True:
        round_idx += 1
        count = page_size
        if limit is not None:
            remaining = limit - len(collected)
            if remaining <= 0:
                break
            count = min(page_size, remaining)

        data = _fetch_page(session, user_id, kind, max_id, count=count)
        users_batch = data.get("users", []) or []

        if verbose:
            print(
                f"[{kind}] page {round_idx}: +{len(users_batch)} total {len(collected) + len(users_batch)}"
            )

        if not users_batch and not data.get("next_max_id"):
            break

        collected.extend(users_batch)

        if limit is not None and len(collected) >= limit:
            collected = collected[:limit]
            break

        next_max_id = data.get("next_max_id")
        has_more = data.get("has_more")
        if not next_max_id:
            break
        if has_more is False and next_max_id == max_id:
            break

        max_id = next_max_id

    usernames = {user.get("username") for user in collected if user.get("username")}
    return usernames


def get_non_mutual_via_api(
    session,
    limit_followers=1000,
    limit_following=1000,
    verbose=False,
):
    my_id = session.cookies.get("ds_user_id")
    if not my_id:
        raise RuntimeError("Missing ds_user_id cookie (login required)")

    followers = fetch_all(session, my_id, "followers", limit_followers, verbose=verbose)
    following = fetch_all(session, my_id, "following", limit_following, verbose=verbose)

    return {
        "followers": followers,
        "following": following,
        "not_following_back": following - followers,
        "not_followed_by_me": followers - following,
    }
