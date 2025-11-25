#!/usr/bin/env python3

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import *
from linebot.exceptions import InvalidSignatureError
import os
import json
import random
import time
from state import UserState, user_states
import logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
# ユーザーごとの状態管理
user_state = {}
quiz_state = {}
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

processed_events = set()
def is_duplicate(event):
    event_id = getattr(event, 'reply_token', None) or f"{event.source.user_id}-{event.timestamp}"
    if event_id in processed_events:
        return True
    processed_events.add(event_id)
    return False

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

    if is_duplicate(event):
        logger.info("Duplicate event detected; skipping.")
        return
    user_id = event.source.user_id
    text = event.message.text.strip()

    # 安全な初期化
    if user_id not in user_state:
        user_state[user_id] = {"mode": None, "genre": None}

    # モード切替
    if text == "モード:quiz":
        user_state[user_id].update({"mode": "quiz", "genre": None})
        # （ジャンルQuickReplyは既存のままでOK）
        # ...
        return

    if text == "モード:ask":
        user_state[user_id].update({"mode": "ask"})
        # ...
        return

    # 質問モード
    if user_state[user_id].get("mode") == "ask":
        # 外部呼び出しが遅い場合はタイムアウト対策を（後述）
        # ...
        return

    # クイズモード以外はここで誘導
    if user_state[user_id].get("mode") != "quiz":
        line_bot_api.reply_message(event.reply_token,
            TextSendMessage(text="今はメニューにいるよ。🎯クイズか💡質問を選んでね！"))
        return

    # ジャンル選択
    if text.startswith("ジャンル:"):
        genre = text.replace("ジャンル:", "").strip()
        user_state[user_id]["genre"] = genre
        # スタート/戻るQuickReply
        # ...
        return

    # スタート
    if text == "スタート":
        genre = user_state[user_id].get("genre")
        all_questions = load_questions()

        # フィルタ方式を明確化（完全一致推奨）
        filtered = [q for q in all_questions if q.get("genre") == genre] if genre else all_questions

        # 検証（choices/answer）
        for i, q in enumerate(filtered):
            if not q.get("choices"):
                logger.warning(f"Empty choices at index {i}: {q}")
            if q.get("answer") not in q.get("choices", []):
                logger.warning(f"Answer not in choices at index {i}: {q}")

        if len(filtered) < 20:
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text=f"{genre}ジャンルの問題が足りないみたい💦（{len(filtered)}問）"))
            return

        selected = random.sample(filtered, 20)
        quiz_state[user_id] = {"questions": selected, "current_index": 0}

        q = selected[0]
        choices = q.get("choices", [])
        quick_reply_items = [QuickReplyButton(action=MessageAction(label=shorten_label(c), text=c)) for c in choices]

        line_bot_api.reply_message(event.reply_token,
            TextSendMessage(text=f"第1問！🔥\n{q.get('question')}",
                            quick_reply=QuickReply(items=quick_reply_items)))
        logger.info(f"Start quiz user={user_id} genre={genre} total=20")
        return

    # 進行（防御的に）
    if user_id in quiz_state:
        progress = quiz_state[user_id]
        idx = progress["current_index"]
        questions = progress["questions"]

        # 境界防御
        if idx < 0 or idx >= len(questions):
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text="進行がずれちゃったみたい。もう一度スタートしてね🙏"))
            logger.error(f"Index out of range user={user_id} idx={idx}")
            del quiz_state[user_id]
            return

        answer_text = text
        correct = questions[idx]["answer"]
        result = "⭕✨ 正解！" if answer_text == correct else f"❌😅 不正解… 正解は「{correct}」"

        # 次へ
        progress["current_index"] += 1
        next_idx = progress["current_index"]

        if next_idx >= len(questions):
            # 終了
            quick_reply_items = [
                QuickReplyButton(action=MessageAction(label="もう一度 🚀", text="スタート")),
                QuickReplyButton(action=MessageAction(label="メニューへ ↩️", text="モード:quiz"))
            ]
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text=f"{result}\nクイズ終了！🎉 また挑戦する？👇",
                                quick_reply=QuickReply(items=quick_reply_items)))
            logger.info(f"Finish quiz user={user_id}")
            del quiz_state[user_id]
            return
        else:
            next_q = questions[next_idx]
            choices = next_q.get("choices", [])
            quick_reply_items = [QuickReplyButton(action=MessageAction(label=shorten_label(c), text=c)) for c in choices]
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text=f"{result}\n第{next_idx+1}問！🔥\n{next_q.get('question')}",
                                quick_reply=QuickReply(items=quick_reply_items)))
            logger.info(f"Next question user={user_id} idx={next_idx}")
            return
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




