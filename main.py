import os
import logging
import time
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, WebDriverException
from webdriver_manager.chrome import ChromeDriverManager
from google.cloud import secretmanager
from config import PROJECT_IDS, BASE_URL, LOGIN_WAIT_TIME
import functions_framework

# ログの設定
logging.basicConfig(level=logging.INFO)

def get_secret(secret_id):
    """Secret Managerから機密情報を取得"""
    client = secretmanager.SecretManagerServiceClient()
    name = f"projects/{os.environ['GCP_PROJECT']}/secrets/{secret_id}/versions/latest"
    response = client.access_secret_version(request={"name": name})
    return response.payload.data.decode("UTF-8")

def setup_chrome_driver():
    """Chromeドライバーのセットアップ"""
    chrome_options = Options()
    chrome_options.add_argument('--headless')
    chrome_options.add_argument('--no-sandbox')
    chrome_options.add_argument('--disable-dev-shm-usage')
    chrome_options.add_argument('--disable-gpu')
    chrome_options.add_argument('--disable-software-rasterizer')
    chrome_options.binary_location = os.environ.get('GOOGLE_CHROME_BIN', '/usr/bin/google-chrome')
    
    service = Service(executable_path=os.environ.get('CHROMEDRIVER_PATH', '/usr/local/bin/chromedriver'))
    return webdriver.Chrome(service=service, options=chrome_options)

def update_titles():
    """タイトル更新の実行関数"""
    try:
        # Chromeドライバーのセットアップ
        driver = setup_chrome_driver()
        wait = WebDriverWait(driver, 10)
        
        # ログイン
        email = get_secret('WANTEDLY_EMAIL')
        password = get_secret('WANTEDLY_PASSWORD')
        
        driver.get(f"{BASE_URL}/sign_in")
        
        # メールアドレスとパスワードを入力
        email_field = wait.until(EC.presence_of_element_located((By.NAME, "email")))
        email_field.send_keys(email)
        
        password_field = wait.until(EC.presence_of_element_located((By.NAME, "password")))
        password_field.send_keys(password)
        
        # ログインボタンをクリック
        login_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, "button[type='submit']")))
        login_button.click()
        time.sleep(5)  # ログイン完了を待機
        
        # 各プロジェクトのタイトルを更新
        for project_id in PROJECT_IDS:
            try:
                logging.info(f"Processing project ID: {project_id}")
                driver.get(f"{BASE_URL}/projects/{project_id}/edit/title")
                
                input_field = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input.wui-visit-light-textfield-translucent"))
                )
                
                original_title = input_field.get_attribute("value").strip()
                logging.info(f"Original title: {original_title}")
                
                # タイトルを一時的に変更
                input_field.send_keys(Keys.END)
                input_field.send_keys(" ")
                time.sleep(1)
                
                # 空白を削除
                input_field.send_keys(Keys.BACK_SPACE)
                time.sleep(1)
                
                # 更新ボタンを探して実行
                buttons = driver.find_elements(By.TAG_NAME, "button")
                update_button = None
                for button in buttons:
                    try:
                        if "更新" in button.text:
                            update_button = button
                            break
                    except:
                        continue
                
                if not update_button:
                    raise Exception(f"Update button not found for project {project_id}")
                
                update_button.click()
                time.sleep(2)
                
                logging.info(f"Successfully updated project {project_id}")
                
            except Exception as e:
                logging.error(f"Error processing project {project_id}: {str(e)}")
                continue
            
    except Exception as e:
        logging.error(f"Error: {str(e)}")
        raise e
        
    finally:
        try:
            driver.quit()
        except:
            pass

@functions_framework.http
def update_wantedly_titles(request):
    """Cloud Functions のエントリーポイント"""
    try:
        update_titles()
        return 'Success', 200
    except Exception as e:
        logging.error(f'Error: {str(e)}')
        return f'Error: {str(e)}', 500

if __name__ == '__main__':
    update_titles() 