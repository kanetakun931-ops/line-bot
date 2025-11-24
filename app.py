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

# FlaskアプリとLINE Botの初期化
app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# クイズデータを読み込む
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
    print(f"[DEBUG] text: '{text}'")

    if user_id not in user_states:
        user_states[user_id] = UserState()
    state = user_states[user_id]

    # 🔽 ジャンル選択メニュー
    if text == "ジャンル選択":
        print("[DEBUG] ジャンル選択ブロックに入った！")
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label=genre, text=f"ジャンル:{genre}"))
            for genre in genre_list
        ]
        print("[DEBUG] QuickReply items:", [btn.action.label for btn in quick_reply_items])
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="📚 ジャンルを選んでね！",
                    quick_reply=QuickReply(items=quick_reply_items)
                )
            )
            print("[DEBUG] 応答送信成功！")
        except Exception as e:
            print("[ERROR] 応答失敗:", e)
        return

    # 🔽 ジャンル設定
    if text.startswith("ジャンル:"):
        print(f"[DEBUG] ジャンル設定ブロックに入った！ text={text}")
        genre = text.replace("ジャンル:", "").strip()
        print(f"[DEBUG] 選ばれたジャンル: {genre}")
        if genre not in quiz_data:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="そのジャンルは見つからなかったよ！")
            )
            return

        state.set_genre(genre)
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label="スタート 🚀", text="スタート")),
            QuickReplyButton(action=MessageAction(label="ジャンル選択 ↩️", text="ジャンル選択"))
        ]
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=f"{genre}ジャンルを選んだよ！スタートする？",
                quick_reply=QuickReply(items=quick_reply_items)
            )
        )
        return
    # 🔽 スタートで問題出題 ← ここを関数の中に！
    if text == "スタート":
        #debugジャンル一覧の確認
        print("[DEBUG] quiz_data keys:", list(quiz_data.keys()))
        print("[DEBUG] genre_list:", genre_list)

        genre = state.genre
        if not genre:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="まずジャンルを選んでね！")
            )
            return

        questions = quiz_data.get(genre, [])
        unanswered = [q for q in questions if q["id"] not in state.answered]
        if not unanswered:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="もう全部解いちゃったみたい！ジャンルを変えてみてね！")
            )
            return

        next_q = random.choice(unanswered)
        state.current_question = next_q
        if not hasattr(state, "start_time"):
            state.start_time = time.time()

        choices = next_q["choices"]
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label=choice, text=choice))
            for choice in choices
        ]
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=f"Q. {next_q['question']}",
                quick_reply=QuickReply(items=quick_reply_items)
            )
        )
        return
        
    try:
        # 🔽 回答処理
        current_q = state.current_question
        print("[DEBUG] current_question:", current_q)

        if current_q:
            normalized = text.strip()
            print("[DEBUG] normalized:", repr(normalized))

            valid_choices = [c.strip() for c in current_q.get("choices", [])]
            if normalized not in valid_choices:

                print("[DEBUG] valid_choices:", valid_choices)  # ← これでOK！

                if normalized not in valid_choices:
                    print("[DEBUG] 選択肢に一致しない！ normalized:", normalized)
                    print("[DEBUG] valid_choices:", valid_choices)
                    line_bot_api.reply_message(
                        event.reply_token,
                        TextSendMessage(text="その選択肢は見つからなかったよ！もう一度選んでね！")
                    )
                return
    except Exception as e:
        print("[ERROR] 回答処理で例外:", e)

        correct = current_q["answer"].strip()
        explanation = current_q.get("explanation", "")
        print("[DEBUG] 正解:", repr(correct))

        feedback = ""
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
        print("[DEBUG] 回答処理完了！")

        # 🔽 次の問題を探す
        questions = quiz_data.get(state.genre, [])
        unanswered = [q for q in questions if q["id"] not in state.answered]

        if not unanswered:
            total = len(state.answered)
            score = state.score
            elapsed = int(time.time() - getattr(state, "start_time", time.time()))
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"{feedback}\n🎉 全{total}問中、{score}問正解だったよ！\n⏱️ 所要時間：{elapsed}秒\nまた挑戦してね！"
                )
            )
            user_states.pop(user_id, None)
            return

        # 🔽 次の問題へ
        next_q = random.choice(unanswered)
        state.current_question = next_q
        choices = next_q["choices"]
        choice_text = "\n".join([f"・{c}" for c in choices])
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label=choice, text=choice))
            for choice in choices
        ]

        line_bot_api.reply_message(
            event.reply_token,
            [
                TextSendMessage(text=feedback),
                TextSendMessage(
                    text=f"Q. {next_q['question']}",
                    quick_reply=QuickReply(items=quick_reply_items)
                )
            ]
        )
        return




