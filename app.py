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

    # 🔍 ここからデバッグ用メッセージを追加！
    print(f"[DEBUG] text: '{text}'")

    if text == "ジャンルは？":
        genre = user_state.get(user_id, {}).get("genre", "（未設定）")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"📘 現在のジャンル：{genre}")
        )
        return

    if text == "状態は？":
        mode = user_state.get(user_id, {}).get("mode", "（未設定）")
        quiz = quiz_state.get(user_id)
        msg = f"🧭 モード：{mode}\n"
        msg += "📝 クイズ中！" if quiz else "🛌 クイズ未開始"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=msg)
        )
        return
    
    # モード切替
    if text == "モード:ask":
        print("[DEBUG] モード:ask が押されたよ！")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="🛠️ 質問モードは現在開発中だよ！もうちょっと待っててね〜！")
        )
        return

    if text == "ジャンル選択":
        if user_id not in user_state:
            user_state[user_id] = {}
        user_state[user_id]["mode"] = "quiz"
        line_bot_api.reply_message(
                event.reply_token,
            TextSendMessage(text="📚 クイズモードに切り替えたよ！ジャンルを選んでね！")
        )
        return

    # クイズ中断
    if text == "やめる":
        if user_id in quiz_state:
            del quiz_state[user_id]
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="🛑 クイズを中断したよ！またいつでも再開してね！")
                )
            else:
                line_bot_api.reply_message(
                    event.reply_token,
                    TextSendMessage(text="今はクイズ中じゃないみたいだよ〜！")
                )
            return

    # ジャンル選択メニュー
    if text == "ジャンル選択":
    print("[DEBUG] ジャンル選択が押されたよ！")
    if user_id not in user_state:
        user_state[user_id] = {}
    user_state[user_id]["mode"] = "quiz"

    try:
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
                text="ジャンルを選んでね！👇",
                quick_reply=QuickReply(items=quick_reply_items)
            )
        )
    except Exception as e:
        print("[ERROR] クイックリプライ送信失敗:", e)
    return


    # ジャンルを選んだとき
    if text.startswith("ジャンル:"):
        genre = text.replace("ジャンル:", "").strip()
        if user_id not in user_state:
            user_state[user_id] = {}
        user_state[user_id]["genre"] = genre
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

    # クイズスタート
    if text == "スタート":
        genre = user_state.get(user_id, {}).get("genre", "")
        if not genre:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="⚠️ ジャンルが選ばれてないみたい！先にジャンルを選んでね〜！")
            )
            return

        all_questions = load_questions()
        filtered = [
            q for q in all_questions
            if genre == q.get("genre") or genre in q.get("genre", [])
        ]
        if len(filtered) < 20:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"{genre}ジャンルの問題が足りないみたい💦")
            )
            return

        selected = random.sample(filtered, 20)
        quiz_state[user_id] = {
            "questions": selected,
            "current_index": 0,
            "correct_count": 0
        }

        q = selected[0]
        quick_reply_items = [
            QuickReplyButton(action=MessageAction(label=shorten_label(choice), text=choice))
            for choice in q.get("choices", [])
        ]
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(
                text=f"第1問！🔥\n{q.get('question')}",
                quick_reply=QuickReply(items=quick_reply_items)
            )
        )
        return

    # クイズ進行中
    if user_id in quiz_state:
        progress = quiz_state[user_id]
        idx = progress["current_index"]
        questions = progress["questions"]
        q = questions[idx]
        choices = [c.strip() for c in q.get("choices", [])]
        answer = text.strip()
        correct = q["answer"].strip()

        if answer not in choices:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="❓その選択肢は見つからなかったよ！もう一度ボタンから選んでね〜！")
            )
            return
        # ✅ reply をここで必ず定義！
        if answer == correct:
            reply = "⭕✨ 正解！"
            progress["correct_count"] += 1
        else:
            reply = f"❌😅 不正解… 正解は「{correct}」"

        # ↓ここから reply を使ってOK！

        progress["current_index"] += 1
        if progress["current_index"] >= len(questions):
            quick_reply_items = [
                QuickReplyButton(action=MessageAction(label="スタート 🚀", text="スタート")),
                QuickReplyButton(action=MessageAction(label="ジャンル選択 ↩️", text="ジャンル選択"))
            ]
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"{reply}\nクイズ終了！🎉 また挑戦してね👇",
                    quick_reply=QuickReply(items=quick_reply_items)
                )
            )
            del quiz_state[user_id]
        else:
            next_q = questions[progress["current_index"]]
            quick_reply_items = [
                QuickReplyButton(action=MessageAction(label=shorten_label(choice), text=choice))
                for choice in next_q.get("choices", [])
            ]
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(
                    text=f"{reply}\n第{progress['current_index']+1}問！🔥\n{next_q.get('question')}",
                    quick_reply=QuickReply(items=quick_reply_items)
                )
            )
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













