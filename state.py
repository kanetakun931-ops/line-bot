# state.py
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
