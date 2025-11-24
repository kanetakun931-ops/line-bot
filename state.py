# state.py

import json
from collections import defaultdict

class UserState:
    def __init__(self):
        self.genre = None
        self.answered = []
        self.score = 0
        self.current_question = None

    def reset(self):
        self.answered = []
        self.score = 0
        self.current_question = None

    def set_genre(self, genre):
        self.genre = genre
        self.reset()

    def to_dict(self):
        return {
            "genre": self.genre,
            "answered": self.answered,
            "score": self.score,
            "current_question": self.current_question
        }

    def from_dict(self, data):
        self.genre = data.get("genre")
        self.answered = data.get("answered", [])
        self.score = data.get("score", 0)
        self.current_question = data.get("current_question")

# 全ユーザーの状態を保持（user_id: UserState）
user_states = {}

# クイズデータの読み込み
def load_quiz_data(filepath="questions.json"):
    quiz_data = defaultdict(list)
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
    return quiz_data
