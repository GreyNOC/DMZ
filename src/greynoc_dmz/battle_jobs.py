"""Background battle jobs.

Live battles make many sequential model calls and can run for a minute or more.
Running them in a request handler would block the browser, so the dashboard hands
each battle to this store: a worker thread runs the battle while the page polls
for progress (via a no-JavaScript meta refresh) and shows rounds as they land.

The store is thread-safe and in-memory: a worker thread mutates a job's progress
under a lock, and ``get`` returns an immutable snapshot for rendering.
"""

from __future__ import annotations

import threading
import uuid
from dataclasses import dataclass, field

from .live_battle import (
    CollaborativeBattleResult,
    CollaborativeRound,
    Combatant,
    JudgedRound,
    LiveBattleResult,
    Team,
    run_collaborative_battle,
    run_live_battle,
)

STATUS_PENDING = "pending"
STATUS_RUNNING = "running"
STATUS_DONE = "done"
STATUS_ERROR = "error"

MODE_LIVE = "live"
MODE_COLLAB = "collaborative"

_MAX_JOBS = 50

BattleResult = LiveBattleResult | CollaborativeBattleResult
BattleRound = JudgedRound | CollaborativeRound


@dataclass
class _Job:
    id: str
    mode: str
    label: dict[str, object]
    objective: str
    total_rounds: int
    status: str = STATUS_PENDING
    partial: list[BattleRound] = field(default_factory=list)
    result: BattleResult | None = None
    error: str = ""


@dataclass(frozen=True)
class BattleJobView:
    """An immutable snapshot of a job, safe to render outside the lock."""

    id: str
    mode: str
    label: dict[str, object]
    objective: str
    total_rounds: int
    status: str
    rounds_done: int
    partial: tuple[BattleRound, ...]
    result: BattleResult | None
    error: str

    @property
    def finished(self) -> bool:
        return self.status in {STATUS_DONE, STATUS_ERROR}


class JobStore:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._jobs: dict[str, _Job] = {}

    def create_live(
        self,
        label: dict[str, object],
        combatants: list[Combatant],
        judge: Combatant,
        objective: str,
        rounds: int,
    ) -> str:
        job = _Job(
            id=uuid.uuid4().hex, mode=MODE_LIVE, label=label, objective=objective, total_rounds=rounds
        )
        self._register(job)
        threading.Thread(
            target=self._run_live,
            args=(job.id, combatants, judge, objective, rounds),
            daemon=True,
        ).start()
        return job.id

    def create_collab(
        self,
        label: dict[str, object],
        teams: list[Team],
        judge: Combatant,
        objective: str,
        rounds: int,
    ) -> str:
        job = _Job(
            id=uuid.uuid4().hex,
            mode=MODE_COLLAB,
            label=label,
            objective=objective,
            total_rounds=rounds,
        )
        self._register(job)
        threading.Thread(
            target=self._run_collab,
            args=(job.id, teams, judge, objective, rounds),
            daemon=True,
        ).start()
        return job.id

    def get(self, job_id: str) -> BattleJobView | None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is None:
                return None
            return BattleJobView(
                id=job.id,
                mode=job.mode,
                label=dict(job.label),
                objective=job.objective,
                total_rounds=job.total_rounds,
                status=job.status,
                rounds_done=len(job.partial),
                partial=tuple(job.partial),
                result=job.result,
                error=job.error,
            )

    def _register(self, job: _Job) -> None:
        with self._lock:
            self._jobs[job.id] = job
            self._evict_locked()

    def _evict_locked(self) -> None:
        # Drop the oldest finished jobs once the cap is exceeded; never evict a
        # job that is still running.
        while len(self._jobs) > _MAX_JOBS:
            for job_id, job in list(self._jobs.items()):
                if job.status in {STATUS_DONE, STATUS_ERROR}:
                    del self._jobs[job_id]
                    break
            else:
                break

    def _set_status(self, job_id: str, status: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.status = status

    def _append_round(self, job_id: str, battle_round: BattleRound) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.partial.append(battle_round)

    def _complete(self, job_id: str, result: BattleResult) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.result = result
                job.status = STATUS_DONE

    def _fail(self, job_id: str, message: str) -> None:
        with self._lock:
            job = self._jobs.get(job_id)
            if job is not None:
                job.error = message
                job.status = STATUS_ERROR

    def _run_live(
        self,
        job_id: str,
        combatants: list[Combatant],
        judge: Combatant,
        objective: str,
        rounds: int,
    ) -> None:
        self._set_status(job_id, STATUS_RUNNING)
        try:
            result = run_live_battle(
                combatants,
                judge,
                objective,
                rounds,
                on_round=lambda battle_round: self._append_round(job_id, battle_round),
            )
        except Exception as error:  # noqa: BLE001 - a worker thread must record any failure
            self._fail(job_id, str(error))
            return
        self._complete(job_id, result)

    def _run_collab(
        self,
        job_id: str,
        teams: list[Team],
        judge: Combatant,
        objective: str,
        rounds: int,
    ) -> None:
        self._set_status(job_id, STATUS_RUNNING)
        try:
            result = run_collaborative_battle(
                teams,
                judge,
                objective,
                rounds,
                on_round=lambda battle_round: self._append_round(job_id, battle_round),
            )
        except Exception as error:  # noqa: BLE001 - a worker thread must record any failure
            self._fail(job_id, str(error))
            return
        self._complete(job_id, result)


# Process-wide store shared by the dashboard handler threads.
JOBS = JobStore()
