from collections import deque
import time

class StateManager:
    def __init__(self, memory_size=50):
        self.current_state = {}
        self.history = deque(maxlen=memory_size)
        self.context = {}

    def update_state(self, state_update: dict):
        timestamp = time.time()
        self.current_state.update(state_update)
        self.history.append({
            "timestamp": timestamp,
            "state": state_update
        })

    def get_state(self):
        return self.current_state

    def set_context(self, key, value):
        self.context[key] = value

    def get_context(self, key, default=None):
        return self.context.get(key, default)
