import os

from dotenv import load_dotenv

from setting import get_driver
from login import login
from api_fetch import selenium_cookies_to_session, get_non_mutual_via_api

load_dotenv()

if __name__ == "__main__":
    driver = get_driver()

    username = os.getenv("INSTAGRAM_USERNAME")
    password = os.getenv("INSTAGRAM_PASSWORD")

    if not username or not password:
        raise RuntimeError(
            "INSTAGRAM_USERNAME and INSTAGRAM_PASSWORD must be set. See README for details."
        )

    login(driver, username, password)

    # Transfer Selenium cookies into a requests session for API calls.
    session = selenium_cookies_to_session(driver)

    result = get_non_mutual_via_api(session)

    print(f"총 팔로워 수: {len(result['followers'])}")
    print(f"총 팔로잉 수: {len(result['following'])}")
    print(f"\n나를 팔로우하지 않는 계정 수: {len(result['not_following_back'])}")
    if result['not_following_back']:
        print("- 나를 팔로우하지 않는 계정 목록:")
        for user in sorted(result['not_following_back']):
            print(f"  - {user}")
    else:
        print("- 모든 팔로잉이 나를 팔로우합니다.")
    print(f"\n내가 팔로우하지 않는 계정 수: {len(result['not_followed_by_me'])}")
    if result['not_followed_by_me']:
        print("- 내가 팔로우하지 않는 계정 목록:")
        for user in sorted(result['not_followed_by_me']):
            print(f"  - {user}")
    else:
        print("- 모든 팔로워를 팔로우하고 있습니다.")

    driver.quit()
