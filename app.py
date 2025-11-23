import os
import json
import difflib
import random
from datetime import datetime
from flask import Flask, request, abort
from linebot import LineBotApi, WebhookHandler
from linebot.models import MessageEvent, TextMessage, TextSendMessage
import openai

# 環境変数からAPIキーを読み込む
openai.api_key = os.getenv("OPENAI_API_KEY")
line_bot_api = LineBotApi(os.getenv("LINE_CHANNEL_ACCESS_TOKEN"))
handler = WebhookHandler(os.getenv("LINE_CHANNEL_SECRET"))

# 作成者のLINEユーザーID（admin）
admin_users = ["Uxxxxxxxxxxxxxxxx"]  # ← ちゃんのLINE user_idをここに！

# 状態管理
user_state = {}     # 保存確認用
quiz_state = {}     # 出題モード用

# 🔹 Copilotに質問を送る関数
def ask_copilot(question):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo",
        messages=[
            {"role": "system", "content": "あなたはやさしくてわかりやすい学習アシスタントです。"},
            {"role": "user", "content": question}
        ],
        temperature=0.7
    )
    return response.choices[0].message.content

# 🔹 ナレッジを保存する関数
def save_knowledge(question, response, user="作成者"):
    data = {
        "question": question,
        "response": response,
        "user": user,
        "timestamp": datetime.now().isoformat()
    }

    try:
        with open("knowledge.json", "r", encoding="utf-8") as f:
            existing = json.load(f)
    except FileNotFoundError:
        existing = []

    existing.append(data)

    with open("knowledge.json", "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=2)

# 🔹 ナレッジを検索する関数
def search_knowledge(query, threshold=0.6):
    try:
        with open("knowledge.json", "r", encoding="utf-8") as f:
            knowledge = json.load(f)
    except FileNotFoundError:
        return []

    results = []
    for item in knowledge:
        similarity = difflib.SequenceMatcher(None, query, item["question"]).ratio()
        if similarity >= threshold:
            results.append({
                "question": item["question"],
                "response": item["response"],
                "score": similarity
            })

    results.sort(key=lambda x: x["score"], reverse=True)
    return results

# 🔹 ランダムに問題を出す関数
def get_random_question():
    try:
        with open("questions.json", "r", encoding="utf-8") as f:
            questions = json.load(f)
        return random.choice(questions)
    except Exception as e:
        print("問題の読み込みエラー:", e)
        return None

# 🔹 ジャンル別に問題を出す関数
def get_question_by_genre(genre):
    try:
        with open("questions.json", "r", encoding="utf-8") as f:
            questions = json.load(f)
        filtered = [q for q in questions if q.get("genre") == genre]
        return random.choice(filtered) if filtered else None
    except Exception as e:
        print("ジャンル別出題エラー:", e)
        return None

# 🔹 LINEメッセージ受信時の処理
@handler.add(MessageEvent, message=TextMessage)
def handle_message(event):
    user_id = event.source.user_id
    text = event.message.text.strip()

    # ① 出題モード中の回答処理
    if user_id in quiz_state:
        current = quiz_state[user_id]
        correct = current["answer"].strip().lower()
        user_answer = text.strip().lower()

        # 🔽 数字で答えた場合、選択肢に変換
        if "choices" in current and user_answer.isdigit():
            index = int(user_answer) - 1
            if 0 <= index < len(current["choices"]):
                user_answer = current["choices"][index].strip().lower()

        if user_answer == correct:
            reply = f"正解！🎉\n\n{current['explanation']}"
        else:
            reply = f"ざんねん…💦 正解は「{current['answer']}」だよ！\n\n{current['explanation']}"

        del quiz_state[user_id]
        line_bot_api.reply_message(event.reply_token, TextSendMessage(text=reply))
        return

    # ② 出題モード開始（ジャンル指定 or ランダム）
    if text in ["出題して", "問題ちょうだい", "クイズ出して"] or text.endswith("の問題出して") or text.endswith("のクイズちょうだい"):
        if text.endswith("の問題出して") or text.endswith("のクイズちょうだい"):
            genre = text.replace("の問題出して", "").replace("のクイズちょうだい", "").strip()
            q = get_question_by_genre(genre)
        else:
            q = get_random_question()

        if q:
            quiz_state[user_id] = q
            # 🔽 選択肢がある場合は整形して表示
            if "choices" in q:
                choices_text = "\n".join([f"{i+1}. {choice}" for i, choice in enumerate(q["choices"])])
                question_text = f"{q['question']}\n\n{choices_text}"
            else:
                question_text = q["question"]

            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text=f"{q.get('genre', '問題')}の問題だよ！\n\n{question_text}")
            )
        else:
            line_bot_api.reply_message(
                event.reply_token,
                TextSendMessage(text="ごめんね、問題が見つからなかったみたい…💦")
            )
        return

    # ③ 保存確認：「はい」
    if text == "はい" and user_id in user_state and "pending_save" in user_state[user_id]:
        pending = user_state[user_id]["pending_save"]
        save_knowledge(pending["question"], pending["response"], user="作成者")
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="ナレッジに保存しました！📚✨")
        )
        user_state[user_id].pop("pending_save")
        return

    # ④ 保存確認：「いいえ」
    if text == "いいえ" and user_id in user_state and "pending_save" in user_state[user_id]:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text="保存しませんでした！また何かあれば聞いてね〜💧")
        )
        user_state[user_id].pop("pending_save")
        return

    # ⑤ ナレッジ検索
    matches = search_knowledge(text)

    if matches:
        top = matches[0]
        reply = f"過去のナレッジから見つけたよ！\n\nQ: {top['question']}\nA: {top['response']}"
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=reply)
        )
        return

    # ⑥ ナレッジがなければ Copilot に聞く
    copilot_response = ask_copilot(text)

    if user_id in admin_users:
        user_state[user_id] = {
            "pending_save": {
                "question": text,
                "response": copilot_response
            }
        }
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=f"{copilot_response}\n\nこの会話をナレッジに保存しますか？（はい／いいえ）")
        )
    else:
        line_bot_api.reply_message(
            event.reply_token,
            TextSendMessage(text=copilot_response)
        )

# 🔹 Flaskのルーティング
app = Flask(__name__)

@app.route("/callback", methods=["POST"])
def callback():
    signature = request.headers["X-Line-Signature"]
    body = request.get_data(as_text=True)

    try:
        handler.handle(body, signature)
    except Exception as e:
        print("エラー:", e)
        abort(400)

    return "OK"

# 🔹 ローカル実行用
if __name__ == "__main__":
    app.run()
