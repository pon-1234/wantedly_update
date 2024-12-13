# Wantedly Update Automation

Wantedlyの求人情報を自動的に更新するCloud Runアプリケーション。

## セットアップ

1. 環境変数の設定
   - `.env.example`を`.env`にコピーし、必要な情報を入力
   ```bash
   cp .env.example .env
   ```

2. 仮想環境の作成とパッケージのインストール
   ```bash
   python -m venv venv
   source venv/bin/activate  # Windows: venv\Scripts\activate
   pip install -r requirements.txt
   ```

3. Cloud Runへのデプロイ
   ```bash
   gcloud run deploy wantedly-update \
     --source . \
     --region asia-northeast1 \
     --platform managed \
     --allow-unauthenticated \
     --set-env-vars WANTEDLY_EMAIL=your-email,WANTEDLY_PASSWORD=your-password,WANTEDLY_COMPANY_ID=your-company-id,GCP_PROJECT=your-project-id
   ```

## 使用方法

### 手動実行
```bash
curl -X POST https://[YOUR-SERVICE-URL]/update-wantedly
```

### ログの確認
```bash
gcloud logging read "resource.type=cloud_run_revision AND resource.labels.service_name=wantedly-update" --limit 20
```

## 環境変数

- `WANTEDLY_EMAIL`: Wantedlyログイン用メールアドレス
- `WANTEDLY_PASSWORD`: Wantedlyログイン用パスワード
- `WANTEDLY_COMPANY_ID`: 更新対象の企業ID
- `GCP_PROJECT`: GCPプロジェクトID

## 注意事項

- 環境変数は必ず設定してください
- デプロイ前にテストを実行することを推奨します
- エラーが発生した場合は、Cloud Runのログを確認してください

## ライセンス

MIT License 