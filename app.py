# app.py

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)
import os

from state import UserState, user_states, load_quiz_data

app = Flask(__name__)

# 環境変数からトークンとシークレットを取得
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# クイズデータを読み込む
quiz_data = load_quiz_data()
genre_list = list(quiz_data.keys())

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)

    return "OK"

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()
    print(f"[DEBUG] text: '{text}'")

    # ユーザー状態を取得 or 初期化
    if user_id not in user_states:
        user_states[user_id] = UserState()
    state = user_states[user_id]

    # 🔽 ジャンル選択メニュー
    if text == "ジャンル選択":
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label=genre, text=f"ジャンル:{genre}"))
            for genre in genre_list
        ]
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="📚 ジャンルを選んでね！",
                quick_reply=QuickReply(items=quick_reply_items)
            )
        )
        return

    # 🔽 ジャンル設定
    if text.startswith("ジャンル:"):
        genre = text.replace("ジャンル:", "").strip()
        if genre not in quiz_data:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="そのジャンルは見つからなかったよ！")
            )
            return
        state.set_genre(genre)
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label="スタート 🚀", text="スタート")),
            QuickReplyButton(action=MessageAction(label="ジャンル選択 ↩️", text="ジャンル選択"))
        ]
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=f"{genre}ジャンルを選んだよ！スタートする？",
                quick_reply=QuickReply(items=quick_reply_items)
            )
        )
        return
