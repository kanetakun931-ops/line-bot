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

# 状態管理
quiz_state = {}
quiz_progress = {}
user_state = {}

# ごほうび画像（GitHub Raw URL）
image_urls = [
    "https://raw.githubusercontent.com/kanetakura913/ops/main/1707186602194.jpg",
    "https://raw.githubusercontent.com/kanetakura913/ops/main/1707186602195.jpg",
    "https://raw.githubusercontent.com/kanetakura913/ops/main/1707186602196.jpg",
    "https://raw.githubusercontent.com/kanetakura913/ops/main/1707186602197.jpg",
    "https://raw.githubusercontent.com/kanetakura913/ops/main/1707186602198.jpg",
    "https://raw.githubusercontent.com/kanetakura913/ops/main/1707186602199.jpg"
]

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

    # モード切り替え
    if text == "質問していい？":
        user_state[user_id] = {"mode": "chat"}
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="うん、なんでも聞いてね！勉強のことでも、気になることでもOKだよ🌈")
        )
        return

    if text == "クイズに戻る":
        user_state[user_id] = {"mode": "quiz"}
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="クイズモードに戻るよ！「スタート」で始めてね💧")
        )
        return

    # 質問モード
    if user_state.get(user_id, {}).get("mode") == "chat":
        copilot_response = ask_copilot(text)
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=copilot_response))
        return

    # クイズ開始（教科別）
    if text.startswith("スタート"):
        genre = text.replace("スタート", "").strip()
        all_questions = load_questions()
        filtered = [q for q in all_questions if genre in q.get("genre", "")] if genre else all_questions

        # 出題候補を調整（間違えた問題は3倍に）
        wrong_ids = quiz_progress.get(user_id, {}).get("wrong_ids", [])
        candidates = []
        for q in filtered:
            q_id = q.get("id", q.get("question"))
            if q_id in wrong_ids:
                candidates.extend([q] * 3)
            else:
                candidates.append(q)

        if len(candidates) < 20:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="問題が足りないみたい…💦 20問以上用意してね！")
            )
            return

        selected = random.sample(candidates, 20)
        quiz_progress[user_id] = {
            "current_index": 0,
            "correct_count": 0,
            "start_time": time(),
            "wrong_ids": [],
            "questions": selected
        }

        q = selected[0]
        quiz_state[user_id] = q
        user_state[user_id] = {"mode": "quiz"}

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
                image_url = random.choice(image_urls)
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

if __

