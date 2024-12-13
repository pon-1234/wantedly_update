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
    
    # iframeの確認
    iframes = driver.find_elements(By.TAG_NAME, "iframe")
    logger.info(f"iframeの数: {len(iframes)}")
    for idx, iframe in enumerate(iframes):
        logger.info(f"iframe {idx}: id={iframe.get_attribute('id')}, name={iframe.get_attribute('name')}")
    
    # Shadow DOMの確認
    shadow_roots = driver.execute_script("""
        return Array.from(document.querySelectorAll('*')).filter(el => el.shadowRoot).map(el => ({
            tag: el.tagName,
            id: el.id,
            class: el.className
        }));
    """)
    if shadow_roots:
        logger.info("Shadow DOM要素:")
        for root in shadow_roots:
            logger.info(f"Shadow host: tag={root['tag']}, id={root['id']}, class={root['class']}")
    
    logger.info("利用可能なボタン:")
    buttons = driver.find_elements(By.TAG_NAME, "button")
    for button in buttons:
        try:
            logger.info(f"ボタン情報: text='{button.text}', id='{button.get_attribute('id')}', "
                       f"class='{button.get_attribute('class')}', type='{button.get_attribute('type')}', "
                       f"aria-label='{button.get_attribute('aria-label')}', "
                       f"disabled='{button.get_attribute('disabled')}', "
                       f"display='{button.value_of_css_property('display')}', "
                       f"visibility='{button.value_of_css_property('visibility')}'")
        except:
            pass
    
    logger.info("利用可能な入力フィールド:")
    inputs = driver.find_elements(By.TAG_NAME, "input")
    for input_field in inputs:
        try:
            logger.info(f"入力フィールド情報: type='{input_field.get_attribute('type')}', "
                       f"id='{input_field.get_attribute('id')}', "
                       f"class='{input_field.get_attribute('class')}', "
                       f"name='{input_field.get_attribute('name')}', "
                       f"placeholder='{input_field.get_attribute('placeholder')}'")
        except:
            pass
    
    logger.info("ページソース:")
    logger.info(driver.page_source[:2000])  # より多くのページソースを表示
    logger.info("=== 状態確認終了 ===")

def update_titles():
    """タイトル更新の実行関数"""
    driver = None
    try:
        logger.info("=== 処理開始 ===")
        logger.info(f"設定されているプロジェクトID: {PROJECT_IDS}")
        logger.info(f"BASE_URL: {BASE_URL}")
        
        # 環境変数のチェック
        email = os.environ.get('WANTEDLY_EMAIL')
        password = os.environ.get('WANTEDLY_PASSWORD')
        
        if not email or not password:
            logger.error("必要な環境変数が設定されていません")
            logger.error(f"WANTEDLY_EMAIL: {'設定済み' if email else '未設定'}")
            logger.error(f"WANTEDLY_PASSWORD: {'設定済み' if password else '未設定'}")
            raise ValueError("必要な環境変数が設定されていません")
            
        logger.info(f"メールアドレス: {email[:3]}...{email[-10:]}")  # セキュリティのため一部のみ表示
        
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
        time.sleep(10)  # 待機時間を10秒に延長

        # メールアドレス入力フィールドを待機して入力
        logger.info("メールアドレス入力フィールドを待機中...")
        email_field = wait.until(EC.presence_of_element_located((By.ID, "email")))
        
        # JavaScriptを使用して値をセットし、イベントを発火
        driver.execute_script("""
            arguments[0].value = arguments[1];
            arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
            arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
        """, email_field, email)
        logger.info("JavaScriptでメールアドレスをセットし、イベントを発火させました")
        
        time.sleep(2)  # イベント処理待機
        
        # メールアドレス入力後の状態を確認
        log_page_state(driver, "メールアドレス入力後")
        
        try:
            # 次へボタンが有効になるまで待機
            next_button = wait.until(
                EC.element_to_be_clickable((By.ID, "next-step-button"))
            )
            logger.info("次へボタンが有効になりました")
            
            # JavaScriptでクリックイベントを発火
            driver.execute_script("arguments[0].click();", next_button)
            logger.info("次へボタンをクリックしました")
        except Exception as e:
            logger.error(f"次へボタンの処理中にエラーが発生: {str(e)}")
            log_page_state(driver, "次へボタン処理エラー")
            raise
        
        time.sleep(5)  # 画面遷移待機
        
        try:
            # パスワード入力フィールドの表示を待機
            wait_long = WebDriverWait(driver, 30)
            password_field = wait_long.until(
                EC.presence_of_element_located((By.ID, "password"))
            )
            
            # JavaScriptを使用してパスワードをセットし、イベントを発火
            driver.execute_script("""
                arguments[0].value = arguments[1];
                arguments[0].dispatchEvent(new Event('input', { bubbles: true }));
                arguments[0].dispatchEvent(new Event('change', { bubbles: true }));
            """, password_field, password)
            logger.info("JavaScriptでパスワードをセットし、イベントを発火させました")
            
            time.sleep(2)  # イベント処理待機
            
            # パスワード入力後の状態を確認
            log_page_state(driver, "パスワード入力後")
            
            # ログインボタンが有効になるまで待機
            login_button = wait_long.until(
                EC.element_to_be_clickable((By.ID, "next-step-button"))
            )
            logger.info("ログインボタンが有効になりました")
            
            # JavaScriptでクリックイベントを発火
            driver.execute_script("arguments[0].click();", login_button)
            logger.info("ログインボタンをクリックしました")
        except Exception as e:
            logger.error(f"パスワードフォームの処理中にエラーが発生: {str(e)}")
            log_page_state(driver, "パスワードフォーム処理エラー")
            raise

        # ログイン処理の完了を待機
        time.sleep(10)

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