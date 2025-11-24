# app.py
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)
import os
import random
import time

from state import UserState, user_states, load_quiz_data

app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

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
    state = user_states.setdefault(user_id, UserState())

    # 🔹 ジャンル選択
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

    # 🔹 ジャンル設定
    if text.startswith("ジャンル:"):
        genre = text.replace("ジャンル:", "").strip()
        if genre not in quiz_data:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="そのジャンルは見つからなかったよ！")
            )
            return
        state.set_genre(genre)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=f"{genre}ジャンルを選んだよ！\nスタートする？",
                quick_reply=QuickReply(items=[
                    QuickReplyButton(action=MessageAction(label="スタート 🚀", text="スタート")),
                    QuickReplyButton(action=MessageAction(label="ジャンル選択 ↩️", text="ジャンル選択"))
                ])
            )
        )
        return

    # 🔹 スタート
    if text == "スタート":
        if not state.genre:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="まずジャンルを選んでね！")
            )
            return
        state.reset()
        send_next_question(event, state, feedback="🚀 スタート！がんばってね！")
        return

    # 🔹 回答処理
    current_q = state.current_question
    if current_q:
        normalized = text.strip()
        valid_choices = [c.strip() for c in current_q.get("choices", [])]
        if normalized not in valid_choices:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="その選択肢は見つからなかったよ！もう一度選んでね！")
            )
            return

        correct = current_q["answer"].strip()
        explanation = current_q.get("explanation", "")
        if normalized == correct:
            feedback = "⭕ 正解！すごい！"
            state.score += 1
        else:
            feedback = f"❌ 残念！正解は「{correct}」だったよ！"
            state.mistakes.append(current_q["id"])
        if explanation:
            feedback += f"\n💡 {explanation}"

        state.answered.append(current_q["id"])
        state.current_question = None
        send_next_question(event, state, feedback)
        return

    # 🔹 その他
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="「ジャンル選択」から始めてね！")
    )

# 🔹 出題処理
def send_next_question(event, state, feedback=""):
    unanswered = get_unanswered_questions(state)
    if not unanswered:
        reply_with_result(event, state, feedback)
        user_states.pop(event.source.user_id, None)
        return

    next_q = random.choice(unanswered)
    state.current_question = next_q
    reply_with_question(event, next_q, feedback)

def reply_with_question(event, question, feedback=""):
    choices = question["choices"]
    quick_reply_items = [
        QuickReplyButton(action=MessageAction(label=choice, text=choice))
        for choice in choices
    ]
    messages = []
    if feedback:
        messages.append(TextSendMessage(text=feedback))
    messages.append(
        TextSendMessage(
            text=f"Q. {question['question']}",
            quick_reply=QuickReply(items=quick_reply_items)
        )
    )
    line_bot_api.reply_message(event.reply_token, messages)

def reply_with_result(event, state, feedback=""):
    total = len(state.answered)
    score = state.score
    elapsed = int(time.time() - getattr(state, "start_time", time.time()))
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(
            text=f"{feedback}\n🎉 全{total}問中、{score}問正解だったよ！\n⏱️ 所要時間：{elapsed}秒\nまた挑戦してね！"
        )
    )

def get_unanswered_questions(state):
    return [
        q for q in quiz_data.get(state.genre, [])
        if q["id"] not in state.answered
    ]
