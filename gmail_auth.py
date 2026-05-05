import json
import os
from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

from google_auth import load_config

GMAIL_SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly"
]


def get_gmail_credentials():
    # CI / GitHub Actions: 環境変数からトークン JSON を直接読み込む
    token_json = os.getenv("GMAIL_TOKEN_JSON")
    if token_json:
        creds = Credentials.from_authorized_user_info(json.loads(token_json), GMAIL_SCOPES)
        if creds.expired and creds.refresh_token:
            creds.refresh(Request())
        return creds

    config = load_config()
    gmail_config = config.get("gmail", {})
    credentials_file = gmail_config.get("credentials_file")
    token_file = gmail_config.get("token_file", "./gmail_token.json")

    if not credentials_file:
        raise ValueError("config.json の gmail.credentials_file を設定してください。")

    credentials_path = Path(credentials_file)
    if not credentials_path.exists():
        raise FileNotFoundError(
            f"Gmail OAuth クライアントシークレットファイルが見つかりません: {credentials_path}"
        )

    creds = None
    token_path = Path(token_file)
    if token_path.exists():
        creds = Credentials.from_authorized_user_file(str(token_path), GMAIL_SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(
                str(credentials_path), GMAIL_SCOPES
            )
            creds = flow.run_local_server(port=0)

        with open(token_path, "w", encoding="utf-8") as token_file_handle:
            token_file_handle.write(creds.to_json())

    return creds


def get_gmail_service():
    credentials = get_gmail_credentials()
    return build("gmail", "v1", credentials=credentials)


if __name__ == "__main__":
    service = get_gmail_service()
    profile = service.users().getProfile(userId="me").execute()
    print("Gmail OAuth の認可が完了しました。")
    print(f"認可済みユーザー: {profile.get('emailAddress')}")
