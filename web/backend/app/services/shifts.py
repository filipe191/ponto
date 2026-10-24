"""Jornadas: pares entrada→saída, inclusive as que passam da meia-noite."""

from collections.abc import Callable
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.models import Punch, PunchType
from app.utils.dates import to_local


@dataclass
class Shift:
    punches: list[Punch]  # [entrada, saída] quando completa; uma batida só quando ficou sem par
    complete: bool
    pending: bool = False  # última entrada do funcionário, ainda sem saída
    tz: ZoneInfo | None = None  # fuso da empresa (define o dia da jornada)

    @property
    def start(self) -> datetime:
        return self.punches[0].ts

    @property
    def day(self) -> date:
        """A jornada conta no dia (local) em que começou."""
        return to_local(self.start, self.tz).date()

    @property
    def worked(self) -> timedelta:
        return self.punches[1].ts - self.punches[0].ts if self.complete else timedelta(0)

    def is_open(self, now: datetime, max_shift: timedelta) -> bool:
        """Entrada sem saída que ainda pode ser fechada (funcionário trabalhando agora)."""
        return self.pending and now - self.start <= max_shift


def pair_shifts(
    punches: list[Punch],
    max_shift: timedelta | Callable[[datetime], timedelta],
    tz: ZoneInfo | None = None,
) -> list[Shift]:
    """Monta as jornadas de UM funcionário. As batidas vêm em ordem de horário, sem as excluídas.

    Uma saída fecha a entrada anterior se vier até `max_shift` depois dela; o que sobra sem
    par vira uma jornada incompleta. `max_shift` pode depender do horário da entrada (regra em vigor
    no dia, ver RuleBook.max_shift_at).
    """
    limit = max_shift if callable(max_shift) else (lambda _ts: max_shift)
    shifts: list[Shift] = []
    open_entry: Punch | None = None
    for p in punches:
        if p.type == PunchType.ENTRADA:
            if open_entry:
                shifts.append(Shift([open_entry], complete=False, tz=tz))
            open_entry = p
        elif open_entry and p.ts - open_entry.ts <= limit(open_entry.ts):
            shifts.append(Shift([open_entry, p], complete=True, tz=tz))
            open_entry = None
        else:
            if open_entry:
                shifts.append(Shift([open_entry], complete=False, tz=tz))
                open_entry = None
            shifts.append(Shift([p], complete=False, tz=tz))
    if open_entry:
        shifts.append(Shift([open_entry], complete=False, pending=True, tz=tz))
    return shifts
