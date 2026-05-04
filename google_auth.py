import json
import os
import base64
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build

SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def load_config():
    """環境変数からconfig を読み込む"""
    config = {
        "google": {
            "spreadsheet_id": os.getenv("GOOGLE_SPREADSHEET_ID"),
            "expense_sheet_name": os.getenv("GOOGLE_EXPENSE_SHEET_NAME", "経費帳"),
            "service_account_file": os.getenv("GOOGLE_SERVICE_ACCOUNT_FILE", "./expense-automation-493207-678d0e3e8531.json"),
        },
        "google_maps": {
            "api_key": os.getenv("GOOGLE_MAPS_API_KEY"),
        },
        "exchange_rate_api": {
            "api_key": os.getenv("EXCHANGERATE_API_KEY"),
        },
        "gmail": {
            "credentials_file": os.getenv("GMAIL_CREDENTIALS_FILE", "./gmail_client_secret.json"),
            "token_file": os.getenv("GMAIL_TOKEN_FILE", "./gmail_token.json"),
        },
        "anthropic": {
            "api_key": os.getenv("ANTHROPIC_API_KEY"),
        },
        "yahoo": {
            "transit_api_client_id": os.getenv("YAHOO_TRANSIT_CLIENT_ID"),
        },
        "line": {
            "channel_id": os.getenv("LINE_CHANNEL_ID"),
            "channel_secret": os.getenv("LINE_CHANNEL_SECRET"),
            "channel_access_token": os.getenv("LINE_CHANNEL_ACCESS_TOKEN"),
            "user_id": os.getenv("LINE_USER_ID"),
        },
        "drive": {
            "receipt_root_folder_name": os.getenv("DRIVE_RECEIPT_ROOT_FOLDER_NAME", "経費領収書"),
        },
    }
    
    # ローカル開発環境ではconfig.jsonを読み込む
    config_path = Path(__file__).parent / "config.json"
    if config_path.exists():
        with open(config_path, "r", encoding="utf-8") as f:
            local_config = json.load(f)
            # 環境変数が設定されていない場合のみローカルconfigを使用
            if not os.getenv("GOOGLE_SPREADSHEET_ID"):
                config.update(local_config)
    
    return config


def get_service_account_credentials():
    config = load_config()
    service_account_file = config["google"].get("service_account_file")
    
    if not service_account_file:
        raise ValueError("GOOGLE_SERVICE_ACCOUNT_FILE 環境変数を設定してください。")

    credentials_path = Path(service_account_file)
    if not credentials_path.exists():
        raise FileNotFoundError(
            f"サービスアカウントの認証ファイルが見つかりません: {credentials_path}"
        )

    return service_account.Credentials.from_service_account_file(
        filename=str(credentials_path), scopes=SCOPES
    )


def get_sheets_service():
    credentials = get_service_account_credentials()
    return build("sheets", "v4", credentials=credentials)


def get_drive_service():
    credentials = get_service_account_credentials()
    return build("drive", "v3", credentials=credentials)


def get_spreadsheet_config():
    config = load_config()
    google_config = config.get("google", {})
    spreadsheet_id = google_config.get("spreadsheet_id")
    sheet_name = google_config.get("expense_sheet_name", "経費")

    if not spreadsheet_id:
        raise ValueError("GOOGLE_SPREADSHEET_ID 環境変数を設定してください。")

    return spreadsheet_id, sheet_name


if __name__ == "__main__":
    service = get_sheets_service()
    spreadsheet_id, sheet_name = get_spreadsheet_config()
    print("Google Sheets API の認証が完了しました。")
    print(f"Spreadsheet ID: {spreadsheet_id}")
    print(f"Sheet name: {sheet_name}")
