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
from line_receipt import process_receipt_image, record_receipt

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


def _prompt_correction_fields(event, state):
    prompt_text = (
        "修正する項目を番号で入力してください（複数可、例：1 3）\n"
        "1. 日付\n"
        "2. 店名\n"
        "3. 金額"
    )
    state["mode"] = "select_fields"
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=prompt_text))


def _prompt_next_field(event, state):
    pending_fields = state.get("pending_fields", [])
    index = state.get("pending_index", 0)
    if index >= len(pending_fields):
        return False

    field = pending_fields[index]
    labels = {
        "date": "日付（YYYY-MM-DD形式）を入力してください。",
        "shop": "店名を入力してください。",
        "amount": "金額（数字のみ）を入力してください。",
    }
    state["mode"] = "editing"
    state["current_field"] = field
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=labels[field]))
    return True


@handler.add(MessageEvent, message=TextMessage)
def handle_text_message(event):
    """テキストメッセージの処理"""
    user_id = event.source.user_id
    text = event.message.text.strip()
    logger.info(f"TextMessage received from {user_id}: {text}")

    state = user_states.get(user_id, {})
    mode = state.get("mode")

    if mode == "confirm_transit":
        logger.info(f"Transit confirmation from {user_id}: {text}")
        selected = text.strip()
        if selected in ["1", "片道"]:
            amount = int(state["fare"])
            record_amount = amount
            label = "片道"
        elif selected in ["2", "往復"]:
            amount = int(state["fare"]) * 2
            record_amount = amount
            label = "往復"
        else:
            reply_text = (
                "「片道」または「往復」を入力してください。\n"
                "1. 片道\n"
                "2. 往復"
            )
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply_text))
            return

        try:
            record_transit_expense(
                state["origin"],
                state["destination"],
                state["location"],
                record_amount,
            )
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"¥{record_amount}（{label}）を交通費（電車）まとめに入力しました✅")
            )
        except Exception as e:
            logger.error(f"Error recording transit expense: {e}", exc_info=True)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"交通費の記録に失敗しました: {str(e)}")
            )
        finally:
            user_states.pop(user_id, None)
        return

    if mode == "select_fields":
        logger.info(f"Receipt field selection from {user_id}: {text}")
        field_numbers = re.findall(r"[1-3]", text)
        if not field_numbers:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="1〜3の番号をスペース区切りで入力してください。例：1 3")
            )
            return

        field_map = {"1": "date", "2": "shop", "3": "amount"}
        pending_fields = [field_map[num] for num in field_numbers]
        state["pending_fields"] = pending_fields
        state["pending_index"] = 0
        state["mode"] = "editing"
        user_states[user_id] = state
        _prompt_next_field(event, state)
        return

    if mode == "editing":
        current_field = state.get("current_field")
        logger.info(f"Receipt edit input for {user_id}: field={current_field}, text={text}")
        if current_field == "date":
            state["receipt_date"] = text
        elif current_field == "shop":
            state["receipt_shop"] = text
        elif current_field == "amount":
            amount_text = re.sub(r"[^0-9]", "", text)
            if not amount_text:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="金額は数字のみで入力してください。例：2450")
                )
                return
            state["receipt_amount"] = amount_text
        else:
            logger.warning(f"Unknown current_field for {user_id}: {current_field}")

        pending_index = state.get("pending_index", 0) + 1
        state["pending_index"] = pending_index
        user_states[user_id] = state

        if pending_index < len(state.get("pending_fields", [])):
            _prompt_next_field(event, state)
            return

        # すべての編集が完了したら確認画面へ
        state["mode"] = "confirm_after_edit"
        amount = state.get("receipt_amount")
        date = state.get("receipt_date")
        shop = state.get("receipt_shop")
        confirm_text = (
            f"以下の内容で記録しますか？\n"
            f"日付：{date}\n"
            f"店名：{shop}\n"
            f"金額：¥{amount}"
        )
        buttons_template = ButtonsTemplate(
            text=confirm_text,
            actions=[
                MessageAction(label="はい", text="領収書_確認_yes"),
                MessageAction(label="修正", text="領収書_確認_no"),
            ]
        )
        line_bot_api.reply_message(event.reply_token, TemplateSendMessage(alt_text=confirm_text, template=buttons_template))
        return

    if text == "領収書_確認_yes":
        logger.info(f"Receipt confirmation 'yes' from {user_id}")
        if user_id in user_states:
            state = user_states[user_id]
            try:
                amount = state.get("receipt_amount")
                date = state.get("receipt_date")
                shop = state.get("receipt_shop")
                logger.debug(f"Recording receipt for {user_id}: amount={amount}, date={date}, shop={shop}")
                record_receipt(amount, date, shop)
                response_text = f"✅ 領収書を記録しました\n¥{amount} ({date})\n{shop}"
                line_bot_api.reply_message(event.reply_token, TextSendMessage(text=response_text))
                # 状態をクリア
                del user_states[user_id]
                logger.info(f"Receipt recorded and state cleared for {user_id}")
            except Exception as e:
                logger.error(f"Error recording receipt: {e}", exc_info=True)
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=f"領収書の記録に失敗しました: {str(e)}")
                )
        else:
            logger.warning(f"No receipt state found for {user_id}")
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="領収書の情報が見つかりません。もう一度画像を送信してください。")
            )
        return

    if text == "領収書_確認_no":
        logger.info(f"Receipt confirmation 'no' from {user_id}")
        if user_id not in user_states:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="領収書の情報が見つかりません。もう一度画像を送信してください。")
            )
            return

        state = user_states[user_id]
        state["mode"] = "select_fields"
        user_states[user_id] = state
        _prompt_correction_fields(event, state)
        return

    # 交通費入力を処理
    transit_input = parse_transit_input(text)
    if transit_input:
        if len(transit_input) == 3:
            # 金額が含まれている場合
            route, location, fare = transit_input
            try:
                origin, destination = parse_route(route)
                user_states[user_id] = {
                    "mode": "confirm_transit",
                    "origin": origin,
                    "destination": destination,
                    "location": location,
                    "fare": fare,
                }
                total_fare = fare * 2
                confirm_text = (
                    f"片道¥{fare}で記録しますか？それとも往復（¥{total_fare}）ですか？\n"
                    "1. 片道\n"
                    "2. 往復"
                )
                buttons_template = ButtonsTemplate(
                    text=confirm_text,
                    actions=[
                        MessageAction(label="片道", text="片道"),
                        MessageAction(label="往復", text="往復"),
                    ]
                )
                line_bot_api.reply_message(event.reply_token, TemplateSendMessage(alt_text=confirm_text, template=buttons_template))
            except Exception as e:
                logger.error(f"Error preparing transit confirmation: {e}")
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=f"交通費の確認に失敗しました: {str(e)}")
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
        logger.info(f"Sending confirmation message to {user_id}: {confirm_text}")

        buttons_template = ButtonsTemplate(
            text=confirm_text,
            actions=[
                MessageAction(label="はい", text="領収書_確認_yes"),
                MessageAction(label="修正", text="領収書_確認_no"),
            ]
        )
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TemplateSendMessage(alt_text=confirm_text, template=buttons_template)
            )
            logger.info(f"Confirmation message sent to {user_id}")
        except Exception as send_error:
            logger.error(f"Error sending confirmation message: {send_error}", exc_info=True)
            raise

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
