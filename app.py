#!/usr/bin/env python3

from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import json
import os

app = Flask(__name__)

# 環境変数からLINEの設定を取得
LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

# ユーザー状態（最低限）
user_state = {}

@app.route("/callback", methods=['POST'])
def load_questions(genre):
    # ジャンルごとのファイルを読み込む
    path = f"question/{genre}.json"
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)
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
    text = event.message.text.strip()
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text=f"受け取ったよ: {text}")
    )

    if text == "モード:quiz":
        user_state[event.source.user_id] = {"mode": "quiz"}
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🎯 クイズモードに切り替えたよ！")
        )
    elif text == "モード:ask":
        user_state[event.source.user_id] = {"mode": "ask"}
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="💡 質問モードに切り替えたよ！")
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="今はメニューにいるよ。モードを選んでね！")
        )

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=int(os.environ.get("PORT", 5000)))

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

    if text == "スタート":
        genre = user_state[user_id].get("genre")
        all_questions = load_questions(genre)  # ← ジャンルごとのファイルを読む
        if not all_questions:
            line_bot_api.reply_message(event.reply_token,
                TextSendMessage(text=f"{genre}ジャンルの問題ファイルが見つからないよ💦"))
            return

        selected = random.sample(all_questions, min(20, len(all_questions)))
        quiz_state[user_id] = {"questions": selected, "current_index": 0}

        q = selected[0]
        choices = q.get("choices", [])
        quick_reply_items = [QuickReplyButton(action=MessageAction(label=c, text=c)) for c in choices]

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"第1問！🔥\n{q.get('question')}",
                            quick_reply=QuickReply(items=quick_reply_items))
        )

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










