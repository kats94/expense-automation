#!/usr/bin/env python3

import logging
import os
import re
from functools import wraps

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, ImageMessage, TextSendMessage, 
    ConfirmTemplate, MessageAction, TemplateSendMessage,
    ButtonsTemplate, DatetimePickerAction
)

from google_auth import load_config
from line_transit import get_transit_fare, record_transit_expense, parse_route
from line_receipt import process_receipt_image

logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

app = Flask(__name__)

config = load_config()
line_config = config.get("line", {})

line_bot_api = LineBotApi(line_config.get("channel_access_token"))
handler = WebhookHandler(line_config.get("channel_secret"))

# ユーザーの状態管理（簡易）
user_states = {}


@app.route("/webhook", methods=["POST"])
def webhook():
    """LINE Webhook のエンドポイント"""
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    logger.info(f"Received webhook request. Signature: {signature[:20]}...")
    logger.debug(f"Webhook body: {body[:200]}")

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.warning("Invalid signature received.")
        abort(400)
    except Exception as e:
        logger.error(f"Error handling message: {e}", exc_info=True)
        abort(500)

    return "OK", 200


def parse_transit_input(text: str) -> tuple[str, str, int] | tuple[str, str] | None:
    """出発地→目的地 訪問先形式の入力を解析する。金額が含まれている場合は金額も返す"""
    # 全角スペースも含めて分割
    parts = re.split(r"\s+", text.strip())
    if len(parts) < 2:
        return None

    route = parts[0].strip()
    if "→" not in route:
        return None

    # 金額を含む場合の処理
    fare = None
    location = None

    for part in parts[1:]:
        # 金額を検索（数字 + 円）
        fare_match = re.search(r"(\d+)円?", part)
        if fare_match:
            fare = int(fare_match.group(1))
        elif location is None:
            location = part.strip()

    if location is None:
        return None

    if fare is not None:
        return route, location, fare
    else:
        return route, location


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """テキストメッセージの処理"""
    user_id = event.source.user_id
    text = event.message.text.strip()
    logger.info(f"TextMessage received from {user_id}: {text}")

    transit_input = parse_transit_input(text)
    if transit_input:
        if len(transit_input) == 3:
            # 金額が含まれている場合
            route, location, fare = transit_input
            try:
                origin, destination = parse_route(route)
                record_transit_expense(origin, destination, location, fare)
                response_text = f"¥{fare} を交通費に入力しました✅\n{route} {location}"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=response_text))
            except Exception as e:
                logger.error(f"Error recording transit expense: {e}")
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=f"交通費の記録に失敗しました: {str(e)}")
                )
        else:
            # 金額が含まれていない場合（従来のAPI使用）
            route, location = transit_input
            try:
                fare, route_info = get_transit_fare(route)
                origin, destination = parse_route(route)
                record_transit_expense(origin, destination, location, fare)
                response_text = f"¥{fare} を交通費に入力しました✅\n{route_info}"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=response_text))
            except Exception as e:
                logger.error(f"Error getting transit fare: {e}")
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=f"交通費の計算に失敗しました: {str(e)}")
                )
    else:
        # その他のテキストメッセージ
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="領収書を送信するか、「出発地→目的地 訪問先」または「出発地→目的地 金額 訪問先」の形式で交通費を入力してください。")
        )


@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    """画像メッセージ（領収書）の処理"""
    user_id = event.source.user_id
    message_id = event.message.id
    logger.info(f"ImageMessage received from {user_id}. Message ID: {message_id}")

    try:
        logger.debug(f"Downloading image content for message {message_id}")
        # 画像をダウンロード
        message_content = line_bot_api.get_message_content(message_id)
        image_data = message_content.content
        logger.debug(f"Image downloaded successfully. Size: {len(image_data)} bytes")

        # Claude Vision API で推定
        logger.debug("Processing image with Claude Vision API")
        amount, date, shop = process_receipt_image(image_data)
        logger.info(f"Receipt processed: amount={amount}, date={date}, shop={shop}")

        # 確認メッセージをテンプレートで送信
        confirm_text = f"¥{amount} / {date} / {shop}\nで合っていますか？"

        buttons_template = ButtonsTemplate(
            text=confirm_text,
            actions=[
                MessageAction(label="はい", text="領収書_確認_yes"),
                MessageAction(label="修正", text="領収書_確認_no"),
            ]
        )
        line_bot_api.reply_message(
            event.reply_token,
            TemplateSendMessage(alt_text=confirm_text, template=buttons_template)
        )

        # ユーザーの状態を保存
        user_states[user_id] = {
            "receipt_amount": amount,
            "receipt_date": date,
            "receipt_shop": shop,
        }
        logger.info(f"User state saved for {user_id}")
    except Exception as e:
        logger.error(f"Error processing receipt image: {e}", exc_info=True)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"領収書の読み取りに失敗しました: {str(e)}")
        )


@app.route("/health", methods=["GET"])
def health_check():
    """ヘルスチェック"""
    return {"status": "ok"}, 200


if __name__ == "__main__":
    PORT = os.getenv("PORT", 5000)
    app.run(host="0.0.0.0", port=int(PORT), debug=False)
