from login import login
from get_follow_list_requests import extract_cookies, get_follow_list

if __name__ == "__main__":
    username = input("아이디 입력: ")
    password = input("비밀번호 입력: ")

    driver = login(username, password)

    # 쿠키 추출 및 user_id 확인
    cookies = extract_cookies(driver)
    user_id = cookies.get("ds_user_id")

    # 팔로워/팔로잉 목록 요청
    followers = get_follow_list(user_id, "followers", cookies)
    following = get_follow_list(user_id, "following", cookies)

    # 맞팔 분석
    mutual = set(followers) & set(following)
    not_following_back = set(following) - set(followers)

    print("\n전체 팔로잉 수:", len(following))
    print("전체 팔로워 수:", len(followers))
    print("맞팔 수:", len(mutual))
    print("나를 안 팔로우하는 사람 수:", len(not_following_back))

    print("나를 안 팔로우하는 사람 목록:")
    for user in sorted(not_following_back):
        print("-", user)
