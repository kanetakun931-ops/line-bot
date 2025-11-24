#state.py
import time

class UserState:
    def __init__(self):
        self.genre = None
        self.answered = []
        self.mistakes = []
        self.score = 0
        self.current_question = None
        self.start_time = None
        self.available_ids = []

    def reset(self):
        self.answered = []
        self.mistakes = []
        self.score = 0
        self.current_question = None
        self.start_time = time.time()
        self.available_ids = []

    def set_genre(self, genre, quiz_data):
        self.genre = genre
        self.available_ids = [q["id"] for q in quiz_data[genre]]
        print(f"[DEBUG] {genre}ジャンルの問題数: {len(self.available_ids)}")

user_states = {}
