#!/usr/bin/env python3

import re
from datetime import datetime
from pathlib import Path

from google_auth import get_drive_service, load_config


def sanitize_filename(name: str) -> str:
    """ファイル名として使用できるように特殊文字を置換"""
    return re.sub(r"[^0-9A-Za-z一-龥ぁ-んァ-ン_\-\. ]", "_", name)


def ensure_directory_structure(drive_service, root_folder_name: str, year: str, month: str, category: str = "その他") -> str:
    """
    Google Drive に以下の構造でディレクトリを作成：
    {root_folder_name}/{year}/{month}/{category}/{service_name}_{year}{month}.pdf
    
    Returns:
        作成先フォルダの ID
    """
    def find_or_create_folder(parent_id: str, folder_name: str) -> str:
        """フォルダが存在すれば ID を返し、なければ作成して返す"""
        escaped_name = folder_name.replace("'", "\\'")
        query = f"name = '{escaped_name}' and mimeType = 'application/vnd.google-apps.folder'"
        if parent_id:
            query += f" and '{parent_id}' in parents"

        response = drive_service.files().list(
            q=query,
            spaces="drive",
            fields="files(id, name)"
        ).execute()

        files = response.get("files", [])
        if files:
            return files[0]["id"]

        # フォルダが存在しないから作成
        metadata = {
            "name": folder_name,
            "mimeType": "application/vnd.google-apps.folder",
        }
        if parent_id:
            metadata["parents"] = [parent_id]

        folder = drive_service.files().create(body=metadata, fields="id").execute()
        return folder["id"]

    # ディレクトリ階層を作成
    root_id = find_or_create_folder(None, root_folder_name)
    year_id = find_or_create_folder(root_id, year)
    month_id = find_or_create_folder(year_id, month)
    category_id = find_or_create_folder(month_id, category)

    return category_id


def download_pdf(url: str) -> bytes:
    """URL から PDF をダウンロード"""
    import requests

    response = requests.get(url, timeout=20)
    response.raise_for_status()
    return response.content


def upload_receipt_pdf(
    drive_service,
    pdf_data: bytes,
    filename: str,
    folder_id: str,
) -> str:
    """
    PDF を Google Drive にアップロード
    
    Returns:
        Google Drive ファイルのリンク
    """
    from googleapiclient.http import MediaFileUpload
    import io

    file_metadata = {
        "name": filename,
        "parents": [folder_id],
    }

    # メモリからのアップロード
    media = MediaFileUpload(
        io.BytesIO(pdf_data),
        mimetype="application/pdf",
        resumable=True
    )

    file = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id,webViewLink"
    ).execute()

    return file.get("webViewLink", "")


def save_receipt(
    service_name: str,
    pdf_url: str,
    category: str = "その他"
) -> str:
    """
    PDF 領収書を Google Drive に保存
    
    Args:
        service_name: サービス名（例：「Genspark」）
        pdf_url: PDF の URL
        category: カテゴリ（例：「サブスク」「コンサル」）
    
    Returns:
        Google Drive リンク
    """
    drive_service = get_drive_service()
    config = load_config()

    try:
        # PDF をダウンロード
        pdf_data = download_pdf(pdf_url)

        # ディレクトリ構造を確認・作成
        year = datetime.now().strftime("%Y")
        month = datetime.now().strftime("%m")
        receipt_root = config.get("drive", {}).get("receipt_root_folder_name", "経費領収書")

        folder_id = ensure_directory_structure(drive_service, receipt_root, year, month, category)

        # ファイル名を作成
        filename = sanitize_filename(f"{service_name}_{year}{month}.pdf")

        # Google Drive にアップロード
        link = upload_receipt_pdf(drive_service, pdf_data, filename, folder_id)

        return link

    except Exception as e:
        raise RuntimeError(f"領収書の保存に失敗しました: {str(e)}")


if __name__ == "__main__":
    # テスト用（実際の使用は gmail_integration.py から呼び出し）
    import sys

    if len(sys.argv) > 2:
        service_name = sys.argv[1]
        pdf_url = sys.argv[2]
        category = sys.argv[3] if len(sys.argv) > 3 else "その他"

        try:
            link = save_receipt(service_name, pdf_url, category)
            print(f"保存完了: {link}")
        except Exception as e:
            print(f"エラー: {e}")
    else:
        print("使用方法: python save_receipt.py <service_name> <pdf_url> [category]")
