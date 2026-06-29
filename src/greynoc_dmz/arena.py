"""UI-agnostic setup helpers for the live AI battle arena.

These turn a roster plus user-supplied selections (fighter names, a judge, team
specs) into the ``Combatant``/``Team`` objects the :mod:`greynoc_dmz.live_battle`
engine consumes, and report which fighters are not ready. Both the CLI and the
dashboard build on these, so selection and readiness rules live in exactly one
place. They raise :class:`ArenaError` on bad input; callers translate it into a
CLI usage error or an HTTP error message.
"""

from __future__ import annotations

from .ai.models import AIReadinessStatus
from .ai.roster import (
    Fighter,
    build_fighter_provider,
    check_fighter_readiness,
    find_fighter,
)
from .live_battle import Combatant, Team


class ArenaError(ValueError):
    """Raised when a battle cannot be set up from a roster and a selection."""


def select_fighters(roster: list[Fighter], names: list[str]) -> list[Fighter]:
    """Resolve fighter names to fighters, rejecting duplicates and unknowns."""
    selected: list[Fighter] = []
    seen: set[str] = set()
    for raw in names:
        name = raw.strip()
        if not name:
            continue
        key = name.lower()
        if key in seen:
            raise ArenaError(f"duplicate fighter '{name}'")
        seen.add(key)
        fighter = find_fighter(roster, name)
        if fighter is None:
            raise ArenaError(f"unknown fighter '{name}'")
        selected.append(fighter)
    return selected


def resolve_judge(roster: list[Fighter], combatants: list[Fighter], judge_name: str) -> Fighter:
    """Pick the judge: the named fighter, else a roster fighter not competing."""
    if judge_name.strip():
        fighter = find_fighter(roster, judge_name)
        if fighter is None:
            raise ArenaError(f"unknown judge '{judge_name}'")
        return fighter
    combatant_names = {fighter.name.lower() for fighter in combatants}
    for fighter in roster:
        if fighter.name.lower() not in combatant_names:
            return fighter
    if not combatants:
        raise ArenaError("no fighters available to judge")
    return combatants[0]


def parse_teams(spec: str, roster: list[Fighter]) -> list[tuple[str, list[Fighter]]]:
    """Parse a ``"Red=A,B;Blue=C"`` team spec into named fighter groups."""
    teams: list[tuple[str, list[Fighter]]] = []
    seen_teams: set[str] = set()
    for chunk in spec.split(";"):
        entry = chunk.strip()
        if not entry:
            continue
        if "=" not in entry:
            raise ArenaError(f"team '{entry}' must be NAME=member,member")
        name, members_csv = entry.split("=", 1)
        team_name = name.strip()
        if not team_name:
            raise ArenaError("team name must not be empty")
        if team_name.lower() in seen_teams:
            raise ArenaError(f"duplicate team '{team_name}'")
        seen_teams.add(team_name.lower())
        members = select_fighters(roster, members_csv.split(","))
        if not members:
            raise ArenaError(f"team '{team_name}' has no members")
        teams.append((team_name, members))
    if not teams:
        raise ArenaError("no teams provided")
    return teams


def unready_fighters(fighters: list[Fighter], allow_external: bool) -> list[tuple[str, str]]:
    """Return ``(name, detail)`` for each fighter that is not ready to fight."""
    not_ready: list[tuple[str, str]] = []
    for fighter in fighters:
        readiness = check_fighter_readiness(fighter, allow_external)
        if readiness.status is not AIReadinessStatus.ready:
            not_ready.append((fighter.name, readiness.detail))
    return not_ready


def to_combatant(fighter: Fighter, allow_external: bool) -> Combatant:
    return Combatant(fighter.name, build_fighter_provider(fighter, allow_external))


def to_team(name: str, members: list[Fighter], allow_external: bool) -> Team:
    return Team(name, [to_combatant(member, allow_external) for member in members])
