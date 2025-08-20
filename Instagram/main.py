from setting import get_driver
from login import login
from api_fetch import selenium_cookies_to_session, get_non_mutual_via_api

if __name__ == "__main__":
    driver = get_driver()

    username = "seunghun0312"
    password = "Dntmdgns01~"
    login(driver, username, password)

    # Selenium 쿠키 → requests 세션 (여기가 추가)
    session = selenium_cookies_to_session(driver)

    result = get_non_mutual_via_api(session)

    print("총 팔로워 수:", len(result["followers"]))
    print("총 팔로잉 수:", len(result["following"]))
    print("\n나를 팔로우 하지 않음:", len(result["not_following_back"]))
    for u in sorted(result["not_following_back"]):
        print(" -", u)
    print("\n내가 팔로우 하지 않음:", len(result["not_followed_by_me"]))
    for u in sorted(result["not_followed_by_me"]):
        print(" -", u)

    driver.quit()