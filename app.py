import os
import json
import random
from time import time
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)
import openai
from dotenv import load_dotenv

load_dotenv()

# 環境変数
openai.api_key = os.getenv("OPENAI_API_KEY")
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

app = Flask(__name__)

# 状態管理
quiz_state = {}
quiz_progress = {}
user_state = {}

# ごほうび画像
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

# 間違えた問題の記録
def save_wrong_ids(user_id, wrong_ids):
    try:
        with open("wrong_ids.json", "r", encoding="utf-8") as f:
            data = json.load(f)
    except:
        data = {}
    data[user_id] = wrong_ids
    with open("wrong_ids.json", "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)

def load_wrong_ids(user_id):
    try:
        with open("wrong_ids.json", "r", encoding="utf-8") as f:
            data = json.load(f)
        return data.get(user_id, [])
    except:
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

    # メニュー表示
    if text in ["メニュー", "モード切替", "こんにちは", "はじめる"]:
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label="クイズモード", text="クイズに戻る")),
            QuickReplyButton(action=MessageAction(label="質問モード", text="質問していい？"))
        ]
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="どっちのモードにする？選んでね👇\nいつでも「メニュー」って送れば戻れるよ🌟",
                quick_reply=QuickReply(items=quick_reply_items)
            )
        )
        return

    # モード切替
    if text == "質問していい？":
        user_state[user_id] = {"mode": "chat", "chat_count": 0}
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="うん、なんでも聞いてね！🌈")
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
        user_state[user_id]["chat_count"] += 1
        try:
            copilot_response = ask_copilot(text)
        except Exception as e:
            print("Copilot応答エラー:", e)
            copilot_response = "ごめんね、今は答えられなかった💦"

        messages = [TextSendMessage(text=copilot_response)]

        # 10回目でクイズ招待
        if user_state[user_id]["chat_count"] == 10:
            messages.append(TextSendMessage(
                text="そういえば、クイズにも挑戦できるよ！「メニュー」って送ると選べるよ🌈"
            ))

        line_bot_api.reply_message(event.reply_token, messages)
        return

    # クイズ開始
    if text.startswith("スタート"):
        genre = text.replace("スタート", "").strip()
        all_questions = load_questions()
        filtered = [q for q in all_questions if genre in q.get("genre", "")] if genre else all_questions

        wrong_ids = load_wrong_ids(user_id)
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
            reply = f"正解！🎉 {elapsed}秒で答えられたね！"
        else:
            wrong_id = current.get("id", current.get("question"))
            progress["wrong_ids"].append(wrong_id)
            reply = f"ざんねん…💦 正解は「{current['answer']}」だよ！ ({elapsed}秒)"

        progress["current_index"] += 1

        if progress["current_index"] >= len(progress["questions"]):
            total = len(progress["questions"])
            correct_count = progress["correct_count"]
            avg_time = elapsed // total if total else 0
            save_wrong_ids(user_id, progress["wrong_ids"])

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"終了！スコア：{correct_count}/{total}問\n平均回答時間：{avg_time}秒\nまた挑戦したくなったら「スタート」って送ってね！"
                )
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
                [
                    TextSendMessage(text=reply),
                    TextSendMessage(
                        text=f"{
