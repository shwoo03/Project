from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException
import random, time
import requests
import json


def login(driver, id, pw, timeout=15):
    wait = WebDriverWait(driver, timeout)

    # id, pw 받아서 전송 
    user_input = wait.until(EC.presence_of_element_located((By.NAME, "username")))
    pass_input = wait.until(EC.presence_of_element_located((By.NAME, "password")))

    user_input.clear()
    user_input.send_keys(id)

    pass_input.clear()
    pass_input.send_keys(pw)

    login_btn = wait.until(EC.element_to_be_clickable((By.XPATH, "//button[@type='submit']")))
    login_btn.click()


    # 나중에 하기 버튼 클릭 
    btn = wait.until(
            EC.element_to_be_clickable((By.XPATH, "//div[@role='button' and contains(text(), '나중에 하기')]"))
        )
    btn.click()


