import json
from datetime import datetime
from pathlib import Path

import requests
from google_auth import get_sheets_service, get_spreadsheet_config, load_config


def get_exchange_rate(api_key: str, base: str = "USD", target: str = "JPY") -> float:
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


def month_column_letter(month: int) -> str:
    if not 1 <= month <= 12:
        raise ValueError("Month must be between 1 and 12")
    return chr(ord("A") + month)


def find_row_by_item(values: list[list[str]], item_name: str) -> int | None:
    for row_index, row in enumerate(values, start=1):
        if row and row[0].strip() == item_name:
            return row_index
    return None


def update_sheet_values(spreadsheet_id: str, sheet_name: str, updates: list[dict]):
    service = get_sheets_service()
    sheet = service.spreadsheets().values()
    for update in updates:
        sheet.values().update(
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
    result = sheet.get(spreadsheetId=spreadsheet_id, range=f"'{sheet_name}'!A1:N100").execute()
    return result.get("values", [])


def build_row_for_item(item_name: str, month_index: int, amount: str, memo: str | None = None) -> list[str]:
    row = [""] * 14
    row[0] = item_name
    row[month_index] = amount
    if memo:
        row[13] = memo
    return row


def main():
    config = load_config()
    spreadsheet_id, sheet_name = get_spreadsheet_config()
    exchange_api_key = config["exchange_rate_api"]["api_key"]
    current_month = datetime.now().month

    exchange_rate = get_exchange_rate(exchange_api_key, base="USD", target="JPY")
    chatgpt_jpy = round(22 * exchange_rate)
    chatgpt_memo = f"USD 22 @ {exchange_rate:.6f} = JPY {chatgpt_jpy}"

    items = [
        {"name": "お名前.com メールサーバー費用", "amount": "1911", "memo": None},
        {"name": "PIC", "amount": "5500", "memo": None},
        {"name": "NIC（初回交流会込み）", "amount": "13000", "memo": None},
        {"name": "代理店交流会", "amount": "5500", "memo": None},
        {"name": "ChatGPT Plus", "amount": str(chatgpt_jpy), "memo": chatgpt_memo},
    ]

    values = load_sheet_data(spreadsheet_id, sheet_name)
    updates = []

    for item in items:
        row_index = find_row_by_item(values, item["name"])
        column = month_column_letter(current_month)
        if row_index is not None:
            updates.append({"range": f"'{sheet_name}'!{column}{row_index}", "values": [item["amount"]]})
            if item["memo"]:
                updates.append({"range": f"'{sheet_name}'!N{row_index}", "values": [item["memo"]]})
        else:
            new_row = build_row_for_item(item["name"], current_month, item["amount"], item["memo"])
            append_new_row(spreadsheet_id, sheet_name, new_row)

    if updates:
        update_sheet_values(spreadsheet_id, sheet_name, updates)

    print("固定費の自動入力が完了しました。")
    print(f"ChatGPT Plus の換算レート: {exchange_rate:.6f}")


if __name__ == "__main__":
    main()
