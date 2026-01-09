class LearningEngine:
    def __init__(self):
        self.feedback_buffer = []

    def record_feedback(self, feedback: dict):
        self.feedback_buffer.append(feedback)

    def summarize(self):
        if not self.feedback_buffer:
            return {}
        score_avg = sum(f["score"] for f in self.feedback_buffer) / len(self.feedback_buffer)
        return {
            "samples": len(self.feedback_buffer),
            "avg_score": score_avg
        }
