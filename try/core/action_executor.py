import time

class ActionExecutor:
    def __init__(self, timeout=30, retry=2):
        self.timeout = timeout
        self.retry = retry

    def execute(self, action_fn, *args, **kwargs):
        for attempt in range(self.retry + 1):
            try:
                start = time.time()
                result = action_fn(*args, **kwargs)
                elapsed = time.time() - start
                return {
                    "success": True,
                    "result": result,
                    "elapsed": elapsed
                }
            except Exception as e:
                if attempt >= self.retry:
                    return {
                        "success": False,
                        "error": str(e)
                    }
