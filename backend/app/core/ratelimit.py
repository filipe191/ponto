"""Limite de tentativas erradas por chave (ex.: IP), guardado na memória do processo."""

import threading
import time
from collections import deque


class AttemptLimiter:
    def __init__(self, max_attempts: int, window_seconds: int):
        self.max_attempts = max_attempts
        self.window = window_seconds
        self._failures: dict[str, deque[float]] = {}
        self._lock = threading.Lock()

    def blocked(self, key: str) -> bool:
        with self._lock:
            return len(self._recent(key, time.monotonic())) >= self.max_attempts

    def fail(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            if len(self._failures) > 10_000:  # não deixa o dicionário crescer sem limite
                for k in list(self._failures):
                    self._recent(k, now)
            self._failures.setdefault(key, deque()).append(now)

    def reset(self, key: str) -> None:
        with self._lock:
            self._failures.pop(key, None)

    def _recent(self, key: str, now: float) -> deque[float]:
        attempts = self._failures.get(key, deque())
        while attempts and attempts[0] <= now - self.window:
            attempts.popleft()
        if not attempts:
            self._failures.pop(key, None)
        return attempts
