# state.py

import os
import json
from collections import defaultdict

class UserState:
    def __init__(self):
        self.genre = None
        self.answered = []
        self.score = 0
        self.current_question = None
        self.mistakes = []

    def reset(self):
        self.answered = []
        self.score = 0
        self.current_question = None
        self.mistakes = []

    def set_genre(self, genre):
        self.genre = genre
        self.reset()

    def to_dict(self):
        return {
            "genre": self.genre,
            "answered": self.answered,
            "score": self.score,
            "current_question": self.current_question,
            "mistakes": self.mistakes
        }

    def from_dict(self, data):
        self.genre = data.get("genre")
        self.answered = data.get("answered", [])
        self.score = data.get("score", 0)
        self.current_question = data.get("current_question")
        self.mistakes = data.get("mistakes", [])

# 全ユーザーの状態を保持（user_id: UserState）
user_states = {}

# クイズデータの読み込み（ジャンル別ファイル対応）
def load_quiz_data(folder="questions"):
    quiz_data = defaultdict(list)
    for filename in os.listdir(folder):
        if filename.endswith(".json"):
            filepath = os.path.join(folder, filename)
            try:
                with open(filepath, encoding="utf-8") as f:
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
            except Exception as e:
                print(f"[ERROR] {filename} の読み込みに失敗しました: {e}")
    return quiz_data
