#!/usr/bin/env python3

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import json, os, random

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

user_state = {}
quiz_state = {}

def load_questions(genre):
    path = f"question/{genre}.json"
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
    body = request.get_data(as_text=True)
    try:
        handler.handle(body, signature)
    except InvalidSignatureError:
        abort(400)
    return 'OK'

@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    if text == "モード:quiz":
        user_state[user_id] = {"mode": "quiz"}
        line_bot_api.reply_message(event.reply_token,
            TextSendMessage(text="🎯 クイズモードに切り替えたよ！"))
        return

    if text.startswith("ジャンル:"):
        genre = text.replace("ジャンル:", "").strip()
        user_state[user_id]["genre"] = genre
        line_bot_api.reply_message(event.reply_token,
            TextSendMessage(text=f"{genre}ジャンルを選んだね！スタートする？"))
        return

    if text == "スタート":
        genre = user_state[user_id].get("genre")
        questions = load_questions(genre)
        if not questions:
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text=f"{genre}ジャンルの問題ファイルが見つからないよ💦"))
            return

        selected = random.sample(questions, min(20, len(questions)))
        quiz_state[user_id] = {"questions": selected, "current_index": 0}

        q = selected[0]
        choices = q.get("choices", [])
        line_bot_api.reply_message(event.reply_token,
            TextSendMessage(text=f"第1問！🔥\n{q.get('question')}\n選択肢: {', '.join(choices)}"))
        return

    line_bot_api.reply_message(event.reply_token,
        TextSendMessage(text="今はメニューにいるよ。モードを選んでね！"))

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))
