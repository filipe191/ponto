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


class EscalatingLimiter:
    """Como o AttemptLimiter, mas cada bloqueio dura o dobro do anterior (até `max_block`).

    Ex.: 10 erros em 5 min bloqueiam por 5 min; a próxima rodada de 10 erros, 10 min; depois 20, 40...
    A contagem de bloqueios zera depois de `forget_after` segundos sem nenhum bloqueio.
    """

    def __init__(self, max_attempts: int, window_seconds: int, base_block: int, max_block: int, forget_after: int):
        self.attempts = AttemptLimiter(max_attempts, window_seconds)
        self.base_block = base_block
        self.max_block = max_block
        self.forget_after = forget_after
        self._blocks: dict[str, tuple[int, float]] = {}  # chave → (bloqueios seguidos, fim do último)
        self._lock = threading.Lock()

    def blocked_for(self, key: str) -> int:
        """Segundos que ainda faltam de bloqueio (0 = liberado)."""
        with self._lock:
            _, until = self._blocks.get(key, (0, 0.0))
            return max(0, int(until - time.monotonic() + 0.999))

    def fail(self, key: str) -> int:
        """Registra um erro; devolve a duração do bloqueio que ele causou (0 se não bloqueou)."""
        self.attempts.fail(key)
        if not self.attempts.blocked(key):
            return 0
        self.attempts.reset(key)
        now = time.monotonic()
        with self._lock:
            if len(self._blocks) > 10_000:
                self._blocks = {k: v for k, v in self._blocks.items() if now - v[1] < self.forget_after}
            strikes, until = self._blocks.get(key, (0, 0.0))
            if now - until > self.forget_after:
                strikes = 0
            seconds = min(self.base_block * 2**strikes, self.max_block)
            self._blocks[key] = (strikes + 1, now + seconds)
            return seconds
