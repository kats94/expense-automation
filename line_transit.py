#!/usr/bin/env python3

import re
from datetime import datetime
from pathlib import Path

import googlemaps
import requests

from google_auth import load_config, get_sheets_service, get_spreadsheet_config


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


def get_transit_fare(route_text: str) -> tuple[int, str]:
    """
    Google Maps API を使って交通費（電車）を取得
    
    Args:
        route_text: 「出発地→目的地」形式のテキスト
    
    Returns:
        (運賃（円）, ルート情報）
    """
    origin, destination = parse_route(route_text)

    # Google Maps API 初期化
    config = load_config()
    google_maps_api_key = config.get("google_maps", {}).get("api_key")
    
    if not google_maps_api_key:
        raise ValueError("config.json に google_maps.api_key を設定してください")

    gmaps = googlemaps.Client(key=google_maps_api_key)

    try:
        # 最安経路を取得（transit mode）
        result = gmaps.directions(
            origin=origin,
            destination=destination,
            mode="transit",
            departure_time="now",
            language="ja"
        )

        if not result:
            raise ValueError(f"ルートが見つかりません: {origin} → {destination}")

        # 最初のルートを取得
        route = result[0]
        legs = route.get("legs", [])

        if not legs:
            raise ValueError("ルート情報が不完全です")

        leg = legs[0]
        duration = leg.get("duration", {}).get("text", "N/A")
        steps_info = []

        # 各ステップの情報を集約
        for step in leg.get("steps", []):
            if step.get("transit_details"):
                transit = step["transit_details"]
                line = transit.get("line", {}).get("name", "不明")
                steps_info.append(line)

        route_info = ", ".join(steps_info) if steps_info else "N/A"

        # 注：Google Maps API からは直接運賃を取得できないため、
        # ここでは固定値または外部 API を使用（例：ジョルダンAPI）
        fare = estimate_fare(origin, destination)

        return fare, f"{route_info} ({duration})"

    except googlemaps.exceptions.TransitRouteNotFound:
        raise ValueError(f"公共交通機関のルートが見つかりません: {origin} → {destination}")
    except Exception as e:
        raise RuntimeError(f"ルート検索エラー: {str(e)}")


def estimate_fare(origin: str, destination: str) -> int:
    """
    簡易的な運賃推定
    実際には NAVITIME API や ジョルダン API を使用することを推奨
    """
    # 仮の実装：距離ベース推定
    # より正確な運賃が必要な場合は、
    # NAVITIME API や ジョルダン API と連携してください
    config = load_config()
    gmaps_api_key = config.get("google_maps", {}).get("api_key")

    if not gmaps_api_key:
        return 0  # デフォルト値

    gmaps = googlemaps.Client(key=gmaps_api_key)

    try:
        result = gmaps.distance_matrix(
            origins=[origin],
            destinations=[destination],
            mode="transit"
        )

        if result["status"] != "OK":
            return 0

        distance_text = result["rows"][0]["elements"][0].get("distance", {}).get("text", "")
        
        # 距離から運賃を推定（東京近郊ICカード基準の簡易値）
        # 1km未満: 170円、2km: 190円、3km: 210円...
        distance_match = re.search(r"(\d+)", distance_text)
        if distance_match:
            distance_km = int(distance_match.group(1))
            if distance_km <= 1:
                return 170
            elif distance_km <= 2:
                return 190
            elif distance_km <= 3:
                return 210
            else:
                return 170 + (distance_km - 1) * 30
        return 210  # デフォルト

    except Exception as e:
        print(f"Distance estimation error: {e}")
        return 210  # デフォルト値


def record_transit_expense(origin: str, destination: str, location: str, fare: int) -> None:
    """
    交通費をスプレッドシートに記録
    """
    spreadsheet_id, sheet_name = get_spreadsheet_config()
    service = get_sheets_service()

    # シートにデータを追加
    today = datetime.now().strftime("%Y-%m-%d")
    row = [today, origin, destination, location, str(fare)]

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
    # テスト
    try:
        config = load_config()
        if not config.get("google_maps", {}).get("api_key"):
            print("config.json に google_maps.api_key を設定してください")
        else:
            fare, info = get_transit_fare("渋谷→新宿")
            print(f"運賃: ¥{fare}")
            print(f"ルート情報: {info}")
    except Exception as e:
        print(f"エラー: {e}")
