from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)

import os
import json
import random
import time

app = Flask(__name__)

LINE_CHANNEL_ACCESS_TOKEN = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
LINE_CHANNEL_SECRET = os.getenv("LINE_CHANNEL_SECRET")

line_bot_api = LineBotApi(LINE_CHANNEL_ACCESS_TOKEN)
handler = WebhookHandler(LINE_CHANNEL_SECRET)

user_state = {}
quiz_state = {}

# ジャンルマッピング（表示名 → ファイル名）
def load_questions(genre):
    genre_map = {
        "漢字": "kanji",
        "地理": "chiri",
        "英語": "eigo",
        "英単語1": "word1",
        "英単語2": "word2",
        "保健体育": "hoken",
        "国語": "kokugo",
        "歴史": "rekishi",
        "理科": "rika",
        "数学": "sugaku",
        "北英": "hokushin_english",
        "北国": "hokushin_japanese",
        "北数": "hokushin_math"
    }
    filename = genre_map.get(genre, genre)
    path = f"questions/{filename}.json"
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return json.load(f)

@app.route("/callback", methods=['POST'])
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
    user_id = event.source.user_id
    text = event.message.text.strip()

    # 🟡 再起動検知（優しさ機能）
    if user_id not in user_state:
        user_state[user_id] = {"mode": None, "genre": None}
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="😴 ちょっと寝てたみたい…準備するね！")
        )
        return

    # ジャンル選択メニュー
    if text == "ジャンル選択":
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label="漢字", text="ジャンル:漢字")),
            QuickReplyButton(action=MessageAction(label="地理", text="ジャンル:地理")),
            QuickReplyButton(action=MessageAction(label="英語", text="ジャンル:英語")),
            QuickReplyButton(action=MessageAction(label="英単語1", text="ジャンル:英単語1")),
            QuickReplyButton(action=MessageAction(label="英単語2", text="ジャンル:英単語2")),
            QuickReplyButton(action=MessageAction(label="保健体育", text="ジャンル:保健体育")),
            QuickReplyButton(action=MessageAction(label="国語", text="ジャンル:国語")),
            QuickReplyButton(action=MessageAction(label="歴史", text="ジャンル:歴史")),
            QuickReplyButton(action=MessageAction(label="理科", text="ジャンル:理科")),
            QuickReplyButton(action=MessageAction(label="数学", text="ジャンル:数学")),
            QuickReplyButton(action=MessageAction(label="北英", text="ジャンル:北英")),
            QuickReplyButton(action=MessageAction(label="北国", text="ジャンル:北国")),
            QuickReplyButton(action=MessageAction(label="北数", text="ジャンル:北数"))
        ]
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text="📚 ジャンルを選んでね！",
                quick_reply=QuickReply(items=quick_reply_items)
            )
        )
        return

    # ジャンル選択後
    if text.startswith("ジャンル:"):
        genre = text.replace("ジャンル:", "").strip()
        user_state[user_id]["genre"] = genre
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label="スタート 🚀", text="スタート")),
            QuickReplyButton(action=MessageAction(label="ジャンル ↩️", text="ジャンル選択")),
        ]
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=f"{genre}ジャンルを選んだね！スタートする？👇",
                quick_reply=QuickReply(items=quick_reply_items)
            )
        )
        return

    # クイズ開始
    if text == "スタート":
        genre = user_state[user_id].get("genre")
        all_questions = load_questions(genre)
        if not all_questions:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"{genre}ジャンルの問題ファイルが見つからないよ💦")
            )
            return

        selected = random.sample(all_questions, min(20, len(all_questions)))
        quiz_state[user_id] = {"questions": selected, "current_index": 0,"start_time": time.time()}

        q = selected[0]
        choices = q.get("choices", []).copy()
        random.shuffle(choices)
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label=c, text=c)) for c in choices
        ]

        # 選択肢をA〜Dで整形
        question_text = f"第1問！🔥\n{q.get('question')}\n\n"
        for i, choice in enumerate(choices):
            question_text += f"{chr(65+i)}. {choice}\n"
        question_text += "\n（んぽちゃむ）これ、わかるちゃむ〜？"

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=question_text,
                quick_reply=QuickReply(items=quick_reply_items)
            )
        )
        return

    # 回答処理
    if user_id in quiz_state:
        progress = quiz_state[user_id]
        idx = progress["current_index"]
        questions = progress["questions"]

        if idx >= len(questions):
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="クイズはもう終わってるよ！またスタートしてね！")
            )
            del quiz_state[user_id]
            return

        answer_text = text
        correct = questions[idx]["answer"]
        explanation = questions[idx].get("explanation", "")
        result = "⭕ 正解ちゃむ〜！すごいちゃむ〜！" if answer_text == correct else f"❌ 不正解ちゃむ… 正解は「{correct}」ちゃむ〜"

        if explanation:
            result += f"\n（んぽちゃむ）{explanation}ちゃむ〜"

        result += "\n\n------------------------------"

        # 次の問題へ
        progress["current_index"] += 1
        next_idx = progress["current_index"]

        if next_idx >= len(questions):
            elapsed = time.time() - progress["start_time"]
            minutes = int(elapsed // 60)
            seconds = int(elapsed % 60)
            duration_text = f"🕒 所要時間：{minutes}分{seconds}秒"
            quick_reply_items = [
                QuickReplyButton(action=MessageAction(label="再挑戦 🚀", text="スタート")),
                QuickReplyButton(action=MessageAction(label="ジャンル ↩️", text="ジャンル選択")),
            ]
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"{result}\n🎉 クイズ終了ちゃむ〜！またあそぼちゃむ〜！👇",
                    quick_reply=QuickReply(items=quick_reply_items)
                )
            )
            del quiz_state[user_id]
            return

        next_q = questions[next_idx]
        choices = next_q.get("choices", []).copy()
        random.shuffle(choices)
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label=choice, text=choice))
            for choice in choices
        ]

        # 次の問題を整形
        next_question_text = f"第{next_idx+1}問！🔥\n{next_q['question']}\n\n"
        for i, choice in enumerate(choices):
            next_question_text += f"{chr(65+i)}. {choice}\n"
        next_question_text += "\n（んぽちゃむ）これ、わかるちゃむ〜？"

        # 2通に分けて送信！
        line_bot_api.reply_message(
            event.reply_token,
            [
                TextSendMessage(text=result),
                TextSendMessage(
                    text=next_question_text,
                    quick_reply=QuickReply(items=quick_reply_items)
                )
            ]
        )
        return

    # その他
    line_bot_api.reply_message(
        event.reply_token,
        TextSendMessage(text="今はメニューにいるよ。モードを選んでね！")
    )
