from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.exceptions import InvalidSignatureError
from linebot.models import (
    MessageEvent, TextMessage, TextSendMessage,
    QuickReply, QuickReplyButton, MessageAction
)
from dotenv import load_dotenv
import os
import json, random
import openai
from collections import defaultdict

# ジャンルごとに問題をまとめる辞書
quiz_data = defaultdict(list)

# JSONファイルを読み込んで整形
with open("questions.json", encoding="utf-8") as f:
    raw_questions = json.load(f)
    for q in raw_questions:
        genre = q.get("genre", "その他")
        quiz_data[genre].append({
            "id": q["id"],
            "question": q["question"],
            "choices": q["choices"],
            "answer": q["answer"],
            "explanation": q.get("explanation", "")
        })

# 環境変数を読み込む
load_dotenv()
openai.api_key = os.getenv("OPENAI_API_KEY")

# FlaskアプリとLINE Botの初期化
app = Flask(__name__)
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# ユーザーごとの状態管理
user_state = {}
quiz_state = {}

def shorten_label(label, max_length=20):
    return label if len(label) <= max_length else label[:17] + "…"

def load_questions():
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
    # ユーザー状態を初期化
    if user_id not in user_state:
        user_state[user_id] = {}

    state = user_state[user_id]

    # ジャンル選択メニュー
    if text == "ジャンル選択":
        print("[DEBUG] ジャンル選択が押されたよ！")
        state["mode"] = "quiz"
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label="保健体育", text="ジャンル:保健体育")),
            QuickReplyButton(action=MessageAction(label="英語", text="ジャンル:英語")),
            QuickReplyButton(action=MessageAction(label="数学", text="ジャンル:数学")),
            QuickReplyButton(action=MessageAction(label="国語", text="ジャンル:国語"))
        ]
        try:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text="📚 クイズモードに切り替えたよ！ジャンルを選んでね！👇",
                    quick_reply=QuickReply(items=quick_reply_items)
                )
            )
        except Exception as e:
            print("[ERROR] クイックリプライ送信失敗:", e)
        return

    # ジャンル設定
    if text.startswith("ジャンル:"):
        genre = text.replace("ジャンル:", "").strip()
        state["genre"] = genre
        state["answered"] = []
        state["score"] = 0
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label="スタート 🚀", text="スタート")),
            QuickReplyButton(action=MessageAction(label="ジャンル選択に戻る ↩️", text="ジャンル選択"))
        ]
        line_bot_api.reply_message(
            event.reply_token,
            [
                TextSendMessage(text=f"{genre}ジャンルを選んだね！"),
                TextSendMessage(
                    text="スタートする？それともメニューに戻る？👇",
                    quick_reply=QuickReply(items=quick_reply_items)
                )
            ]
        )
        return

    # スタートでクイズ開始
    if text == "スタート":
        genre = state.get("genre")
        if not genre:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="ジャンルが選ばれてないみたい！「ジャンル選択」から始めてね！")
            )
            return
            

        # 問題取得
        answered_ids = state.get("answered", [])
        questions = quiz_data.get(genre, [])
        next_q = next((q for q in questions if q["id"] not in answered_ids), None)

        if not next_q:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="もうすべての問題に答えたよ！おつかれさま！")
            )
            return

        state["current_question"] = next_q
        quick_reply_items = []

        if "choices" in next_q:
            for choice in next_q["choices"]:
                quick_reply_items.append(
                    QuickReplyButton(action=MessageAction(label=choice, text=choice))
                )
        else:
            quick_reply_items = [
                QuickReplyButton(action=MessageAction(label="〇", text="〇")),
                QuickReplyButton(action=MessageAction(label="×", text="×"))
            ]

        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=next_q["question"],
                quick_reply=QuickReply(items=quick_reply_items)
            )
        )
        return

    # 回答処理（〇× or 4択）
    current_q = state.get("current_question")
    if current_q:
        expected = current_q["answer"]
        valid_choices = current_q.get("choices", ["〇", "○", "×", "✕"])
        normalized = "〇" if text in ["〇", "○"] else "×" if text in ["×", "✕"] else text

        if normalized not in valid_choices:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="その選択肢は見つからなかったよ！もう一度選んでね！")
            )
            return

        if normalized == expected:
            feedback = "⭕ 正解！すごい！"
            state["score"] = state.get("score", 0) + 1
        else:
            feedback = f"❌ 残念！正解は「{expected}」だったよ！"

        state.setdefault("answered", []).append(current_q["id"])

        # 次の問題
        genre = state.get("genre")
        questions = quiz_data.get(genre, [])
        next_q = next((q for q in questions if q["id"] not in state["answered"]), None)

        if next_q:
            state["current_question"] = next_q
            quick_reply_items = []

            if "choices" in next_q:
                for choice in next_q["choices"]:
                    quick_reply_items.append(
                        QuickReplyButton(action=MessageAction(label=choice, text=choice))
                    )
            else:
                quick_reply_items = [
                    QuickReplyButton(action=MessageAction(label="〇", text="〇")),
                    QuickReplyButton(action=MessageAction(label="×", text="×"))
                ]

            line_bot_api.reply_message(
                event.reply_token,
                [
                    TextSendMessage(text=feedback),
                    TextSendMessage(
                        text=next_q["question"],
                        quick_reply=QuickReply(items=quick_reply_items)
                    )
                ]
            )
        else:
            total = len(state["answered"])
            score = state.get("score", 0)
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"{feedback}\n🎉 全{total}問中、{score}問正解だったよ！また挑戦してね！")
            )
            user_state.pop(user_id, None)
        return

    # 質問モード（Copilotに聞く）
    if user_state.get(user_id, {}).get("mode") == "ask":
        try:
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo",
                messages=[
                    {"role": "system", "content": "あなたは中学生にわかりやすく答える先生です。答えの最後に豆知識を必ず添えてください。"},
                    {"role": "user", "content": text}
                ],
                max_tokens=300
            )
            copilot_response = response["choices"][0]["message"]["content"]
            reply_text = f"💡いい質問だね！\n{copilot_response}"
        except Exception as e:
            print("OpenAI応答エラー:", e)
            reply_text = "😅ごめんね、今は答えられなかった…また聞いてみて！"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply_text)
        )
        return


















