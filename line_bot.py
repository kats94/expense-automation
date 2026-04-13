#!/usr/bin/env python3

import logging
import os
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
from line_transit import get_transit_fare
from line_receipt import process_receipt_image

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)

config = load_config()
line_config = config.get("line", {})

line_bot_api = LineBotApi(line_config.get("channel_access_token"))
handler = WebhookHandler(line_config.get("channel_secret"))

# ユーザーの状態管理（簡易）
user_states = {}


@app.route("/callback", methods=["POST"])
def callback():
    """LINE Webhook のエンドポイント"""
    signature = request.headers.get("X-Line-Signature", "")
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        logger.warning("Invalid signature received.")
        abort(400)
    except Exception as e:
        logger.error(f"Error handling message: {e}")
        abort(500)

    return "OK"


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """テキストメッセージの処理"""
    user_id = event.source.user_id
    text = event.message.text.strip()

    # 交通費入力：「出発地→目的地 訪問先」形式
    if "→" in text and " " in text:
        parts = text.split(" ", 1)
        route = parts[0]  # 出発地→目的地
        location = parts[1]  # 訪問先

        try:
            fare, route_info = get_transit_fare(route)
            # スプレッドシートに追加（後で実装）
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
            TextSendMessage(text="領収書を送信するか、「出発地→目的地 訪問先」の形式で交通費を入力してください。")
        )


@handler.add(MessageEvent, message=ImageMessage)
def handle_image_message(event):
    """画像メッセージ（領収書）の処理"""
    user_id = event.source.user_id
    message_id = event.message.id

    try:
        # 画像をダウンロード
        message_content = line_bot_api.get_message_content(message_id)
        image_data = message_content.content

        # Claude Vision API で推定
        amount, date, shop = process_receipt_image(image_data)

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
    except Exception as e:
        logger.error(f"Error processing receipt image: {e}")
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
