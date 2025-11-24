# state.py
# state.py

import time

class UserState:
    def __init__(self):
        self.genre = None
        self.answered = []
        self.mistakes = []
        self.score = 0
        self.current_question = None
        self.start_time = None

    def reset(self):
        self.answered = []
        self.mistakes = []
        self.score = 0
        self.current_question = None
        self.start_time = time.time()

    def set_genre(self, genre):
        self.genre = genre

# 🔽 これを忘れずに追加！
user_states = {}

# 🔽 クイズデータ読み込み関数（仮の例）
import json
import os

def load_quiz_data(folder="questions"):
    quiz_data = {}
    for filename in os.listdir(folder):
        if filename.endswith(".json"):
            genre = filename.replace(".json", "")
            with open(os.path.join(folder, filename), encoding="utf-8") as f:
                quiz_data[genre] = json.load(f)
    return quiz_data
