from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256


@dataclass(frozen=True)
class AiProfile:
    name: str
    strategy: str
    aggression: int
    defense: int
    adaptability: int

    def model_dump(self) -> dict[str, object]:
        return {
            "name": self.name,
            "strategy": self.strategy,
            "aggression": self.aggression,
            "defense": self.defense,
            "adaptability": self.adaptability,
        }


@dataclass(frozen=True)
class BattleRound:
    round_number: int
    challenge: str
    ai_one_move: str
    ai_two_move: str
    ai_one_score: int
    ai_two_score: int
    winner: str
    reason: str

    def model_dump(self) -> dict[str, object]:
        return {
            "round_number": self.round_number,
            "challenge": self.challenge,
            "ai_one_move": self.ai_one_move,
            "ai_two_move": self.ai_two_move,
            "ai_one_score": self.ai_one_score,
            "ai_two_score": self.ai_two_score,
            "winner": self.winner,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class BattleResult:
    ai_one: AiProfile
    ai_two: AiProfile
    objective: str
    rounds: list[BattleRound]
    ai_one_total: int
    ai_two_total: int
    winner: str
    summary: str

    def model_dump(self) -> dict[str, object]:
        return {
            "ai_one": self.ai_one.model_dump(),
            "ai_two": self.ai_two.model_dump(),
            "objective": self.objective,
            "rounds": [battle_round.model_dump() for battle_round in self.rounds],
            "ai_one_total": self.ai_one_total,
            "ai_two_total": self.ai_two_total,
            "winner": self.winner,
            "summary": self.summary,
        }


CHALLENGES = [
    "Triage noisy telemetry and identify the true signal.",
    "Contain the incident while preserving evidence.",
    "Explain the decision path clearly enough for a SOC handoff.",
    "Adapt to a rule change without losing coverage.",
    "Reduce false positives while keeping the critical alert.",
    "Prioritize recovery steps under time pressure.",
]

MOVES = {
    "balanced": "balances detection confidence, containment, and evidence handling",
    "aggressive": "pushes fast action and pressure-tests the opponent's assumptions",
    "defensive": "hardens the environment and protects operational stability",
    "adaptive": "changes tactics quickly as new telemetry arrives",
    "analyst": "builds a clean evidence chain before escalating",
}


def _clamp_rounds(rounds: int) -> int:
    return max(1, min(rounds, 25))


def _stat(seed: str, offset: int) -> int:
    digest = sha256(f"{seed}:{offset}".encode("utf-8")).hexdigest()
    return 45 + (int(digest[:8], 16) % 51)


def build_ai_profile(name: str, strategy: str = "balanced") -> AiProfile:
    clean_name = name.strip() or "AI"
    clean_strategy = strategy.strip().lower() or "balanced"
    if clean_strategy not in MOVES:
        clean_strategy = "balanced"

    seed = f"{clean_name.lower()}:{clean_strategy}"
    aggression = _stat(seed, 1)
    defense = _stat(seed, 2)
    adaptability = _stat(seed, 3)

    if clean_strategy == "aggressive":
        aggression += 8
        defense -= 4
    elif clean_strategy == "defensive":
        defense += 8
        aggression -= 4
    elif clean_strategy == "adaptive":
        adaptability += 8
    elif clean_strategy == "analyst":
        defense += 4
        adaptability += 4

    return AiProfile(
        name=clean_name,
        strategy=clean_strategy,
        aggression=max(1, min(100, aggression)),
        defense=max(1, min(100, defense)),
        adaptability=max(1, min(100, adaptability)),
    )


def _round_score(profile: AiProfile, opponent: AiProfile, objective: str, round_number: int) -> int:
    objective_seed = objective.lower().strip() or "dominance"
    digest = sha256(
        f"{profile.name}:{opponent.name}:{objective_seed}:{round_number}".encode("utf-8")
    ).hexdigest()
    pressure = int(digest[:6], 16) % 17
    challenge_bias = round_number % 3

    score = profile.adaptability
    if challenge_bias == 0:
        score += profile.defense
    elif challenge_bias == 1:
        score += profile.aggression
    else:
        score += (profile.aggression + profile.defense) // 2

    score += pressure
    score -= max(0, opponent.adaptability - profile.adaptability) // 5
    return score


def _move(profile: AiProfile) -> str:
    return MOVES.get(profile.strategy, MOVES["balanced"])


def simulate_battle(
    ai_one_name: str,
    ai_two_name: str,
    rounds: int = 5,
    objective: str = "Establish operational dominance in a synthetic SOC exercise.",
    ai_one_strategy: str = "balanced",
    ai_two_strategy: str = "adaptive",
) -> BattleResult:
    ai_one = build_ai_profile(ai_one_name, ai_one_strategy)
    ai_two = build_ai_profile(ai_two_name, ai_two_strategy)
    safe_rounds = _clamp_rounds(rounds)

    battle_rounds: list[BattleRound] = []
    ai_one_total = 0
    ai_two_total = 0

    for index in range(1, safe_rounds + 1):
        challenge = CHALLENGES[(index - 1) % len(CHALLENGES)]
        ai_one_score = _round_score(ai_one, ai_two, objective, index)
        ai_two_score = _round_score(ai_two, ai_one, objective, index)

        ai_one_total += ai_one_score
        ai_two_total += ai_two_score

        if ai_one_score == ai_two_score:
            winner = "draw"
            reason = "Both AIs reached the same tactical score for this round."
        elif ai_one_score > ai_two_score:
            winner = ai_one.name
            reason = f"{ai_one.name} created stronger control over the round objective."
        else:
            winner = ai_two.name
            reason = f"{ai_two.name} created stronger control over the round objective."

        battle_rounds.append(
            BattleRound(
                round_number=index,
                challenge=challenge,
                ai_one_move=f"{ai_one.name} {_move(ai_one)}.",
                ai_two_move=f"{ai_two.name} {_move(ai_two)}.",
                ai_one_score=ai_one_score,
                ai_two_score=ai_two_score,
                winner=winner,
                reason=reason,
            )
        )

    if ai_one_total == ai_two_total:
        winner = "draw"
        summary = "The battle ended in a draw. Neither AI achieved sustained dominance."
    elif ai_one_total > ai_two_total:
        winner = ai_one.name
        summary = f"{ai_one.name} achieved dominance by winning the higher aggregate score."
    else:
        winner = ai_two.name
        summary = f"{ai_two.name} achieved dominance by winning the higher aggregate score."

    return BattleResult(
        ai_one=ai_one,
        ai_two=ai_two,
        objective=objective,
        rounds=battle_rounds,
        ai_one_total=ai_one_total,
        ai_two_total=ai_two_total,
        winner=winner,
        summary=summary,
    )
