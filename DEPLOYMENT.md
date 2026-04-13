# デプロイメント ガイド

## 📋 目次

1. [Windows 固定費自動入力（Task Scheduler）](#windows-固定費自動入力task-scheduler)
2. [Linux/macOS Cron 設定](#linuxmacos-cron-設定)
3. [Railway へのLINE ボット デプロイ](#railway-へのline-ボット-デプロイ-ガイド)
4. [Render でのデプロイ（代替案）](#render-でのデプロイ代替案)
5. [トラブルシューティング](#トラブルシューティング)

---

## Windows 固定費自動入力（Task Scheduler）

毎月1日の9時に固定費を自動入力する場合の設定方法です。

### ステップ 1: タスクスケジューラを開く
- Windows キーを押して「タスクスケジューラ」を検索
- 「タスクスケジューラ」を起動

### ステップ 2: 基本タスクを作成
1. 左ペインで「タスク スケジューラル ライブラリ」を選択
2. 右ペインで「基本タスクの作成」をクリック
3. 名前：`ExpenseAutomation_FixedCosts`
4. 説明：`Monthly fixed expenses auto-input on 1st of month`
5. 「次へ」をクリック

### ステップ 3: トリガーを設定
1. 「トリガー」で「毎月」を選択
2. 日付を「1」に設定
3. 時刻を「09:00:00」に設定
4. 「次へ」をクリック

### ステップ 4: アクションを設定
1. 「操作」で「プログラムの開始」を選択
2. プログラムまたはスクリプト：
   ```
   C:\Users\m94ka_\AppData\Local\Programs\Python\Python313\python.exe
   ```
3. 引数を追加：
   ```
   C:\Users\m94ka_\expense-automation\fixed_costs.py
   ```
4. 開始場所（オプション）：
   ```
   C:\Users\m94ka_\expense-automation
   ```
5. 「次へ」をクリック

### ステップ 5: 完了
1. 「完了」をクリック
2. 管理者権限で実行する場合は、作成されたタスクを右クリック → プロパティ → 「セキュリティオプション」で「最上位の特権で実行」をチェック

---

## Linux/macOS Cron 設定

毎月1日の9時に固定費を自動入力する場合：

```bash
0 9 1 * * cd /path/to/expense-automation && /usr/bin/python3 fixed_costs.py
```

crontab に追加する手順：

1. `crontab -e` を実行
2. 上記行をファイルの末尾に追加
3. ファイルを保存して終了

---

# Railway へのLINE ボット デプロイ ガイド

Railwayへのデプロイは最も簡単で、推奨される方法です。

## 前提条件

- ✅ GitHub アカウント（コードを push する）
- ✅ Railway アカウント（https://railway.app）
- ✅ LINE Messaging API 認証情報
  - Channel ID
  - Channel Secret
  - Channel Access Token
  - User ID

---

## ステップ 1: GitHub にリポジトリをプッシュ

まず、プロジェクトを GitHub にアップロードします。

```bash
# プロジェクトディレクトリに移動
cd C:\Users\m94ka_\expense-automation

# Git を初期化（未初期化の場合）
git init

# リモートリポジトリを追加
git remote add origin https://github.com/your-username/expense-automation.git

# ブランチを作成・移動
git checkout -b main

# ファイルをステージング
git add .

# コミット
git commit -m "Initial commit: Expense automation system"

# プッシュ
git push -u origin main
```

**⚠️ 重要**: `config.json`、`gmail_token.json`、`*.json` クレデンシャルファイルは `.gitignore` に登録されているため、プッシュされません。これはセキュリティのためです。Railway では環境変数で設定します。

---

## ステップ 2: Railway アカウントを作成

1. `https://railway.app` にアクセス
2. **「GitHub で登録」** をクリック
3. GitHub 認可画面で「Authorize」を選択
4. Railway へのアクセスを許可
5. メールアドレスを確認し、ダッシュボードへ

---

## ステップ 3: Railway で新規プロジェクトを作成

### 3-1: 新規プロジェクトを作成

1. Railway ダッシュボードで **「New Project」** をクリック
2. **「Deploy from GitHub repo」** を選択

### 3-2: GitHub リポジトリを連携

1. **「Install Railway on GitHub」** をクリック
2. GitHub リポジトリアクセス許可画面で：
   - 「Only select repositories」を選択
   - `expense-automation` リポジトリを選択 → 「Install」
3. Railway に戻り、リポジトリリストから `expense-automation` を選択

### 3-3: デプロイを開始

Rail way が自動でデプロイを開始します。ビルドログを確認してください。

---

## ステップ 4: Procfile を作成してコミット

Railway が Flask アプリを正しく起動するための `Procfile` を作成します。

### 4-1: Procfile を作成

プロジェクトルートに `Procfile` という名前のファイルを作成：

```
web: python line_bot.py
```

### 4-2: Git にコミット・プッシュ

```bash
# Git にステージング
git add Procfile requirements.txt

# コミット
git commit -m "Add Procfile for Railway deployment"

# プッシュ（自動で Railway でリデプロイが開始される）
git push
```

---

## ステップ 5: 環境変数を設定

Railway プロジェクトページで各APIキーを設定します。**この部分が重要です。**

### 5-1: Variables ページを開く

1. Railway プロジェクトダッシュボード
2. **「Variables」** タブをクリック
3. **「+ Add Variable」** をクリック

### 5-2: 環境変数を追加

以下の環境変数を **すべて** 追加してください：

#### Google 認証関連

| キー | 値 |
|------|-----|
| `GOOGLE_SERVICE_ACCOUNT_JSON` | `expense-automation-493207-678d0e3e8531.json` の内容全体（JSON テキスト） |
| `GOOGLE_SHEETS_SPREADSHEET_ID` | `1fTNFOH4oNUO1RwNqUib0tb5Nvfxmp2PKfAWMIkcbYes` |
| `GOOGLE_SHEETS_EXPENSE_SHEET_NAME` | `経費帳` |
| `GOOGLE_MAPS_API_KEY` | `YOUR_GOOGLE_MAPS_API_KEY`（Google Cloud Console から取得） |

#### Gmail 認証関連

| キー | 値 |
|------|-----|
| `GMAIL_CREDENTIALS_FILE` | `./gmail_client_secret.json` |
| `GMAIL_TOKEN_FILE` | `./gmail_token.json` |

#### LINE API 認証

| キー | 値 |
|------|-----|
| `LINE_CHANNEL_ID` | `2009783040` |
| `LINE_CHANNEL_SECRET` | `YOUR_LINE_CHANNEL_SECRET`（LINE Developers Console から取得） |
| `LINE_CHANNEL_ACCESS_TOKEN` | `YOUR_LINE_CHANNEL_ACCESS_TOKEN`（LINE Developers Console から取得） |
| `LINE_USER_ID` | `YOUR_LINE_USER_ID`（LINE ユーザーID） |

#### Anthropic API

| キー | 値 |
|------|-----|
| `ANTHROPIC_API_KEY` | `YOUR_ANTHROPIC_API_KEY`（Anthropic Dashboard から取得） |

#### 為替レート API

| キー | 値 |
|------|-----|
| `EXCHANGE_RATE_API_KEY` | `YOUR_EXCHANGERATE_API_KEY`（exchangerate-api.com から取得） |

#### Yahoo Transit API（オプション）

| キー | 値 |
|------|-----|
| `YAHOO_TRANSIT_CLIENT_ID` | `YOUR_YAHOO_TRANSIT_CLIENT_ID` |

#### 基本設定

| キー | 値 |
|------|-----|
| `PORT` | `5000` |
| `FLASK_ENV` | `production` |

---

## ステップ 6: デプロイの確認

### 6-1: デプロイログを確認

1. Railway ダッシュボード → 「Deployments」 タブ
2. ビルドログを確認：
   ```
   ✓ 依存関係のインストール (requirements.txt)
   ✓ Flask サーバーの起動
   ```
3. デプロイが完了すると、アプリケーション URL が表示される
   - 例：`https://expense-automation-production.up.railway.app`

### 6-2: 実際に動作確認

```bash
# テストでWebhook URL にアクセス
curl https://expense-automation-production.up.railway.app/

# 正常なら以下のようなレスポンスが返される
# <!DOCTYPE HTML> ... 400 Bad Request ...
```

---

## ステップ 7: LINE Webhook URL を設定

### 7-1: LINE Developers Console にアクセス

1. LINE Developers Console (https://developers.line.biz/console/) にログイン
2. チャネルを選択
3. 左メニュー → **「Messaging API」** → **「設定」**

### 7-2: Webhook URL を登録

1. **「Webhook URL」** の欄に以下を入力：
   ```
   https://expense-automation-production.up.railway.app/callback
   ```
   （Railway での実際のアプリケーション URL に置き換え）

2. **「Verify」** ボタンをクリック

3. 下記のように表示されれば成功：
   ```
   ✅ Webhook URL is valid
   ```

### 7-3: Webhook の有効化

1. **「Webhook の利用」** を **「有効」** に設定
2. **「保存」** をクリック

---

## ステップ 8: LINE ボットをテスト

LINE の友達追加QRコードからボットを追加し、テストしてください：

### テスト 1: 交通費入力

```
送信: 渋谷→新宿 会社

期待される返答:
----------------
ルート: 渋谷 → 新宿
訪問先: 会社
推定運賃: ¥210
記録日時: 2026-04-13 14:30:00
```

### テスト 2: 領収書 OCR

```
送信: 領収書の写真（PNG or JPG）

期待される返答:
----------------
金額: ¥3,500
日付: 2026-04-13
店舗: レストラン ABC

記録しますか？
[記録] [キャンセル]
```

---

## ステップ 9: 本番環境での Gmail 認可（オプション）

Gmail 機能を使う場合、初回は OAuth 認可が必要です。

### 方法 A: Railway SSH 接続（上級ユーザー向け）

```bash
# Railway CLI をインストール
npm install -g @railway/cli

# SSH接続
railway connect

# Gmail 認可を実行
python gmail_auth.py

# ブラウザで認可画面が開いたら、Gmail を認可
# gmail_token.json が生成される
```

### 方法 B: ローカルで実行（簡易方法）

```bash
# ローカルで Gmail 認可を完了
python gmail_auth.py

# gmail_token.json を Git に追加
git add gmail_token.json
git commit -m "Add gmail token for production"
git push

# Railway が自動でリデプロイ
```

---

## Railway トラブルシューティング

| 問題 | 原因 | 解決策 |
|------|------|------|
| **Build failed** エラー | `requirements.txt` が不正または Python バージョン不一致 | 1. `requirements.txt` を確認<br>2. `python -m pip list` で依存関係を確認<br>3. Railway ビルドログで詳細を確認 |
| **ポート接続エラー (P10013)** | Flask が正しいポートをバインドしていない | 環境変数で `PORT=5000` が設定されているか確認 |
| **Webhook verification failed** | Webhook URL または Channel Secret が不正 | 1. Webhook URL を確認（Railway URL と一致）<br>2. LINE Channel Secret を確認<br>3. 環境変数が正しく設定されているか確認 |
| **アプリが停止する** | クラッシュまたはメモリ不足 | 1. Railway ダッシュボード → Deployments でログ確認<br>2. エラーメッセージを検索<br>3. Metrics でメモリ使用量を確認 |
| **LINE メッセージに応答しない** | LINE アクセストークンが無効または Webhook が実行されていない | 1. LINE Channel Access Token を確認<br>2. Railway ログで `POST /callback` が記録されているか確認<br>3. `line_bot.py` にエラーがないか確認 |

---

## Railway ダッシュボードの見方

### ログを確認する

1. Railway プロジェクト → **「Deployments」**
2. 最新のデプロイメントをクリック
3. **「Logs」** タブでリアルタイムログを確認

### 環境変数を編集する

1. Railway プロジェクト → **「Variables」**
2. 各変数を修正して **「Save」**
3. 自動でリデプロイが開始される

### アプリを再起動する

1. Railway プロジェクト → **「Settings」**
2. **「Restart」** ボタンをクリック

---

## Render でのデプロイ（代替案）

**Render は Railway よりセットアップが少し複雑ですが、こちらも選択肢として機能します。**

### Render セットアップ手順

#### ステップ 1: render.yaml ファイルを作成

プロジェクトルートに `render.yaml` を作成：

```yaml
services:
  - type: web
    name: expense-automation
    runtime: python311
    buildCommand: "pip install -r requirements.txt"
    startCommand: "gunicorn line_bot:app"
    envVars:
      - key: PORT
        value: 5000
      - key: FLASK_ENV
        value: production
```

#### ステップ 2: requirements.txt に gunicorn を追加

```bash
pip install gunicorn
echo "gunicorn==21.2.0" >> requirements.txt
git add requirements.txt render.yaml
git commit -m "Add Render deployment config"
git push
```

#### ステップ 3: Render でプロジェクト作成

1. `https://render.com` にアクセス → GitHub でサインアップ
2. **「New → Web Service」** をクリック
3. **「Connect a repository」** → `expense-automation` を選択
4. 設定：
   - **Name**: `expense-automation`
   - **Environment**: Python 3.11
   - **Build Command**: `pip install -r requirements.txt`
   - **Start Command**: `gunicorn line_bot:app`
   - **Plan**: Free（または Pro）
5. Railway と同じ環境変数をすべて追加
6. **「Create Web Service」** をクリック

---

## デプロイ後の確認チェックリスト

```
□ GitHub にコードがプッシュされているか確認
□ Railway で「Deploy」が成功したか確認（Deployments ログ）
□ 環境変数がすべて設定されているか確認
□ Webhook URL が LINE Developers Console に登録されているか
□ LINE で「Verify」が成功したか確認（✅ Webhook URL is valid）
□ LINE ボットに交通費メッセージを送ってテスト
□ LINE ボットに領収書画像を送ってテスト
□ Google Sheets にデータが記録されるか確認
□ Railway ログでエラーが出ていないか確認
```

---

## よくある質問（FAQ）

### Q: 環境変数が多すぎて設定が大変です
**A:** コピペで設定できます。`config.json` のテンプレートから値をコピーして Railway に貼り付けてください。

### Q: GitHub に秘密鍵をコミットしたくありません
**A:** `.gitignore` に登録されているため、自動的にコミットされません。安全です。

### Q: Railway の無料プランの制限は？
**A:** 月 5 ドルのクレジットが提供されます。LINE ボットは低トラフィックなら無料で実行できます。

### Q: デプロイ後、コードを変更したら？
**A:** Git にコミット・プッシュするだけで、Railway が自動でリデプロイします。

---

## サポート・問題報告

- **Railway サポート**: https://railway.app/support
- **LINE Developer Support**: https://developers.line.biz/support/
- **GitHub Issues**: プロジェクトの Issue タブで報告
