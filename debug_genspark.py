"""Genspark メール取得デバッグスクリプト"""

from datetime import datetime
from fixed_costs import decode_base64, extract_text_from_payload, search_messages
from gmail_auth import get_gmail_service

SENDER = "invoice+statements+acct_1Q2SePHy7UpDvrVi@stripe.com"
TARGET_YEAR = 2026
TARGET_MONTHS = [1, 2, 3]


def get_message_detail(service, message_id: str) -> dict:
    return service.users().messages().get(userId="me", id=message_id, format="full").execute()


def get_headers(payload: dict) -> dict:
    return {h["name"]: h["value"] for h in payload.get("headers", [])}


def main():
    gmail_service = get_gmail_service()

    for month in TARGET_MONTHS:
        after_date = f"{TARGET_YEAR}/{month:02d}/01"
        before_date = f"{TARGET_YEAR}/{month + 1:02d}/01" if month < 12 else f"{TARGET_YEAR + 1}/01/01"
        query = f"from:{SENDER} after:{after_date} before:{before_date}"

        print(f"\n=== {month}月 ===")
        print(f"クエリ: {query}")

        messages = search_messages(gmail_service, query, max_results=5)
        print(f"ヒット件数: {len(messages)}")

        if not messages:
            # 日付なしで再検索して存在確認
            query_no_date = f"from:{SENDER}"
            all_msgs = search_messages(gmail_service, query_no_date, max_results=10)
            print(f"  → 日付フィルタなしでの全件: {len(all_msgs)} 件")
            for m in all_msgs[:3]:
                detail = get_message_detail(gmail_service, m["id"])
                headers = get_headers(detail.get("payload", {}))
                print(f"     件名: {headers.get('Subject', '(なし)')}")
                print(f"     日付: {headers.get('Date', '(なし)')}")
                print(f"     From: {headers.get('From', '(なし)')}")
            continue

        for msg in messages:
            detail = get_message_detail(gmail_service, msg["id"])
            payload = detail.get("payload", {})
            headers = get_headers(payload)
            body = extract_text_from_payload(payload)

            print(f"  件名: {headers.get('Subject', '(なし)')}")
            print(f"  日付: {headers.get('Date', '(なし)')}")
            print(f"  From: {headers.get('From', '(なし)')}")
            print(f"  本文 (先頭500文字):\n{body[:500]}")
            print("  ---")


if __name__ == "__main__":
    main()
