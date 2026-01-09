import yaml
import os

class ConfigLoader:
    def __init__(self, path: str):
        if not os.path.exists(path):
            raise FileNotFoundError(f"Config file not found: {path}")
        with open(path, "r", encoding="utf-8") as f:
            self.config = yaml.safe_load(f)

    def get(self, key, default=None):
        return self.config.get(key, default)

    def validate(self):
        required = ["agent", "logging", "execution"]
        for r in required:
            if r not in self.config:
                raise ValueError(f"Missing config section: {r}")
