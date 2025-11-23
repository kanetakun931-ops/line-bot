import os
import json
import random
from datetime import datetime
from time import time
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)
import openai

# 環境変数
openai.api_key = os.getenv("OPENAI_API_KEY")
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# 管理者ID（必要に応じて変更）
admin_users = ["@029fpvxs"]

# 状態管理
quiz_state = {}       # 現在の問題
quiz_progress = {}    # 出題数・正解数・時間・間違い記録など
user_state = {}       # ナレッジ保存などに使う

# クイズデータ読み込み
def load_questions():
    try:
        with open("questions.json", "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception as e:
        print("問題読み込みエラー:", e)
        return []

# Copilot応答
def ask_copilot(question):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "あなたは中学生を励ます優しい先生です。"},
            {"role": "user", "content": question}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content

# メッセージ処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # クイズ開始
    if text == "スタート":
        all_questions = load_questions()
        if len(all_questions) < 50:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="問題が足りないみたい…💦 50問以上用意してね！")
            )
            return

        selected = random.sample(all_questions, 50)
        quiz_progress[user_id] = {
            "current_index": 0,
            "correct_count": 0,
            "start_time": time(),
            "wrong_ids": [],
            "questions": selected
        }

        q = selected[0]
        quiz_state[user_id] = q

        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label=choice, text=choice))
            for choice in q.get("choices", [])
        ]

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=f"第1問！\n{q.get('question')}",
                quick_reply=QuickReply(items=quick_reply_items)
            )
        )
        return

    # クイズ回答中
    if user_id in quiz_state and user_id in quiz_progress:
        current = quiz_state[user_id]
        progress = quiz_progress[user_id]
        correct = current["answer"].strip().lower()
        user_answer = text.strip().lower()
        elapsed = int(time() - progress["start_time"])

        if "choices" in current and user_answer.isdigit():
            index = int(user_answer) - 1
            if 0 <= index < len(current["choices"]):
                user_answer = current["choices"][index].strip().lower()

        is_correct = user_answer == correct
        if is_correct:
            progress["correct_count"] += 1
            reply = f"正解！🎉（{elapsed}秒）"
        else:
            progress["wrong_ids"].append(current.get("id", current.get("question")))
            reply = f"ざんねん…💦 正解は「{current['answer']}」だよ！（{elapsed}秒）"

        progress["current_index"] += 1

        if progress["current_index"] >= len(progress["questions"]):
            total = len(progress["questions"])
            correct = progress["correct_count"]
            avg_time = elapsed // total if total else 0

            if correct == total:
                special_msg = "🌟全問正解おめでとう！君は本当にすごい！未来の天才だね！🌟\n\nこの画像を待ち受けにして、これからもがんばろう！"
                image_url = "https://your-github-raw-url.com/special_image.jpg"  # ← ここに画像URLを入れてね！
                line_bot_api.reply_message(
                    event.reply_token,
                    [
                        TextSendMessage(text=special_msg),
                        TextSendMessage(text=f"スコア：{correct}/{total}問\n平均回答時間：{avg_time}秒"),
                        TextSendMessage(text=image_url)
                    ]
                )
            else:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text=f"おつかれさま！\nスコア：{correct}/{total}問\nまたチャレンジしてね！")
                )
            del quiz_progress[user_id]
            del quiz_state[user_id]
        else:
            next_q = progress["questions"][progress["current_index"]]
            quiz_state[user_id] = next_q
            progress["start_time"] = time()

            star = "★" if next_q.get("id", next_q.get("question")) in progress["wrong_ids"] else ""
            quick_reply_items = [
                QuickReplyButton(action=MessageAction(label=choice, text=choice))
                for choice in next_q.get("choices", [])
            ]
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"{star}第{progress['current_index']+1}問！\n{next_q.get('question')}",
                    quick_reply=QuickReply(items=quick_reply_items)
                )
            )
        return

    # その他の応答（Copilot）
    copilot_response = ask_copilot(text)
    line_bot_api.reply_message(event.reply_token, TextSendMessage(text=copilot_response))

# Flaskルーティング
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

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
