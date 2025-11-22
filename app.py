import os
import json
from datetime import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai

# 環境変数からAPIキーを読み込む
openai.api_key = os.getenv("OPENAI_API_KEY")
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# 作成者のLINEユーザーID（admin）
admin_users = ["Uxxxxxxxxxxxxxxxx"]  # ← ちゃんのLINE user_idをここに！

# 一時的な状態保存（保存確認用）
user_state = {}

# Copilotに質問を送る関数
def ask_copilot(question):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "あなたはやさしくてわかりやすい学習アシスタントです。"},
            {"role": "user", "content": question}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content

# ナレッジを保存する関数
def save_knowledge(question, response, user="作成者"):
    data = {
        "question": question,
        "response": response,
        "user": user,
        "timestamp": datetime.now().isoformat()
    }

    try:
        with open("knowledge.json", "r", encoding="utf-8") as f:
            existing = json.load(f)
    except FileNotFoundError:
        existing = []

    existing.append(data)

    with open("knowledge.json", "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

# LINEメッセージ受信時の処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # 「はい」で保存確認中の処理
    if text == "はい" and user_id in user_state and "pending_save" in user_state[user_id]:
        pending = user_state[user_id]["pending_save"]
        save_knowledge(pending["question"], pending["response"], user="作成者")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="ナレッジに保存しました！📚✨")
        )
        user_state[user_id].pop("pending_save")
        return

    # 「いいえ」の場合は保存せずに終了
    if text == "いいえ" and user_id in user_state and "pending_save" in user_state[user_id]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="保存しませんでした！また何かあれば聞いてね〜💧")
        )
        user_state[user_id].pop("pending_save")
        return

    # 通常の質問処理（Copilotに送信）
    copilot_response = ask_copilot(text)

    if user_id in admin_users:
        user_state[user_id] = {
            "pending_save": {
                "question": text,
                "response": copilot_response
            }
        }
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"{copilot_response}\n\nこの会話をナレッジに保存しますか？（はい／いいえ）")
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=copilot_response)
        )

# LINEのWebhookエンドポイント
app = Flask(__name__)

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print("エラー:", e)
        abort(400)

    return "OK"

# ローカル実行用
if __name__ == "__main__":
    app.run()
