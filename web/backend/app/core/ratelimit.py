"""Limite de tentativas erradas por chave (ex.: IP), guardado no banco.

Cada limitador usa a própria sessão: o erro fica gravado mesmo quando a requisição é desfeita, e
reiniciar o backend não zera os bloqueios em andamento. As tentativas e os bloqueios vencidos são
apagados a cada novo erro.
"""

from datetime import UTC, datetime, timedelta

from sqlalchemy import delete, func, select

from app.db.session import SessionLocal
from app.models.attempt import AttemptBlock, AttemptFailure


def _now() -> datetime:
    return datetime.now(UTC)


class AttemptLimiter:
    def __init__(self, scope: str, max_attempts: int, window_seconds: int):
        self.scope = scope
        self.max_attempts = max_attempts
        self.window = timedelta(seconds=window_seconds)

    def blocked(self, key: str) -> bool:
        with SessionLocal() as db:
            count = db.scalar(
                select(func.count()).where(
                    AttemptFailure.scope == self.scope,
                    AttemptFailure.key == key,
                    AttemptFailure.at > _now() - self.window,
                )
            )
        return count >= self.max_attempts

    def fail(self, key: str) -> None:
        now = _now()
        with SessionLocal() as db:
            db.execute(
                delete(AttemptFailure).where(AttemptFailure.scope == self.scope, AttemptFailure.at <= now - self.window)
            )
            db.add(AttemptFailure(scope=self.scope, key=key, at=now))
            db.commit()

    def reset(self, key: str) -> None:
        with SessionLocal() as db:
            db.execute(delete(AttemptFailure).where(AttemptFailure.scope == self.scope, AttemptFailure.key == key))
            db.commit()


class EscalatingLimiter:
    """Como o AttemptLimiter, mas cada bloqueio dura o dobro do anterior (até `max_block`).

    Ex.: 10 erros em 5 min bloqueiam por 5 min; a próxima rodada de 10 erros, 10 min; depois 20, 40...
    A contagem de bloqueios zera depois de `forget_after` segundos sem nenhum bloqueio.
    """

    def __init__(
        self, scope: str, max_attempts: int, window_seconds: int, base_block: int, max_block: int, forget_after: int
    ):
        self.scope = scope
        self.attempts = AttemptLimiter(scope, max_attempts, window_seconds)
        self.base_block = base_block
        self.max_block = max_block
        self.forget_after = timedelta(seconds=forget_after)

    def blocked_for(self, key: str) -> int:
        """Segundos que ainda faltam de bloqueio (0 = liberado)."""
        with SessionLocal() as db:
            block = db.get(AttemptBlock, (self.scope, key))
        if not block:
            return 0
        return max(0, int((block.until - _now()).total_seconds() + 0.999))

    def fail(self, key: str) -> int:
        """Registra um erro; devolve a duração do bloqueio que ele causou (0 se não bloqueou)."""
        self.attempts.fail(key)
        if not self.attempts.blocked(key):
            return 0
        self.attempts.reset(key)
        now = _now()
        with SessionLocal() as db:
            db.execute(
                delete(AttemptBlock).where(
                    AttemptBlock.scope == self.scope,
                    AttemptBlock.key != key,
                    AttemptBlock.until < now - self.forget_after,
                )
            )
            block = db.get(AttemptBlock, (self.scope, key))
            if not block:
                block = AttemptBlock(scope=self.scope, key=key, strikes=0, until=now)
                db.add(block)
            elif now - block.until > self.forget_after:
                block.strikes = 0
            seconds = min(self.base_block * 2**block.strikes, self.max_block)
            block.strikes += 1
            block.until = now + timedelta(seconds=seconds)
            db.commit()
            return seconds
