#!/usr/bin/env python3

import base64
import json
import re
from datetime import datetime
from pathlib import Path

from anthropic import Anthropic

from google_auth import load_config, get_sheets_service, get_spreadsheet_config


def process_receipt_image(image_data: bytes) -> tuple[str, str, str]:
    """
    Claude Vision API を使って領収書画像から金額・日付・店名を抽出
    
    Args:
        image_data: 画像のバイナリデータ
    
    Returns:
        (金額, 日付, 店名)
    """
    config = load_config()
    api_key = config.get("anthropic", {}).get("api_key")
    
    if not api_key:
        raise ValueError("config.json に anthropic.api_key を設定してください")

    client = Anthropic()

    # 画像を Base64 エンコード
    image_base64 = base64.standard_b64encode(image_data).decode("utf-8")

    prompt = """この領収書画像から以下の情報を抽出してください。

1. 金額（数字のみ、円記号なし）
2. 日付（YYYY-MM-DD形式）
3. 店舗名

JSON形式で以下のように返してください：
{
  "amount": "3500",
  "date": "2026-04-13",
  "shop_name": "〇〇レストラン"
}

情報が不明な場合は「UNKNOWN」と記入してください。
"""

    try:
        message = client.messages.create(
            model="claude-sonnet-4-5",
            max_tokens=1024,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/jpeg",
                                "data": image_base64,
                            },
                        },
                        {
                            "type": "text",
                            "text": prompt,
                        }
                    ],
                }
            ],
        )

        # レスポンスを抽出
        response_text = message.content[0].text

        # JSON を抽出
        json_match = re.search(r"\{[^}]+\}", response_text)
        if json_match:
            receipt_data = json.loads(json_match.group())
            amount = receipt_data.get("amount", "UNKNOWN")
            date = receipt_data.get("date", datetime.now().strftime("%Y-%m-%d"))
            shop_name = receipt_data.get("shop_name", "UNKNOWN")

            return amount, date, shop_name
        else:
            raise ValueError("Claude の応答から JSON を解析できませんでした")

    except Exception as e:
        raise RuntimeError(f"Claude Vision API エラー: {str(e)}")


def record_receipt(amount: str, date: str, shop_name: str) -> None:
    """
    領収書情報をスプレッドシートに記録
    """
    spreadsheet_id, sheet_name = get_spreadsheet_config()
    service = get_sheets_service()

    # 金額を数値に変換（カンマがあれば削除）
    amount_clean = amount.replace(",", "")

    row = [date, shop_name, amount_clean]

    # シート名を引用符で囲む
    sheet_range = f"'{sheet_name}'!A1"

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=sheet_range,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()


if __name__ == "__main__":
    # テスト用（実際のテストは LINE ボット経由）
    import sys

    if len(sys.argv) > 1:
        image_path = sys.argv[1]
        try:
            with open(image_path, "rb") as f:
                image_data = f.read()
            amount, date, shop_name = process_receipt_image(image_data)
            print(f"金額: ¥{amount}")
            print(f"日付: {date}")
            print(f"店名: {shop_name}")
        except Exception as e:
            print(f"エラー: {e}")
    else:
        print("使用方法: python line_receipt.py <image_path>")
