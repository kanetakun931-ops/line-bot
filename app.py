from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import *
from linebot.exceptions import InvalidSignatureError
import os
import json
import random
import time
from state import UserState, user_states

app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# クイズデータ読み込み
def load_quiz_data(folder="questions"):
    quiz_data = {}
    for filename in os.listdir(folder):
        if filename.endswith(".json"):
            genre = filename.replace(".json", "")
            with open(os.path.join(folder, filename), encoding="utf-8") as f:
                quiz_data[genre] = json.load(f)
    return quiz_data

quiz_data = load_quiz_data()
genre_list = list(quiz_data.keys())

# 問題IDから1問取得
def get_question_by_id(genre, qid):
    for q in quiz_data[genre]:
        if q["id"] == qid:
            return q
    return None

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

    # ジャンル選択
    if "ジャンル" in text and ":" not in text:
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

    # ジャンル設定
    if text.startswith("ジャンル:"):
        genre = text.replace("ジャンル:", "").strip()
        if genre not in quiz_data:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="そのジャンルは見つからなかったよ！")
            )
            return
        state.set_genre(genre, quiz_data)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=f"{genre}ジャンルを選んだよ！スタートする？",
                quick_reply=QuickReply(items=[
                    QuickReplyButton(action=MessageAction(label="スタート 🚀", text="スタート")),
                    QuickReplyButton(action=MessageAction(label="ジャンル選択 ↩️", text="ジャンル選択"))
                ])
            )
        )
        return

    # スタート
    if text == "スタート":
        if not state.genre:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="まずジャンルを選んでね！")
            )
            return
        state.reset()
        state.set_genre(state.genre, quiz_data)
        send_next_question(event, state, feedback="🚀 スタート！がんばってね！")
        return

    # 回答処理
    current_q = state.current_question
    if current_q:
        normalized = text.strip()
        correct = current_q["answer"]
        explanation = current_q.get("explanation", "")
        if normalized == correct:
            feedback = "⭕ 正解！すごい！"
            state.score += 1
        else:
            feedback = f"❌ 残念！正解は「{correct}」だったよ！"
            state.mistakes.append(current_q["id"])
        if explanation:
            feedback += f"\n{explanation}"

        state.answered.append(current_q["id"])
        state.current_question = None
        send_next_question(event, state, feedback)
        return

    # その他
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="「ジャンル選択」から始めてね！")
    )

def send_next_question(event, state, feedback=""):
    remaining = [qid for qid in state.available_ids if qid not in state.answered]
    if not remaining:
        total = len(state.answered)
        score = state.score
        elapsed = int(time.time() - state.start_time)
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=f"{feedback}\n🎉 全{total}問中、{score}問正解だったよ！\n⏱️ 所要時間：{elapsed}秒\nまた挑戦してね！",
                quick_reply=QuickReply(items=[
                    QuickReplyButton(action=MessageAction(label="ジャンル選択 ↩️", text="ジャンル選択"))
                ])
            )
        )
        #user_states.pop(event.source.user_id, None)
        return

    qid = random.choice(remaining)
    question = get_question_by_id(state.genre, qid)
    if not question:
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text="問題が見つからなかったよ！"))
        return

    choices = question["choices"].copy()
    random.shuffle(choices)
    question["choices"] = choices
    state.current_question = question

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

