from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
import pickle
import os
import time
# 현재 코드는 Instagram 로그인 페이지 접근 후 로그인 버튼 클릭 -> 프로필 접근 까지의 과정을 구현함 


COOKIE_PATH = "./session/session.pkl" # 세션 쿠키 저장 경로


# 셀레니움 드라이버 설정 
def create_driver():
    options = Options()

    # 탐지 방지 옵션
    options.add_argument("--disable-blink-features=AutomationControlled")
    options.add_experimental_option("excludeSwitches", ["enable-automation"]) # 자동화 안내 문구 제거 
    options.add_experimental_option("useAutomationExtension", False)  # 자동화 확장 프로그램 비활성화 

    # 사용자 에이전트 변경으로 탐지 우회
    options.add_argument("user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) ""AppleWebKit/537.36 (KHTML, like Gecko) Chrome/114.0.0.0 Safari/537.36")

    # 화면 사이즈 및 UI 설정
    options.add_argument("--start-maximized")
    options.add_argument("window-size=1920,1080")
    options.add_argument("--disable-infobars")
    options.add_argument("--log-level=3")

    # 페이지 로딩 -> DOMContentLoaded 시점에 완료
    options.page_load_strategy = 'eager'

    # 팝업 및 로그인 저장 차단
    prefs = {
        "profile.default_content_setting_values.notifications": 2,
        "credentials_enable_service": False,
        "profile.password_manager_enabled": False
    }
    options.add_experimental_option("prefs", prefs)
    driver = webdriver.Chrome(options=options)

    # navigator.webdriver 제거
    driver.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
        "source": """
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined  
            })
        """
    }) # -> undefined로 설정하여 탐지 방지

    return driver


# 쿠키 저장 (없으면 자동으로 생성해줌)
def save_cookies(driver, path=COOKIE_PATH):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        pickle.dump(driver.get_cookies(), f)


# 쿠키 불러오기
def load_cookies(driver, path=COOKIE_PATH):
    if not os.path.exists(path):
        return False
    with open(path, "rb") as f:
        cookies = pickle.load(f)
        for cookie in cookies:
            cookie.pop("expiry", None) 
            cookie.pop("sameSite", None)
            try:
                driver.add_cookie(cookie)
            except Exception as e:
                print(f"load_cookies 함수 에러!!!!: {e}")
    return True


# 계정 정보 저장 나중에하기 버튼 누르는 함수
def dismiss_save_info_popup(driver):
    try:
        wait = WebDriverWait(driver, 10)
        element = wait.until(EC.element_to_be_clickable((By.XPATH, "//div[text()='나중에 하기']")))
        element.click()
        print("'나중에 하기' 팝업 닫음")
    except Exception as e:
        print("팝업 닫기 실패 또는 없음:", e)



# 로그인 함수 (메인)
def login(username, password):
    driver = create_driver()
    wait = WebDriverWait(driver, 15)

    # 로그인 페이지 접근 
    driver.get("https://www.instagram.com/")
    time.sleep(3)

    if load_cookies(driver):
        print("쿠키 로드 완료")
        driver.refresh()
        time.sleep(3)
    
    wait.until(EC.presence_of_element_located((By.NAME, "username")))
    driver.find_element(By.NAME, "username").send_keys(username)
    driver.find_element(By.NAME, "password").send_keys(password)
    driver.find_element(By.XPATH, "//button[@type='submit']").click()
    
    # 팝업 무시
    dismiss_save_info_popup(driver)
    
    
    # 로그인 후 프로필 페이지 접근 
    time.sleep(2)
    driver.get(f"https://www.instagram.com/{username}/")
    print("프로필 페이지 접근 완료 팔로워/팔로잉 수 확인 프로세스로 전환")

    return driver
