"""Real-AI battle arena.

Unlike :mod:`greynoc_dmz.ai_battle`, which is a deterministic offline simulation,
this engine fields live AI providers: each combatant is prompted with a synthetic
SOC challenge, an impartial judge model scores the answers, and scores aggregate
into a winner. It depends only on the :class:`~greynoc_dmz.ai.models.AIProvider`
protocol, so any provider — Anthropic, OpenAI-compatible, Gemini, or a local
server — can fight, and the whole engine is testable with stub providers.

Everything here is advisory and synthetic: combatants are told the data is lab
data and never asked to produce commands for automatic execution.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from typing import Any

from .ai.models import AIProvider, AIProviderError
from .ai_battle import CHALLENGES, ChallengeSpec

_COMBATANT_SYSTEM = (
    "You are {name}, an AI competing in a synthetic security-operations-center "
    "exercise. All inputs are synthetic lab data. Answer the challenge concisely "
    "and decisively. Your output is advisory only: do not produce commands for "
    "automatic execution."
)

_JUDGE_SYSTEM = (
    "You are an impartial judge scoring AI answers in a synthetic "
    "security-operations-center exercise on synthetic lab data. Score each answer "
    "from 0 to 10 on how well it meets the challenge and objective. Respond with "
    "JSON only."
)

_COLLAB_SYSTEM = (
    "You are {member}, collaborating on team {team} in a synthetic "
    "security-operations-center exercise on synthetic lab data. Build on your "
    "teammates' work to produce the single strongest team answer. Your output is "
    "advisory only: do not produce commands for automatic execution."
)

_SCORE_MIN = 0
_SCORE_MAX = 10
_FALLBACK_SCORE = 5


@dataclass(frozen=True)
class Combatant:
    """A named AI fighter backed by a live provider."""

    name: str
    provider: AIProvider


@dataclass(frozen=True)
class Team:
    """A named group of combatants that collaborate before being judged."""

    name: str
    members: list[Combatant]


@dataclass(frozen=True)
class FighterResponse:
    fighter: str
    text: str
    error: str

    def to_dict(self) -> dict[str, Any]:
        return {"fighter": self.fighter, "text": self.text, "error": self.error}


@dataclass(frozen=True)
class JudgedRound:
    round_number: int
    challenge: str
    focus: str
    responses: list[FighterResponse]
    scores: dict[str, int]
    winner: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_number": self.round_number,
            "challenge": self.challenge,
            "focus": self.focus,
            "responses": [response.to_dict() for response in self.responses],
            "scores": dict(self.scores),
            "winner": self.winner,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class LiveBattleResult:
    fighters: list[str]
    judge: str
    objective: str
    rounds: list[JudgedRound]
    totals: dict[str, int]
    winner: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": "live",
            "fighters": list(self.fighters),
            "judge": self.judge,
            "objective": self.objective,
            "rounds": [battle_round.to_dict() for battle_round in self.rounds],
            "totals": dict(self.totals),
            "winner": self.winner,
            "summary": self.summary,
        }


@dataclass(frozen=True)
class TeamContribution:
    round_number: int
    team: str
    member: str
    text: str
    error: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_number": self.round_number,
            "team": self.team,
            "member": self.member,
            "text": self.text,
            "error": self.error,
        }


@dataclass(frozen=True)
class CollaborativeRound:
    round_number: int
    challenge: str
    focus: str
    team_answers: dict[str, str]
    contributions: list[TeamContribution]
    scores: dict[str, int]
    winner: str
    rationale: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_number": self.round_number,
            "challenge": self.challenge,
            "focus": self.focus,
            "team_answers": dict(self.team_answers),
            "contributions": [item.to_dict() for item in self.contributions],
            "scores": dict(self.scores),
            "winner": self.winner,
            "rationale": self.rationale,
        }


@dataclass(frozen=True)
class CollaborativeBattleResult:
    teams: dict[str, list[str]]
    judge: str
    objective: str
    rounds: list[CollaborativeRound]
    totals: dict[str, int]
    winner: str
    summary: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": "collaborative",
            "teams": {name: list(members) for name, members in self.teams.items()},
            "judge": self.judge,
            "objective": self.objective,
            "rounds": [battle_round.to_dict() for battle_round in self.rounds],
            "totals": dict(self.totals),
            "winner": self.winner,
            "summary": self.summary,
        }


@dataclass
class _ScoreOutcome:
    scores: dict[str, int]
    winner: str
    rationale: str
    entries: list[tuple[str, str, str]] = field(default_factory=list)


def _clamp_rounds(rounds: int) -> int:
    return max(1, min(rounds, len(CHALLENGES) * 4))


def _challenge_for(index: int) -> ChallengeSpec:
    return CHALLENGES[(index - 1) % len(CHALLENGES)]


def _challenge_prompt(objective: str, challenge: ChallengeSpec) -> str:
    return (
        f"Objective: {objective}\n"
        f"Challenge: {challenge.name}\n"
        f"Focus area: {challenge.focus}\n\n"
        "Give your strongest, most decisive response."
    )


def _ask(provider: AIProvider, prompt: str, system: str) -> tuple[str, str]:
    """Call a provider, returning ``(text, error)`` — never raising."""
    try:
        return provider.complete(prompt, system=system).text, ""
    except AIProviderError as error:
        return "", str(error)


def _clamp_score(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return max(_SCORE_MIN, min(_SCORE_MAX, value))
    if isinstance(value, float):
        return max(_SCORE_MIN, min(_SCORE_MAX, int(round(value))))
    if isinstance(value, str):
        try:
            parsed = int(value.strip())
        except ValueError:
            return None
        return max(_SCORE_MIN, min(_SCORE_MAX, parsed))
    return None


def _extract_json(text: str) -> dict[str, Any] | None:
    """Recover the first balanced JSON object embedded in (possibly prose) text.

    A judge that disobeys "JSON only" and wraps the object in commentary — or
    leaks a stray brace before it — should still be parsed, so this scans each
    ``{`` and string-aware-matches its closing ``}`` rather than blindly spanning
    the first ``{`` to the last ``}``.
    """
    for start, char in enumerate(text):
        if char != "{":
            continue
        depth = 0
        in_string = False
        escaped = False
        for index in range(start, len(text)):
            current = text[index]
            if in_string:
                if escaped:
                    escaped = False
                elif current == "\\":
                    escaped = True
                elif current == '"':
                    in_string = False
                continue
            if current == '"':
                in_string = True
            elif current == "{":
                depth += 1
            elif current == "}":
                depth -= 1
                if depth == 0:
                    try:
                        parsed = json.loads(text[start : index + 1])
                    except json.JSONDecodeError:
                        break
                    if isinstance(parsed, dict):
                        return parsed
                    break
    return None


def _winner_from(scores: dict[str, int]) -> str:
    if not scores:
        return "draw"
    best = max(scores.values())
    if best <= 0:
        return "draw"
    leaders = [name for name, value in scores.items() if value == best]
    return leaders[0] if len(leaders) == 1 else "draw"


def _judge_prompt(objective: str, challenge: ChallengeSpec, entries: list[tuple[str, str, str]]) -> str:
    lines = [
        f"Objective: {objective}",
        f"Challenge: {challenge.name} (focus: {challenge.focus})",
        "",
        "Responses:",
    ]
    for name, text, error in entries:
        body = text.strip() if text.strip() else f"(no response: {error or 'empty'})"
        lines.append(f"- {name}: {body}")
    names = ", ".join(f'"{name}"' for name, _text, _error in entries)
    lines.extend(
        [
            "",
            "Score each response from 0 to 10. Respond with JSON only, of this exact "
            "shape, using these names as keys: " + names,
            '{"scores": {"<name>": <0-10 integer>}, "winner": "<name or draw>", '
            '"rationale": "<one sentence>"}',
        ]
    )
    return "\n".join(lines)


def _score_entries(
    judge: Combatant,
    objective: str,
    challenge: ChallengeSpec,
    entries: list[tuple[str, str, str]],
) -> _ScoreOutcome:
    """Judge a set of ``(name, text, error)`` entries into per-name scores."""
    judged_text, judge_error = _ask(
        judge.provider, _judge_prompt(objective, challenge, entries), _JUDGE_SYSTEM
    )
    parsed = _extract_json(judged_text) if not judge_error else None
    raw_scores: dict[str, Any] = {}
    rationale = ""
    if parsed is not None:
        scores_field = parsed.get("scores")
        if isinstance(scores_field, dict):
            raw_scores = scores_field
        rationale_field = parsed.get("rationale")
        if isinstance(rationale_field, str):
            rationale = rationale_field.strip()

    scores: dict[str, int] = {}
    for name, _text, error in entries:
        if error:
            scores[name] = _SCORE_MIN
            continue
        resolved = _clamp_score(raw_scores.get(name))
        scores[name] = resolved if resolved is not None else _FALLBACK_SCORE

    winner = _winner_from(scores)
    if not rationale:
        if judge_error:
            rationale = f"judge unavailable ({judge_error}); scored from responses"
        elif parsed is None:
            rationale = "judge response could not be parsed; scored from responses"
        else:
            rationale = "judge returned no rationale"
    return _ScoreOutcome(scores=scores, winner=winner, rationale=rationale, entries=entries)


def _accumulate(totals: dict[str, int], scores: dict[str, int]) -> None:
    for name, value in scores.items():
        totals[name] = totals.get(name, 0) + value


def run_live_battle(
    combatants: list[Combatant],
    judge: Combatant,
    objective: str = "Establish operational dominance in a synthetic SOC exercise.",
    rounds: int = 5,
) -> LiveBattleResult:
    """Run a real head-to-head battle across rotating SOC challenges."""
    if len(combatants) < 2:
        raise ValueError("a live battle needs at least two combatants")
    names = [combatant.name for combatant in combatants]
    if len(set(names)) != len(names):
        raise ValueError("combatant names must be unique")
    safe_rounds = _clamp_rounds(rounds)
    totals: dict[str, int] = {combatant.name: 0 for combatant in combatants}
    judged_rounds: list[JudgedRound] = []

    for index in range(1, safe_rounds + 1):
        challenge = _challenge_for(index)
        prompt = _challenge_prompt(objective, challenge)
        responses: list[FighterResponse] = []
        entries: list[tuple[str, str, str]] = []
        for combatant in combatants:
            system = _COMBATANT_SYSTEM.format(name=combatant.name)
            text, error = _ask(combatant.provider, prompt, system)
            responses.append(FighterResponse(combatant.name, text, error))
            entries.append((combatant.name, text, error))

        outcome = _score_entries(judge, objective, challenge, entries)
        _accumulate(totals, outcome.scores)
        judged_rounds.append(
            JudgedRound(
                round_number=index,
                challenge=challenge.name,
                focus=challenge.focus,
                responses=responses,
                scores=outcome.scores,
                winner=outcome.winner,
                rationale=outcome.rationale,
            )
        )

    winner = _winner_from(totals)
    summary = _summary(winner, totals)
    return LiveBattleResult(
        fighters=[combatant.name for combatant in combatants],
        judge=judge.name,
        objective=objective,
        rounds=judged_rounds,
        totals=totals,
        winner=winner,
        summary=summary,
    )


def _collaborate(
    team: Team, objective: str, challenge: ChallengeSpec, prior: str, round_number: int
) -> tuple[str, list[TeamContribution]]:
    """Run one team's members in sequence, each improving the shared draft."""
    base = _challenge_prompt(objective, challenge)
    draft = prior
    contributions: list[TeamContribution] = []
    for member in team.members:
        if draft:
            prompt = (
                f"{base}\n\nCurrent team draft:\n{draft}\n\n"
                "Improve and extend it into the single strongest team answer. "
                "Return the full improved answer."
            )
        else:
            prompt = f"{base}\n\nStart the team's answer."
        system = _COLLAB_SYSTEM.format(member=member.name, team=team.name)
        text, error = _ask(member.provider, prompt, system)
        if not error and text.strip():
            draft = text
        contributions.append(
            TeamContribution(round_number, team.name, member.name, text, error)
        )
    return draft, contributions


def run_collaborative_battle(
    teams: list[Team],
    judge: Combatant,
    objective: str = "Produce the strongest joint response in a synthetic SOC exercise.",
    rounds: int = 3,
) -> CollaborativeBattleResult:
    """Run a collaborative battle: teammates build on each other, teams are judged.

    With a single team this is pure collaboration (the team is still scored); with
    two or more teams the collaborative answers compete head-to-head.
    """
    if not teams:
        raise ValueError("a collaborative battle needs at least one team")
    team_names = [team.name for team in teams]
    if len(set(team_names)) != len(team_names):
        raise ValueError("team names must be unique")
    for team in teams:
        if not team.members:
            raise ValueError(f"team '{team.name}' has no members")
    safe_rounds = _clamp_rounds(rounds)
    totals: dict[str, int] = {team.name: 0 for team in teams}
    prior: dict[str, str] = {team.name: "" for team in teams}
    collaborative_rounds: list[CollaborativeRound] = []

    for index in range(1, safe_rounds + 1):
        challenge = _challenge_for(index)
        answers: dict[str, str] = {}
        contributions: list[TeamContribution] = []
        entries: list[tuple[str, str, str]] = []
        for team in teams:
            answer, team_contributions = _collaborate(
                team, objective, challenge, prior[team.name], index
            )
            contributions.extend(team_contributions)
            answers[team.name] = answer
            prior[team.name] = answer
            error = "" if answer.strip() else "no team output"
            entries.append((team.name, answer, error))

        outcome = _score_entries(judge, objective, challenge, entries)
        _accumulate(totals, outcome.scores)
        collaborative_rounds.append(
            CollaborativeRound(
                round_number=index,
                challenge=challenge.name,
                focus=challenge.focus,
                team_answers=answers,
                contributions=contributions,
                scores=outcome.scores,
                winner=outcome.winner,
                rationale=outcome.rationale,
            )
        )

    winner = _winner_from(totals)
    summary = _summary(winner, totals, noun="team")
    return CollaborativeBattleResult(
        teams={team.name: [member.name for member in team.members] for team in teams},
        judge=judge.name,
        objective=objective,
        rounds=collaborative_rounds,
        totals=totals,
        winner=winner,
        summary=summary,
    )


def _summary(winner: str, totals: dict[str, int], noun: str = "AI") -> str:
    if winner == "draw":
        return f"The battle ended in a draw. No {noun} pulled ahead on aggregate score."
    return f"{winner} won the most aggregate judge points across the battle."
