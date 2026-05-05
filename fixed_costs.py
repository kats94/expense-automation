import json
from datetime import datetime
from pathlib import Path

import requests
from google_auth import get_sheets_service, get_spreadsheet_config, load_config


def get_exchange_rate(api_key: str, base: str = "USD", target: str = "JPY", on_date: str | None = None) -> float:
    if on_date:
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/history/{base}/{on_date}"
    else:
        url = f"https://v6.exchangerate-api.com/v6/{api_key}/latest/{base}"

    response = requests.get(url, timeout=10)
    response.raise_for_status()
    data = response.json()
    if data.get("result") != "success":
        raise RuntimeError(f"Exchange rate API error: {data}")

    rate = data["conversion_rates"].get(target)
    if rate is None:
        raise ValueError(f"Unable to get exchange rate for {target}")
    return float(rate)


def get_12th_exchange_rate(api_key: str, base: str = "USD", target: str = "JPY") -> float:
    today = datetime.now()
    target_date = today.replace(day=12).strftime("%Y-%m-%d")
    try:
        return get_exchange_rate(api_key, base=base, target=target, on_date=target_date)
    except Exception as exc:
        print(f"12日レートの取得に失敗しました: {exc}. 最新レートにフォールバックします。")
        return get_exchange_rate(api_key, base=base, target=target)


def month_column_letter(month: int) -> str:
    if not 1 <= month <= 12:
        raise ValueError("Month must be between 1 and 12")
    return chr(ord("A") + month)


def find_row_by_item(values: list[list[str]], item_name: str) -> int | None:
    for row_index, row in enumerate(values, start=1):
        if row and row[0].strip() == item_name:
            return row_index
    return None


def update_sheet_values(spreadsheet_id: str, updates: list[dict]):
    service = get_sheets_service()
    sheet = service.spreadsheets().values()
    for update in updates:
        sheet.update(
            spreadsheetId=spreadsheet_id,
            range=update["range"],
            valueInputOption="USER_ENTERED",
            body={"values": [update["values"]]},
        ).execute()


def append_new_row(spreadsheet_id: str, sheet_name: str, row: list[str]):
    service = get_sheets_service()
    sheet = service.spreadsheets().values()
    sheet.append(
        spreadsheetId=spreadsheet_id,
        range=f"'{sheet_name}'!A1",
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()


def load_sheet_data(spreadsheet_id: str, sheet_name: str) -> list[list[str]]:
    service = get_sheets_service()
    sheet = service.spreadsheets().values()
    result = sheet.get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!A1:N200").execute()
    return result.get("values", [])


def build_row_for_item(item_name: str, month_index: int, amount: str, memo: str | None = None) -> list[str]:
    row = [""] * 14
    row[0] = item_name
    row[month_index] = amount
    if memo:
        row[13] = memo
    return row


def update_fixed_cost_item(spreadsheet_id: str, sheet_name: str, values: list[list[str]], item_name: str, amount: str, memo: str | None = None, target_month: int = 4) -> None:
    row_index = find_row_by_item(values, item_name)
    column = month_column_letter(target_month)
    if row_index:
        updates = [{"range": f"'{sheet_name}'!{column}{row_index}", "values": [amount]}]
        if memo:
            updates.append({"range": f"'{sheet_name}'!N{row_index}", "values": [memo]})
        update_sheet_values(spreadsheet_id, updates)
    else:
        row = build_row_for_item(item_name, target_month, amount, memo)
        append_new_row(spreadsheet_id, sheet_name, row)


def main():
    config = load_config()
    spreadsheet_id, sheet_name = get_spreadsheet_config("fixed_cost_sheet_name")
    exchange_api_key = config["exchange_rate_api"]["api_key"]

    values = load_sheet_data(spreadsheet_id, sheet_name)

    # USD建て請求書の為替は請求日（毎月12日）のレートを優先
    exchange_rate_12th = get_12th_exchange_rate(exchange_api_key, base="USD", target="JPY")

    items = [
        {
            "sender": "invoice+statements+acct_1Q2SePHy7UpDvrVi@stripe.com",
            "item_name": "Genspark",
            "currency": "USD",
            "query_suffix": "",
        },
        {
            "sender": "invoice+statements@mail.anthropic.com",
            "item_name": "Claude",
            "currency": "USD",
            "query_suffix": "",
        },
        {
            "sender": "server@onamae-support.jp",
            "item_name": "メールサーバー費用",
            "currency": "JPY",
            "query_suffix": "",
        },
    ]

    target_month = 4
    target_year = 2026

    for invoice in items:
        try:
            print(f"処理開始: {invoice['item_name']}")
            process_invoice(
                spreadsheet_id,
                sheet_name,
                invoice["sender"],
                invoice["item_name"],
                invoice["currency"],
                exchange_api_key,
                exchange_rate_12th=exchange_rate_12th,
                target_month=target_month,
                target_year=target_year,
            )
            print(f"処理完了: {invoice['item_name']}")
        except Exception as exc:
            print(f"{invoice['item_name']} の処理中にエラーが発生しました: {exc}")

    print("メール自動取得処理を完了しました")

    fixed_amount_items = [
        {"name": "メールサーバー費用", "amount": "1911"},
        {"name": "代理店交流会", "amount": "5500"},
        {"name": "PIC", "amount": "5500"},
        {"name": "NIC（初回交流会込み）", "amount": "13000"},
    ]

    for item in fixed_amount_items:
        update_fixed_cost_item(
            spreadsheet_id,
            sheet_name,
            values,
            item["name"],
            item["amount"],
            target_month=4,
        )

    chatgpt_amount = str(round(22 * exchange_rate_12th))
    chatgpt_memo = f"USD 22 @ {exchange_rate_12th:.6f} = JPY {chatgpt_amount}"
    update_fixed_cost_item(
        spreadsheet_id,
        sheet_name,
        values,
        "ChatGPT",
        chatgpt_amount,
        chatgpt_memo,
        target_month=4,
    )

    print("固定費の自動入力が完了しました。")
    print(f"ChatGPT の換算レート: {exchange_rate_12th:.6f}")


def parse_amount_jpy(text: str) -> float | None:
    import re

    match = re.search(r"¥\s*([0-9,]+(?:\.[0-9]+)?)", text)
    if match:
        return float(match.group(1).replace(",", ""))
    return None


def parse_amount_usd(text: str) -> float | None:
    import re

    match = re.search(r"\$\s*([0-9,]+(?:\.[0-9]+)?)", text)
    if not match:
        match = re.search(r"USD\s*([0-9,]+(?:\.[0-9]+)?)", text, re.IGNORECASE)
    if match:
        return float(match.group(1).replace(",", ""))
    return None


def normalize_text(data: str) -> str:
    return data.replace("\r", "\n").replace("\n\n", "\n").strip()


def decode_base64(data: str) -> str:
    import base64

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


from gmail_auth import get_gmail_service


def get_message_text(service, message_id: str) -> str:
    try:
        message = service.users().messages().get(userId="me", id=message_id, format="full").execute()
        payload = message.get("payload", {})
        return normalize_text(extract_text_from_payload(payload))
    except Exception as e:
        print(f"メール本文取得エラー: {e}")
        return ""


def search_messages(service, query: str, max_results: int = 1):
    try:
        response = service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
        return response.get("messages", [])
    except Exception as e:
        print(f"メール検索エラー: {e}")
        return []


def process_invoice(
    spreadsheet_id: str,
    sheet_name: str,
    sender: str,
    item_name: str,
    currency: str,
    exchange_api_key: str,
    exchange_rate_12th: float,
    target_month: int = 4,
    target_year: int | None = None,
) -> None:
    if target_year is None:
        target_year = datetime.now().year
    # 対象月の開始日・翌月1日でフィルタ（当月メールのみ取得）
    after_date = f"{target_year}/{target_month:02d}/01"
    if target_month == 12:
        before_date = f"{target_year + 1}/01/01"
    else:
        before_date = f"{target_year}/{target_month + 1:02d}/01"
    gmail_service = get_gmail_service()
    query = f"from:{sender} after:{after_date} before:{before_date}"
    messages = search_messages(gmail_service, query)
    if not messages:
        print(f"未検出: {item_name} の請求メール ({sender})")
        return

    message_id = messages[0]["id"]
    body_text = get_message_text(gmail_service, message_id)

    amount_value = None
    memo = None
    if currency == "USD":
        usd_amount = parse_amount_usd(body_text)
        if usd_amount is None:
            print(f"{item_name} の USD 金額を抽出できませんでした。")
            return
        jpy_amount = round(usd_amount * exchange_rate_12th)
        amount_value = str(jpy_amount)
        memo = f"USD {usd_amount} @ {exchange_rate_12th:.6f} = JPY {jpy_amount}"
    else:
        jpy_amount = parse_amount_jpy(body_text)
        if jpy_amount is None:
            print(f"{item_name} の JPY 金額を抽出できませんでした。")
            return
        amount_value = str(int(jpy_amount))
        memo = f"JPY {int(jpy_amount)}"

    update_fixed_cost_item(spreadsheet_id, sheet_name, values=load_sheet_data(spreadsheet_id, sheet_name), item_name=item_name, amount=amount_value, memo=memo, target_month=4)
    print(f"{item_name} を {amount_value} 円で更新しました。")


if __name__ == "__main__":
    main()
