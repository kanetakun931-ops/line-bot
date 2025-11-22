from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import os
import json
import random

app = Flask(__name__)

line_bot_api = LineBotApi(os.environ.get("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.environ.get("LINE_CHANNEL_SECRET"))

# 問題データの読み込み
with open("questions.json", "r", encoding="utf-8") as f:
    questions = json.load(f)

# ユーザーごとの状態管理
user_state = {}

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

    if text.lower() in ["スタート", "次へ"]:
        q = random.choice(questions)
        user_state[user_id] = q
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"問題: {q['question']}")
        )
    else:
        if user_id in user_state:
            correct = user_state[user_id]["answer"]
            explanation = user_state[user_id]["explanation"]
            if text == correct:
                reply = f"✅ 正解！\n解説: {explanation}\n次へ→「次へ」"
            else:
                reply = f"❌ 不正解… 正解は「{correct}」\n解説: {explanation}\n次へ→「次へ」"
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        else:
            line_bot_api.reply_message(event.reply_token, TextSendMessage(text="「スタート」で始めてね！"))

if __name__ == "__main__":
    app.run()
