# 経費管理自動化システム

Google Sheets、Gmail、Google Drive、LINE、および外部APIを統合した包括的な経費管理自動化システムです。

## 📋 実装済み機能（全7個）

✅ **固定費の自動入力**: 毎月1日に自動で定期費用をシートに登録  
✅ **Gmail請求書抽出**: Genspark、Claude Pro、お名前.comからの請求書を自動取得  
✅ **USD→JPY変換**: 請求金額をリアルタイム為替レートで自動変換  
✅ **LINE交通費入力**: 「渋谷→新宿 会社」形式で交通費を計算・記録  
✅ **LINE領収書OCR**: Claude Vision APIで画像から金額・日付・店舗を自動抽出  
✅ **PDF自動保存**: 領収書PDFをGoogle Driveに自動保存（年月ごとのフォルダ整理）  
✅ **Cron自動スケジューリング**: Windows Task Scheduler またはLinux cronで自動実行  

## 🚀 セットアップ手順

### 1. 依存関係をインストール
```bash
pip install -r requirements.txt
```

### 2. 設定ファイルを作成
```bash
cp config.example.json config.json
```

### 3. Google Cloud認証設定

#### 3.1 Google Sheets API & Drive API を有効化
1. [Google Cloud Console](https://console.cloud.google.com/) を開く
2. プロジェクトを作成（または既存プロジェクトを使用）
3. 「APIs と サービス」 > 「ライブラリ」で以下のAPIを検索して有効化：
   - Google Sheets API
   - Google Drive API
4. サービスアカウントを作成：
   - 「認証情報」 > 「認証情報を作成」 > 「サービスアカウント」
   - JSON キーをダウンロード
5. ダウンロードしたJSON キーを `expense-automation-493207-678d0e3e8531.json` に保存

#### 3.2 Google Sheets/Drive に権限設定
- [Google Sheets](https://docs.google.com/spreadsheets) を開く
- 対象のシートを開く
- サービスアカウントメール（例：`expense-automation-493207@xxx.iam.gserviceaccount.com`）を エディターとして共有

#### 3.3 Gmail API を有効化
1. Google Cloud Console で Gmail API を有効化
2. OAuth 2.0 クライアント ID を作成：
   - 「認証情報」 > 「作成」 > 「OAuth クライアント ID」
   - アプリケーションの種類：「デスクトップアプリ」
3. JSON をダウンロードして `gmail_client_secret.json` に保存
4. 初回実行時にブラウザで認可（自動で `gmail_token.json` が生成される）

### 4. API キーを config.json に設定

```json
{
  "google": {
    "service_account_file": "expense-automation-493207-678d0e3e8531.json",
    "spreadsheet_id": "YOUR_SPREADSHEET_ID",
    "expense_sheet_name": "経費帳"
  },
  "google_maps": {
    "api_key": "YOUR_GOOGLE_MAPS_API_KEY"
  },
  "anthropic": {
    "api_key": "YOUR_DEEPSEEK_API_KEY"
  },
  "line": {
    "channel_access_token": "YOUR_LINE_CHANNEL_ACCESS_TOKEN",
    "channel_secret": "YOUR_LINE_CHANNEL_SECRET",
    "user_id": "YOUR_LINE_USER_ID"
  }
}
```

## 📁 ファイル構成

```
expense-automation/
├── google_auth.py              # Google Sheets/Drive API認証
├── gmail_auth.py               # Gmail OAuth2認証
├── gmail_integration.py         # Gmail請求書自動抽出
├── fixed_costs.py              # 固定費自動入力
├── line_bot.py                 # LINE bot Flaskサーバー
├── line_transit.py             # LINE交通費計算機能
├── line_receipt.py             # LINE領収書OCR機能（Claude Vision）
├── save_receipt.py             # PDF領収書Google Drive保存機能
├── config.json                 # 認証情報・API キー設定（.gitignoreに含める）
├── config.example.json         # 設定ファイルテンプレート
├── requirements.txt            # Python依存関係
├── DEPLOYMENT.md               # Cron/Task Scheduler デプロイ手順
└── README.md                   # このファイル
```

## 🔧 各機能の使用方法

### 1. 固定費の自動入力
```bash
python fixed_costs.py
```
毎月のサーバー維持費・ChatGPT Plus等を自動登録します。  
Cron/Task Scheduler で毎月1日 09:00 に実行してください。

### 2. Gmail請求書の自動抽出
```bash
python gmail_integration.py
```
以下のサービスから請求書を自動抽出：
- Genspark（Stripe経由）
- Claude Pro（Anthropic）
- お名前.com

### 3. LINE bot の起動
```bash
python line_bot.py
```
ポート 5000 で Flask サーバーが起動します。LINE webhook URL を設定してください。

**LINE bot の使用方法:**
- **交通費入力**: `渋谷→新宿 会社`
- **領収書OCR**: 領収書画像を送信 → OCR処理 → 金額・日付・店舗自動抽出

### 4. Cron/Task Scheduler の設定

Windows Task Scheduler または Linux cron で自動実行を設定してください。  
詳細は [DEPLOYMENT.md](DEPLOYMENT.md) を参照。

## 🐛 トラブルシューティング

### 「モジュールが見つかりません」エラー
```bash
pip install -r requirements.txt
```
を実行後、Python を再起動してください。

### 「認証に失敗しました」エラー
- `config.json` に API キーが正しく設定されているか確認
- Google Cloud Console で API が有効になっているか確認
- サービスアカウント/ユーザーに適切な権限があるか確認

### LINE bot が応答しない
- `LINE webhook URL` が正しく設定されているか確認
- `line_bot.py` が正常に起動しているか確認（ログを確認）
- Channel Secret / Channel Access Token が正しいか確認

## 📝 ログとデバッグ

各スクリプトはコンソール出力でデバッグ情報を表示します。  
より詳細なログが必要な場合は以下を追加：

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## 🌐 デプロイ

### Railway へのデプロイ（推奨）
1. [Railway](https://railway.app) にサインアップ
2. `config.json` の情報を環境変数として設定
3. `Procfile` を作成：
   ```
   web: python line_bot.py
   ```
4. デプロイ実行

詳細は [DEPLOYMENT.md](DEPLOYMENT.md) 参照。

## 📚 参考資料

- [Google Sheets API](https://developers.google.com/sheets/api)
- [Gmail API](https://developers.google.com/gmail/api)
- [LINE Messaging API](https://developers.line.biz/ja/services/messaging-api/)
- [Claude API](https://docs.anthropic.com/)
- [Google Maps API](https://developers.google.com/maps)

## ⚠️ セキュリティに関する注意

- `config.json` は絶対に Git リポジトリにコミットしないでください（`.gitignore` に登録済み）
- API キーは環境変数での管理をお勧めします
- .json 認証ファイルを公開リポジトリにアップロードしないで

## 🎯 今後の改善予定

- [ ] Yahoo！乗換案内API の統合（より正確な交通費計算）
- [ ] 増税対応・カテゴリ別集計レポート機能
- [ ] Slack 通知機能
- [ ] Web UI ダッシュボード

---

**License:** MIT
