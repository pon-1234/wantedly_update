# Wantedly Title Update Automation

このプロジェクトは、Wantedlyの求人情報を自動的に更新するためのCloud Run上で動作する自動化システムです。

## 機能

- Wantedly管理画面への自動ログイン
- 指定された求人情報の自動更新
- Cloud Schedulerによる定期実行
- Secret Managerを使用した認証情報の安全な管理

## 技術スタック

- Python 3.10
- Selenium
- Google Cloud Platform
  - Cloud Run
  - Cloud Scheduler
  - Secret Manager
- Docker

## セットアップ

1. 必要な環境変数の設定
```bash
export WANTEDLY_EMAIL="your-email@example.com"
export WANTEDLY_PASSWORD="your-password"
export PROJECT_IDS="id1,id2,id3"  # カンマ区切りで複数指定可能
```

2. 依存パッケージのインストール
```bash
pip install -r requirements.txt
```

3. ローカルでの実行
```bash
python main.py
```

## GCPへのデプロイ

1. GCPプロジェクトの設定
```bash
gcloud config set project your-project-id
```

2. Secret Managerでの認証情報の設定
```bash
gcloud secrets create wantedly-credentials --data-file=credentials.json
```

3. Cloud Runへのデプロイ
```bash
gcloud builds submit
```

4. Cloud Schedulerの設定
```bash
gcloud scheduler jobs create http wantedly-title-update \
  --schedule="0 */6 * * *" \
  --uri="your-cloud-run-url" \
  --http-method=POST \
  --location=asia-northeast1
```

## 注意事項

- 実行前に必ずWantedlyの利用規約を確認してください
- 認証情報は適切に管理してください
- 更新頻度は適切な間隔を設定してください

## ライセンス

MIT License 