from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)
import json, random

app = Flask(__name__)

line_bot_api = LineBotApi("YOUR_CHANNEL_ACCESS_TOKEN")
handler = WebhookHandler("YOUR_CHANNEL_SECRET")

# ユーザーごとの状態管理
user_state = {}
quiz_state = {}

def shorten_label(label, max_length=20):
    """QuickReplyのラベルを20文字以内に短縮"""
    return label if len(label) <= max_length else label[:17] + "…"

def load_questions():
    """questions.jsonを読み込む"""
    with open("questions.json", encoding="utf-8") as f:
        return json.load(f)

@app.route("/callback", methods=['POST'])
def callback():
    signature = request.headers['X-Line-Signature']
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

    # メニュー表示
    if text in ["メニュー", "モード切替", "こんにちは", "はじめる"]:
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label="保健体育", text="ジャンル:保健体育")),
            QuickReplyButton(action=MessageAction(label="歴史", text="ジャンル:歴史")),
            QuickReplyButton(action=MessageAction(label="地理", text="ジャンル:地理")),
            QuickReplyButton(action=MessageAction(label="国語", text="ジャンル:国語")),
            QuickReplyButton(action=MessageAction(label="数学", text="ジャンル:数学")),
            QuickReplyButton(action=MessageAction(label="理科", text="ジャンル:理科")),
            QuickReplyButton(action=MessageAction(label="英語", text="ジャンル:英語"))
        ]
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="ジャンルを選んでね👇",
                quick_reply=QuickReply(items=quick_reply_items)
            )
        )
        return

    # ジャンル選択後にスタート／戻るを提示
    if text.startswith("ジャンル:"):
        genre = text.replace("ジャンル:", "").strip()
        user_state[user_id] = {"mode": "quiz", "genre": genre}

        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label="スタート", text="スタート")),
            QuickReplyButton(action=MessageAction(label="戻る", text="メニュー"))
        ]

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=f"{genre}ジャンルを選んだね！👇",
                quick_reply=QuickReply(items=quick_reply_items)
            )
        )
        return

    # 戻るでジャンル選択に戻る
    if text == "メニュー":
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label="保健体育 🏃‍♂️", text="ジャンル:保健体育")),
            QuickReplyButton(action=MessageAction(label="歴史 📜", text="ジャンル:歴史")),
            QuickReplyButton(action=MessageAction(label="地理 🗾", text="ジャンル:地理")),
            QuickReplyButton(action=MessageAction(label="国語 📖", text="ジャンル:国語")),
            QuickReplyButton(action=MessageAction(label="数学 ➗", text="ジャンル:数学")),
            QuickReplyButton(action=MessageAction(label="理科 🔬", text="ジャンル:理科")),
            QuickReplyButton(action=MessageAction(label="英語 🇬🇧", text="ジャンル:英語"))
        ]
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="ジャンルを選んでね👇",
                quick_reply=QuickReply(items=quick_reply_items)
            )
        )
        return

    # スタートでクイズ開始
    if text == "スタート":
        genre = user_state.get(user_id, {}).get("genre", "")
        all_questions = load_questions()
        filtered = [q for q in all_questions if genre in q.get("genre", "")] if genre else all_questions

        if len(filtered) < 20:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"{genre}ジャンルの問題が足りないみたい💦")
            )
            return

        selected = random.sample(filtered, 20)
        quiz_state[user_id] = {"questions": selected, "current_index": 0}

        q = selected[0]
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label=shorten_label(choice), text=choice))
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

    # クイズ進行
    if user_id in quiz_state:
        progress = quiz_state[user_id]
        idx = progress["current_index"]
        questions = progress["questions"]

        # 回答チェック
        answer = text
        correct = questions[idx]["answer"]
        reply = "⭕正解！" if answer == correct else f"❌不正解… 正解は「{correct}」"

        # 次の問題へ
        progress["current_index"] += 1
        if progress["current_index"] >= len(questions):
            # 終了
            quick_reply_items = [
                QuickReplyButton(action=MessageAction(label="スタート", text="スタート")),
                QuickReplyButton(action=MessageAction(label="戻る", text="メニュー"))
            ]
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"{reply}\nクイズ終了！また挑戦する？👇",
                    quick_reply=QuickReply(items=quick_reply_items)
                )
            )
            del quiz_state[user_id]
            return
        else:
            next_q = questions[progress["current_index"]]
            quick_reply_items = [
                QuickReplyButton(action=MessageAction(label=shorten_label(choice), text=choice))
                for choice in next_q.get("choices", [])
            ]
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"{reply}\n第{progress['current_index']+1}問！\n{next_q.get('question')}",
                    quick_reply=QuickReply(items=quick_reply_items)
                )
            )
            return
