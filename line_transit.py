#!/usr/bin/env python3

import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime

import requests

from google_auth import load_config, get_sheets_service, get_spreadsheet_config

TRANSIT_SEARCH_ENDPOINT = "https://transit.yahooapis.jp/TransitSearch/V1/search"


def parse_route(route_text: str) -> tuple[str, str]:
    """
    「出発地→目的地」形式をパース
    例: 「渋谷→新宿」-> ("渋谷", "新宿")
    """
    if "→" not in route_text:
        raise ValueError("ルートは「出発地→目的地」の形式で指定してください")

    parts = route_text.split("→")
    if len(parts) != 2:
        raise ValueError("ルートは「出発地→目的地」の形式で指定してください")

    origin = parts[0].strip()
    destination = parts[1].strip()

    if not origin or not destination:
        raise ValueError("出発地と目的地を入力してください")

    return origin, destination


def load_yahoo_client_id() -> str:
    config = load_config()
    client_id = os.getenv("YAHOO_TRANSIT_CLIENT_ID") or config.get("yahoo", {}).get("transit_api_client_id")
    if not client_id:
        raise ValueError("YAHOO_TRANSIT_CLIENT_ID 環境変数を設定してください")
    return client_id


def parse_yahoo_transit_response(body: bytes) -> tuple[int, str]:
    root = ET.fromstring(body)

    error = root.find("Error")
    if error is not None:
        message = error.text.strip() if error.text else "Yahoo!乗換案内APIでエラーが発生しました"
        raise ValueError(message)

    price_node = root.find("Result/Route/Price") or root.find("Result/Route/Fare") or root.find("Result/Route/Charge")
    if price_node is None or not price_node.text:
        raise ValueError("Yahoo!乗換案内APIで運賃が取得できませんでした")

    fare_text = re.sub(r"[^0-9]", "", price_node.text)
    fare = int(fare_text) if fare_text else 0

    line_names = []
    for line in root.findall("Result/Route/Line"):
        name = line.findtext("Name") or line.findtext("name")
        if name:
            line_names.append(name.strip())

    route_info = ", ".join(line_names) if line_names else "Yahoo!乗換案内APIでの経路"
    return fare, route_info


def get_transit_fare(route_text: str) -> tuple[int, str]:
    """
    Yahoo!乗換案内APIを使って交通費（電車）を取得

    Args:
        route_text: 「出発地→目的地」形式のテキスト

    Returns:
        (運賃（円）, ルート情報)
    """
    origin, destination = parse_route(route_text)
    client_id = load_yahoo_client_id()

    params = {
        "appid": client_id,
        "from": origin,
        "to": destination,
        "sort": "time",
        "results": 1,
    }

    try:
        response = requests.get(TRANSIT_SEARCH_ENDPOINT, params=params, timeout=10)
        response.raise_for_status()
        fare, route_info = parse_yahoo_transit_response(response.content)
        return fare, route_info
    except requests.RequestException as e:
        raise RuntimeError(f"Yahoo!乗換案内APIへのリクエストに失敗しました: {e}")
    except ET.ParseError as e:
        raise RuntimeError(f"Yahoo!乗換案内APIレスポンスの解析に失敗しました: {e}")


def record_transit_expense(origin: str, destination: str, location: str, fare: int) -> None:
    """
    交通費をスプレッドシートに記録
    """
    spreadsheet_id, sheet_name = get_spreadsheet_config()
    service = get_sheets_service()

    today = datetime.now().strftime("%Y-%m-%d")
    row = [today, origin, destination, location, str(fare)]

    sheet_range = f"'{sheet_name}'!A1"

    service.spreadsheets().values().append(
        spreadsheetId=spreadsheet_id,
        range=sheet_range,
        valueInputOption="USER_ENTERED",
        insertDataOption="INSERT_ROWS",
        body={"values": [row]},
    ).execute()


if __name__ == "__main__":
    try:
        client_id = load_yahoo_client_id()
        print(f"Yahoo! Transit API client id loaded: {client_id[:8]}...")
        fare, info = get_transit_fare("渋谷→新宿")
        print(f"運賃: ¥{fare}")
        print(f"ルート情報: {info}")
    except Exception as e:
        print(f"エラー: {e}")
