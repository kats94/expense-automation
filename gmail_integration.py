import base64
import json
import re
from datetime import datetime
from email import message_from_bytes
from pathlib import Path
from urllib.parse import urlparse

import requests
from googleapiclient.http import MediaFileUpload
from googleapiclient.discovery import build

from google_auth import get_drive_service, get_sheets_service, get_spreadsheet_config, load_config
from gmail_auth import get_gmail_service


def normalize_text(data: str) -> str:
    return data.replace("\r", "\n").replace("\n\n", "\n").strip()


def decode_base64(data: str) -> str:
    text = base64.urlsafe_b64decode(data.encode("utf-8"))
    return text.decode("utf-8", errors="ignore")


def extract_text_from_payload(payload: dict) -> str:
    body = payload.get("body", {})
    data = body.get("data")
    if data:
        return decode_base64(data)

    parts = payload.get("parts", [])
    texts = []
    for part in parts:
        part_text = extract_text_from_payload(part)
        if part_text:
            texts.append(part_text)
    return "\n".join(texts)


def get_message_text(service, message_id: str) -> str:
    message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
    payload = message.get("payload", {})
    return normalize_text(extract_text_from_payload(payload))


def search_messages(service, query: str, max_results: int = 1):
    response = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    return response.get("messages", [])


def parse_amount_jpy(text: str) -> float | None:
    match = re.search(r"¥\s*([0-9,]+(?:\.[0-9]+)?)", text)
    if match:
        return float(match.group(1).replace(",", ""))
    return None


def parse_amount_usd(text: str) -> float | None:
    match = re.search(r"\$\s*([0-9,]+(?:\.[0-9]+)?)", text)
    if not match:
        match = re.search(r"USD\s*([0-9,]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    if match:
        return float(match.group(1).replace(",", ""))
    return None


def extract_pdf_urls(text: str) -> list[str]:
    return re.findall(r"https?://[^\s\"]+\.pdf", text)


def get_exchange_rate(api_key: str, base: str = "USD", target: str = "JPY") -> float:
    url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/{base}"
    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
    if data.get("result") != "success":
        raise RuntimeError(f"Exchange rate API error: {data}")
    rate = data["conversion_rates"].get(target)
    if rate is None:
        raise ValueError(f"Exchange rate for {target} not found")
    return float(rate)


def month_column_letter(month: int) -> str:
    if month < 1 or month > 12:
        raise ValueError("Month must be 1-12")
    return chr(ord("A") + month)


def find_row_by_item(values: list[list[str]], item_name: str) -> int | None:
    for index, row in enumerate(values, start=1):
        if row and row[0].strip() == item_name:
            return index
    return None


def load_sheet_data(spreadsheet_id: str, sheet_name: str) -> list[list[str]]:
    service = get_sheets_service()
    result = service.spreadsheets().values().get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!A1:N200").execute()
    return result.get("values", [])


def update_sheet_values(spreadsheet_id: str, updates: list[dict]):
    service = get_sheets_service()
    for update in updates:
        service.spreadsheets().values().update(
            spreadsheetId=spreadsheet_id,
            range=update["range"],
            valueInputOption="USER_ENTERED",
            body={"values": [update["values"]]},
        ).execute()


def append_new_row(spreadsheet_id: str, sheet_name: str, row: list[str]):
    service = get_sheets_service()
    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()


def sanitize_filename(name: str) -> str:
    return re.sub(r"[^0-9A-Za-z一-龥ぁ-んァ-ン_\-\. ]", "_", name)


def ensure_drive_folder(drive_service, parent_id: str, name: str) -> str:
    escaped_name = name.replace("'", "\\'")
    query = f"name = '{escaped_name}' and mimeType = 'application/vnd.google-apps.folder'"
    if parent_id:
        query += f" and '{parent_id}' in parents"
    response = drive_service.files().list(q=query, spaces="drive", fields="files(id,name)").execute()
    files = response.get("files", [])
    if files:
        return files[0]["id"]

    metadata = {
        "name": name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    if parent_id:
        metadata["parents"] = [parent_id]

    folder = drive_service.files().create(body=metadata, fields="id").execute()
    return folder["id"]


def upload_pdf_to_drive(drive_service, local_path: Path, root_folder_name: str, year: str, month: str, service_name: str) -> dict:
    root_folder_id = ensure_drive_folder(drive_service, None, root_folder_name)
    year_folder_id = ensure_drive_folder(drive_service, root_folder_id, year)
    month_folder_id = ensure_drive_folder(drive_service, year_folder_id, month)

    file_metadata = {
        "name": local_path.name,
        "parents": [month_folder_id],
    }
    media = MediaFileUpload(str(local_path), mimetype="application/pdf")
    uploaded = drive_service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id,webViewLink"
    ).execute()
    return uploaded


def download_file(url: str, destination: Path) -> None:
    response = requests.get(url, timeout=20)
    response.raise_for_status()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with open(destination, "wb") as f:
        f.write(response.content)


def update_invoice_sheet(spreadsheet_id: str, sheet_name: str, item_name: str, amount: str, memo: str | None = None) -> None:
    values = load_sheet_data(spreadsheet_id, sheet_name)
    row_index = find_row_by_item(values, item_name)
    current_month = datetime.now().month
    column = month_column_letter(current_month)
    updates = []

    if row_index:
        updates.append({"range": f"'{sheet_name}'!{column}{row_index}", "values": [amount]})
        if memo:
            updates.append({"range": f"'{sheet_name}'!N{row_index}", "values": [memo]})
        if updates:
            update_sheet_values(spreadsheet_id, updates)
    else:
        row = [""] * 14
        row[0] = item_name
        row[current_month] = amount
        if memo:
            row[13] = memo
        append_new_row(spreadsheet_id, sheet_name, row)


def process_invoice(email_service, drive_service, spreadsheet_id: str, sheet_name: str, sender: str, item_name: str, currency: str, query_suffix: str = "") -> None:
    query = f"from:{sender} {query_suffix}".strip()
    messages = search_messages(email_service, query)
    if not messages:
        print(f"未検出: {item_name} の請求メール ({sender})")
        return

    message_id = messages[0]["id"]
    body_text = get_message_text(email_service, message_id)
    invoice_date = datetime.now().strftime("%Y-%m-%d")
    try:
        message = email_service.users().messages().get(userId="me", id=message_id, format="metadata", metadataHeaders=["Date"]).execute()
        headers = message.get("payload", {}).get("headers", [])
        for header in headers:
            if header.get("name") == "Date":
                invoice_date = header.get("value")
                break
    except Exception:
        pass

    amount_value = None
    memo = None
    if currency == "USD":
        usd_amount = parse_amount_usd(body_text)
        if usd_amount is None:
            print(f"{item_name} の USD 金額を抽出できませんでした。")
            return
        exchange_rate = get_exchange_rate(load_config()["exchange_rate_api"]["api_key"], base="USD", target="JPY")
        jpy_amount = round(usd_amount * exchange_rate)
        amount_value = str(jpy_amount)
        memo = f"USD {usd_amount} @ {exchange_rate:.6f} = JPY {jpy_amount}"
    else:
        jpy_amount = parse_amount_jpy(body_text)
        if jpy_amount is None:
            print(f"{item_name} の JPY 金額を抽出できませんでした。")
            return
        amount_value = str(int(jpy_amount))
        memo = f"JPY {int(jpy_amount)}"

    update_invoice_sheet(spreadsheet_id, sheet_name, item_name, amount_value, memo)
    print(f"{item_name} を {amount_value} 円で更新しました。")

    pdf_urls = extract_pdf_urls(body_text)
    if not pdf_urls:
        print(f"{item_name} の PDF URL が見つかりませんでした。")
        return

    pdf_url = pdf_urls[0]
    receipt_root = load_config()["drive"]["receipt_root_folder_name"]
    year = datetime.now().strftime("%Y")
    month = datetime.now().strftime("%m")
    file_name = sanitize_filename(f"{item_name}_{year}{month}.pdf")
    local_path = Path("./tmp_receipts") / year / month / file_name
    download_file(pdf_url, local_path)
    upload_result = upload_pdf_to_drive(drive_service, local_path, receipt_root, year, month, item_name)
    print(f"{item_name} の領収書を Google Drive に保存しました: {upload_result.get('webViewLink')}")


def main():
    config = load_config()
    spreadsheet_id, sheet_name = get_spreadsheet_config()
    gmail_service = get_gmail_service()
    drive_service = get_drive_service()

    invoices = [
        {
            "sender": "invoice+statements+acct_1Q2SePHy7UpDvrVi@stripe.com",
            "item_name": "Genspark（MainFunc PTE. LTD.）",
            "currency": "USD",
            "query_suffix": "",
        },
        {
            "sender": "invoice+statements@mail.anthropic.com",
            "item_name": "Claude Pro（Anthropic, PBC）",
            "currency": "USD",
            "query_suffix": "",
        },
        {
            "sender": "server@onamae-support.jp",
            "item_name": "お名前.com メールサーバー費用",
            "currency": "JPY",
            "query_suffix": "",
        },
    ]

    for invoice in invoices:
        process_invoice(
            gmail_service,
            drive_service,
            spreadsheet_id,
            sheet_name,
            invoice["sender"],
            invoice["item_name"],
            invoice["currency"],
            invoice["query_suffix"],
        )


if __name__ == "__main__":
    main()
