from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import time

# 해당 코드에서는 팔로워/팔로잉 수를 크롤링하여 리스트에 저장한다.


# 팔로워 수 크롤링 
def open_follower_modal(driver):
    wait = WebDriverWait(driver, 10)

    try:
        # 팔로워 텍스트가 있는 a 태그 클릭
        follower_button = wait.until(EC.element_to_be_clickable(
            (By.XPATH, "//a[contains(@href, '/followers')]")
        ))
        follower_button.click()
        print("팔로워 모달 창 열기")
        time.sleep(2)  # 모달 로딩 시간
    except Exception as e:
        print("팔로워 버튼 클릭 실패:", e)


# 맨 밑으로 스크롤 하기 
def scroll_to_bottom(driver, max_scroll=30, delay=1):
    print("팔로워 목록 스크롤 시작")
    
    scroll_box = WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.XPATH, "/html/body/div[5]/div[2]/div/div/div[1]/div/div[2]/div/div/div/div/div[2]/div/div/div[3]"))
    )

    last_height = 0
    scroll_attempts = 0

    while scroll_attempts < max_scroll:
        # 자바스크립트로 scrollHeight 확인
        current_height = driver.execute_script("return arguments[0].scrollHeight", scroll_box)

        if current_height == last_height:
            print("스크롤 완료")
            break

        # 스크롤 다운
        driver.execute_script("arguments[0].scrollTop = arguments[0].scrollHeight", scroll_box)
        time.sleep(delay)
        last_height = current_height
        scroll_attempts += 1

    print("스크롤 완료")
