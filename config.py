import os

# デフォルト設定
DEFAULT_CONFIG = {
    'PROJECT_IDS': [
        '1821510',  # 現在のプロジェクトID
        # 他のプロジェクトIDをここに追加
    ],
    'BASE_URL': 'https://admin.wantedly.com',
    'LOGIN_WAIT_TIME': 30,  # ログイン待機時間（秒）
}

# 環境変数から設定を読み込む
def get_config(key):
    env_key = f'WANTEDLY_{key}'
    if env_key in os.environ:
        # PROJECT_IDSの場合はカンマ区切りの文字列をリストに変換
        if key == 'PROJECT_IDS':
            return os.environ[env_key].split(',')
        return os.environ[env_key]
    return DEFAULT_CONFIG[key]

# 設定値をエクスポート
PROJECT_IDS = get_config('PROJECT_IDS')
BASE_URL = get_config('BASE_URL')
LOGIN_WAIT_TIME = int(get_config('LOGIN_WAIT_TIME')) 