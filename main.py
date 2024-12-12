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
from google.cloud import secretmanager
from config import PROJECT_IDS, BASE_URL, LOGIN_WAIT_TIME
import functions_framework
from contextlib import contextmanager

# ログの設定
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)
logger = logging.getLogger(__name__)

@contextmanager
def wait_for_page_load(driver, timeout=30):
    """ページの読み込みを待機するコンテキストマネージャー"""
    old_page = driver.find_element(By.TAG_NAME, "html")
    yield
    WebDriverWait(driver, timeout).until(EC.staleness_of(old_page))

def wait_for_js_load(driver, timeout=30):
    """JavaScriptの読み込みが完了するまで待機"""
    WebDriverWait(driver, timeout).until(
        lambda driver: driver.execute_script('return document.readyState') == 'complete'
    )

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
    chrome_options.add_argument('--window-size=1920,1080')
    chrome_options.add_argument('--start-maximized')
    chrome_options.binary_location = os.environ.get('GOOGLE_CHROME_BIN', '/usr/bin/google-chrome')
    
    service = Service(executable_path=os.environ.get('CHROMEDRIVER_PATH', '/usr/local/bin/chromedriver'))
    return webdriver.Chrome(service=service, options=chrome_options)

def log_page_state(driver, step_name):
    """現在のページの状態をログに記録"""
    logger.info(f"=== {step_name} ===")
    logger.info(f"現在のURL: {driver.current_url}")
    logger.info("ページソース:")
    logger.info(driver.page_source[:1000])  # より多くのページソースを表示
    logger.info("利用可能なボタン:")
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for button in buttons:
        try:
            logger.info(f"ボタンテキスト: {button.text}, type: {button.get_attribute('type')}")
        except:
            pass
    logger.info("=== 状態確認終了 ===")

def update_titles():
    """タイトル更新の実行関数"""
    driver = None
    try:
        logger.info("=== 処理開始 ===")
        logger.info(f"設定されているプロジェクトID: {PROJECT_IDS}")
        logger.info(f"BASE_URL: {BASE_URL}")
        
        logger.info("Wantedly更新処理を開始します")
        driver = setup_chrome_driver()
        wait = WebDriverWait(driver, 30)
        logger.info("Chromeドライバーの設定が完了しました")
        
        # ログイン情報の取得
        try:
            email = get_secret('WANTEDLY_EMAIL')
            password = get_secret('WANTEDLY_PASSWORD')
            logger.info("認証情報の取得に成功しました")
        except Exception as e:
            logger.error(f"認証情報の取得に失敗しました: {str(e)}")
            raise

        # ログインプロセス
        login_url = "https://www.wantedly.com/signin_or_signup"
        logger.info(f"ログインページにアクセスします: {login_url}")

        with wait_for_page_load(driver):
            driver.get(login_url)

        # ページ読み込みとJS実行完了を待機
        wait_for_js_load(driver)
        time.sleep(3)  # 追加の待機時間でDOMが安定するのを待つ

        # ログインページ初期状態をログ
        log_page_state(driver, "ログインページ初期状態")

        # メールアドレス入力フィールドを待機
        logger.info("メールアドレス入力フィールドを待機中...")
        try:
            # メール/パスワードログインへの切り替えリンクを探す（複数の可能性を試す）
            selectors = [
                "//a[contains(text(), 'メールアドレス')]",
                "//button[contains(text(), 'メールアドレス')]",
                "//div[contains(text(), 'メールアドレス')]",
                "//span[contains(text(), 'メールアドレス')]"
            ]
            for selector in selectors:
                try:
                    email_login_link = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                    logger.info(f"メール/パスワードログインリンクを見つけました: {selector}")
                    email_login_link.click()
                    time.sleep(3)
                    break
                except:
                    continue

            # ページの状態を確認
            log_page_state(driver, "メールログイン切り替え後")
        except:
            logger.info("すでにメール/パスワードログインフォームが表示されています")

        # メールアドレス入力フィールドを探す（複数の可能性を試す）
        field_selectors = [
            "input[type='email']", 
            "input[name='email']",
            "input[placeholder*='メール']",
            "input[placeholder*='mail']",
            "input#email"
        ]
        
        email_field = None
        for selector in field_selectors:
            try:
                email_field = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, selector)))
                logger.info(f"メールアドレス入力フィールドを見つけました: {selector}")
                break
            except:
                continue

        if not email_field:
            raise Exception("メールアドレス入力フィールドが見つかりませんでした")

        email_field.send_keys(email)
        logger.info("メールアドレスを入力しました")

        # 次へボタンを探す（複数の可能性を試す）
        button_selectors = [
            "//button[contains(text(), '次へ')]",
            "//button[@type='submit']", 
            "//input[@type='submit']",
            "//button[contains(@class, 'primary')]",
            "//button[@id='next-step-button']"
        ]

        next_button = None
        for selector in button_selectors:
            try:
                next_button = wait.until(EC.element_to_be_clickable((By.XPATH, selector)))
                logger.info(f"次へボタンを見つけました: {selector}")
                break
            except:
                continue

        if not next_button:
            raise Exception("次へボタンが見つかりませんでした")

        driver.execute_script("arguments[0].click();", next_button)
        logger.info("次へボタンをクリックしました")

        # 送信ボタンクリック後の状態確認
        log_page_state(driver, "送信ボタンクリック後")

        # ���スワード入力フィールドの待機処理を改善
        wait_for_js_load(driver)
        time.sleep(3)

        try:
            # パスワード入力フィールドのセレクターを追加
            password_selectors = [
                "input[type='password']",
                "input#password",
                "input[name='password']",
                "input.SigninAndSignupForm__TextField-sc-aqv94n-2"  # クラス名を追加
            ]
            
            password_field = None
            for selector in password_selectors:
                try:
                    password_field = wait.until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                    )
                    logger.info(f"パスワード入力フィールドを見つけました: {selector}")
                    break
                except:
                    continue

            if not password_field:
                raise Exception("パスワード入力フィールドが見つかりませんでした")

            password_field.send_keys(password)
            logger.info("パスワードを入力しました")

        except Exception as e:
            logger.error(f"パスワード入力フィールドの取得に失敗しました: {str(e)}")
            raise

        # パスワード入力後の状態確認
        log_page_state(driver, "パスワード入力後")

        # ログインボタンの処理を改善
        logger.info("ログインボタンを待機中...")
        wait_for_js_load(driver)
        time.sleep(3)

        try:
            login_button_selectors = [
                "button#next-step-button",
                "button[type='submit']",
                "button.SigninAndSignupForm__NextStepButton-sc-aqv94n-9"  # クラス名を追加
            ]
            
            login_button = None
            for selector in login_button_selectors:
                try:
                    login_button = wait.until(EC.element_to_be_clickable((By.CSS_SELECTOR, selector)))
                    logger.info(f"ログインボタンを見つけました: {selector}")
                    break
                except:
                    continue

            if not login_button:
                raise Exception("ログインボタンが見つかりませんでした")

            driver.execute_script("arguments[0].click();", login_button)
            logger.info("ログインボタンをクリックしました")

        except Exception as e:
            logger.error(f"ログインボタンの操作に失敗しました: {str(e)}")
            raise

        time.sleep(LOGIN_WAIT_TIME)
        logger.info("ログインプロセスが完了しました")

        # ログイン完了後の状態確認
        log_page_state(driver, "ログイン完了後")

        # プロジェクト更新処理
        for project_id in PROJECT_IDS:
            try:
                logger.info(f"プロジェクトID {project_id} の更新を開始します")
                project_url = f"{BASE_URL}/projects/{project_id}/edit/title"
                logger.info(f"プロジェクトページにアクセスします: {project_url}")
                driver.get(project_url)
                time.sleep(5)
                
                # プロジェクトページの状態確認
                log_page_state(driver, f"プロジェクト {project_id} ページ")
                
                input_field = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "input.wui-visit-light-textfield-translucent"))
                )
                
                original_title = input_field.get_attribute("value").strip()
                logger.info(f"現在のタイトル: {original_title}")
                
                # タイトルの更新処理
                input_field.send_keys(Keys.END)
                input_field.send_keys(" ")
                time.sleep(2)
                
                input_field.send_keys(Keys.BACK_SPACE)
                time.sleep(2)
                
                # 更新ボタンの検索と実行
                buttons = wait.until(EC.presence_of_all_elements_located((By.TAG_NAME, "button")))
                update_button = next((button for button in buttons if "更新" in button.text), None)
                
                if not update_button:
                    raise Exception(f"プロジェクト {project_id} の更新ボタンが見つかりませんでした")
                
                update_button.click()
                time.sleep(5)
                
                logger.info(f"プロジェクトID {project_id} の更新が完了しました")
                
            except Exception as e:
                logger.error(f"プロジェクトID {project_id} の更新中にエラーが発生しました: {str(e)}")
                continue
            
    except Exception as e:
        logger.error(f"予期せぬエラーが発生しました: {str(e)}", exc_info=True)
        raise
    finally:
        logger.info("=== 処理終了 ===")
        if driver:
            try:
                driver.quit()
                logger.info("ブラウザを正常に終了しました")
            except Exception as e:
                logger.error(f"ブラウザの終了中にエラーが発生しました: {str(e)}")

@functions_framework.http
def update_wantedly_titles(request):
    """Cloud Functions のエントリーポイント"""
    try:
        logger.info("Cloud Run処理を開始します")
        # 環境変数の確認
        logger.info(f"GCP_PROJECT: {os.environ.get('GCP_PROJECT')}")
        logger.info(f"GOOGLE_CHROME_BIN: {os.environ.get('GOOGLE_CHROME_BIN')}")
        logger.info(f"CHROMEDRIVER_PATH: {os.environ.get('CHROMEDRIVER_PATH')}")
        
        update_titles()
        return 'Success', 200
    except Exception as e:
        error_message = f"予期せぬエラーが発生しました: {str(e)}"
        logger.error(error_message)
        # スタックトレースも記録
        logger.exception("詳細なエラー情報:")
        return error_message, 500

if __name__ == '__main__':
    update_titles()