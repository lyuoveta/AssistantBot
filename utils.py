from time import time


class ExpiringDict:
    def __init__(self, max_age_seconds):
        assert max_age_seconds > 0
        self.age = max_age_seconds
        self.container = {}

    def get(self, key):
        if key not in self.container:
            return None
        value, created = self.container[key]
        if time() - created > self.age:
            del self.container[key]
            return None

        return value

    def set(self, key, value):
        self.container[key] = (value, time())

    def remove(self, key):
        if key in self.container:
            del self.container[key]
