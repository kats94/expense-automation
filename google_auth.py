import json
from pathlib import Path
from google.oauth2 import service_account
from googleapiclient.discovery import build

CONFIG_PATH = Path(__file__).parent / "config.json"
SCOPES = [
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/drive",
]


def load_config():
    if not CONFIG_PATH.exists():
        raise FileNotFoundError(
            f"config.json が見つかりません。{CONFIG_PATH} を作成し、Google サービスアカウント情報を設定してください。"
        )
    with open(CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)


def get_service_account_credentials():
    config = load_config()
    service_account_file = config["google"].get("service_account_file")
    if not service_account_file:
        raise ValueError("config.json の google.service_account_file を設定してください。")

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
        raise ValueError("config.json の google.spreadsheet_id を設定してください。")

    return spreadsheet_id, sheet_name


if __name__ == "__main__":
    service = get_sheets_service()
    spreadsheet_id, sheet_name = get_spreadsheet_config()
    print("Google Sheets API の認証が完了しました。")
    print(f"Spreadsheet ID: {spreadsheet_id}")
    print(f"Sheet name: {sheet_name}")
