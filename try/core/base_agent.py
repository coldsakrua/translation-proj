class BaseAgent:
    def __init__(self, name, state_manager, executor, learner, logger, max_steps=10):
        self.name = name
        self.state = state_manager
        self.executor = executor
        self.learner = learner
        self.logger = logger
        self.max_steps = max_steps

    def think(self, task: str):
        raise NotImplementedError

    def act(self, action):
        raise NotImplementedError

    def run(self, task: str):
        self.logger.info(f"Agent {self.name} started task: {task}")
        self.state.update_state({"task": task})

        for step in range(self.max_steps):
            self.logger.info(f"Step {step}")
            action = self.think(task)
            result = self.act(action)

            self.state.update_state({
                "step": step,
                "action": action,
                "result": result
            })

            if result.get("done"):
                self.logger.info("Task completed")
                break
