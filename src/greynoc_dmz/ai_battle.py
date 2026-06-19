from __future__ import annotations

from dataclasses import dataclass
from hashlib import sha256
from statistics import mean, pstdev
from typing import Any


@dataclass(frozen=True)
class AiProfile:
    name: str
    strategy: str
    aggression: int
    defense: int
    adaptability: int

    @property
    def power(self) -> int:
        """Combined stat total, used as a pre-battle strength estimate."""
        return self.aggression + self.defense + self.adaptability

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "strategy": self.strategy,
            "aggression": self.aggression,
            "defense": self.defense,
            "adaptability": self.adaptability,
            "power": self.power,
        }


@dataclass(frozen=True)
class StatWeights:
    """How much each stat drives a given challenge. Components sum to 1.0."""

    aggression: float
    defense: float
    adaptability: float

    def primary(self) -> str:
        pairs = (
            ("aggression", self.aggression),
            ("defense", self.defense),
            ("adaptability", self.adaptability),
        )
        return max(pairs, key=lambda pair: pair[1])[0]


@dataclass(frozen=True)
class ChallengeSpec:
    name: str
    focus: str
    weights: StatWeights


@dataclass(frozen=True)
class BattleRound:
    round_number: int
    challenge: str
    focus: str
    ai_one_move: str
    ai_two_move: str
    ai_one_score: int
    ai_two_score: int
    margin: int
    winner: str
    reason: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "round_number": self.round_number,
            "challenge": self.challenge,
            "focus": self.focus,
            "ai_one_move": self.ai_one_move,
            "ai_two_move": self.ai_two_move,
            "ai_one_score": self.ai_one_score,
            "ai_two_score": self.ai_two_score,
            "margin": self.margin,
            "winner": self.winner,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class ChallengeBreakdown:
    challenge: str
    focus: str
    ai_one_score: int
    ai_two_score: int
    winner: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "challenge": self.challenge,
            "focus": self.focus,
            "ai_one_score": self.ai_one_score,
            "ai_two_score": self.ai_two_score,
            "winner": self.winner,
        }


@dataclass(frozen=True)
class BattleStats:
    ai_one_round_wins: int
    ai_two_round_wins: int
    draws: int
    ai_one_avg: float
    ai_two_avg: float
    ai_one_consistency: float
    ai_two_consistency: float
    ai_one_best_round: int
    ai_two_best_round: int
    largest_margin: int
    closest_margin: int
    ai_one_longest_streak: int
    ai_two_longest_streak: int
    lead_changes: int
    lead_timeline: list[int]
    comeback_winner: str
    decisiveness: str
    predicted_winner: str
    upset: bool
    dominance_share_one: float
    dominance_share_two: float
    per_challenge: list[ChallengeBreakdown]

    def to_dict(self) -> dict[str, Any]:
        return {
            "ai_one_round_wins": self.ai_one_round_wins,
            "ai_two_round_wins": self.ai_two_round_wins,
            "draws": self.draws,
            "ai_one_avg": self.ai_one_avg,
            "ai_two_avg": self.ai_two_avg,
            "ai_one_consistency": self.ai_one_consistency,
            "ai_two_consistency": self.ai_two_consistency,
            "ai_one_best_round": self.ai_one_best_round,
            "ai_two_best_round": self.ai_two_best_round,
            "largest_margin": self.largest_margin,
            "closest_margin": self.closest_margin,
            "ai_one_longest_streak": self.ai_one_longest_streak,
            "ai_two_longest_streak": self.ai_two_longest_streak,
            "lead_changes": self.lead_changes,
            "lead_timeline": list(self.lead_timeline),
            "comeback_winner": self.comeback_winner,
            "decisiveness": self.decisiveness,
            "predicted_winner": self.predicted_winner,
            "upset": self.upset,
            "dominance_share_one": self.dominance_share_one,
            "dominance_share_two": self.dominance_share_two,
            "per_challenge": [item.to_dict() for item in self.per_challenge],
        }


@dataclass(frozen=True)
class BattleResult:
    ai_one: AiProfile
    ai_two: AiProfile
    objective: str
    emphasis: str
    seed: str
    rounds: list[BattleRound]
    ai_one_total: int
    ai_two_total: int
    winner: str
    summary: str
    stats: BattleStats

    def to_dict(self) -> dict[str, Any]:
        return {
            "ai_one": self.ai_one.to_dict(),
            "ai_two": self.ai_two.to_dict(),
            "objective": self.objective,
            "emphasis": self.emphasis,
            "seed": self.seed,
            "rounds": [battle_round.to_dict() for battle_round in self.rounds],
            "ai_one_total": self.ai_one_total,
            "ai_two_total": self.ai_two_total,
            "winner": self.winner,
            "summary": self.summary,
            "stats": self.stats.to_dict(),
        }


CHALLENGES: tuple[ChallengeSpec, ...] = (
    ChallengeSpec(
        "Triage noisy telemetry and identify the true signal.",
        "telemetry triage",
        StatWeights(0.30, 0.20, 0.50),
    ),
    ChallengeSpec(
        "Contain the incident while preserving evidence.",
        "containment",
        StatWeights(0.25, 0.55, 0.20),
    ),
    ChallengeSpec(
        "Explain the decision path clearly enough for a SOC handoff.",
        "analyst handoff",
        StatWeights(0.15, 0.40, 0.45),
    ),
    ChallengeSpec(
        "Adapt to a rule change without losing coverage.",
        "rule adaptation",
        StatWeights(0.20, 0.20, 0.60),
    ),
    ChallengeSpec(
        "Reduce false positives while keeping the critical alert.",
        "false-positive control",
        StatWeights(0.20, 0.45, 0.35),
    ),
    ChallengeSpec(
        "Prioritize recovery steps under time pressure.",
        "recovery under pressure",
        StatWeights(0.50, 0.30, 0.20),
    ),
)

MOVES = {
    "balanced": "balances detection confidence, containment, and evidence handling",
    "aggressive": "pushes fast action and pressure-tests the opponent's assumptions",
    "defensive": "hardens the environment and protects operational stability",
    "adaptive": "changes tactics quickly as new telemetry arrives",
    "analyst": "builds a clean evidence chain before escalating",
}

# Strategy is a visible modifier applied on top of name-seeded base stats, so the
# same fighter keeps the same base block and the strategy choice is an isolated lever.
# Modifiers are zero-sum: strategy reshapes a fighter without changing total power, so
# identity sets how strong a fighter is and strategy sets how that strength is spent.
STRATEGY_MODIFIERS: dict[str, dict[str, int]] = {
    "balanced": {"aggression": 0, "defense": 0, "adaptability": 0},
    "aggressive": {"aggression": 12, "defense": -6, "adaptability": -6},
    "defensive": {"aggression": -6, "defense": 12, "adaptability": -6},
    "adaptive": {"aggression": -6, "defense": -6, "adaptability": 12},
    "analyst": {"aggression": -8, "defense": 4, "adaptability": 4},
}

_STAT_NAMES = ("aggression", "defense", "adaptability")

# Objectives reward a stat. Keyword hits make the objective text readable; otherwise
# the text is hashed to a stat so every objective still means something deterministic.
_OBJECTIVE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "defense": ("evidence", "preserve", "stability", "protect", "harden", "integrity"),
    "aggression": ("dominance", "own", "fast", "pressure", "offensive", "pursue"),
    "adaptability": ("adapt", "change", "pivot", "flex", "shift", "evolve"),
}

_DECISIVENESS_TIERS = (
    (0.80, "blowout"),
    (0.65, "clear"),
    (0.55, "narrow"),
)

_MAX_ROUNDS = 25
_PRESSURE_SPAN = 21
_MAX_CATCHUP = 12.0
_EMPHASIS_WEIGHT = 0.10


def _clamp_rounds(rounds: int) -> int:
    return max(1, min(rounds, _MAX_ROUNDS))


def _clamp_stat(value: int) -> int:
    return max(1, min(100, value))


def _stat(seed: str, offset: int) -> int:
    digest = sha256(f"{seed}:{offset}".encode()).hexdigest()
    return 45 + (int(digest[:8], 16) % 51)


def _stat_value(profile: AiProfile, stat: str) -> int:
    if stat == "aggression":
        return profile.aggression
    if stat == "defense":
        return profile.defense
    return profile.adaptability


def objective_emphasis(objective: str) -> str:
    """Return the stat an objective rewards, by keyword first then by hash."""
    key = objective.lower().strip()
    if not key:
        return "adaptability"
    for stat, keywords in _OBJECTIVE_KEYWORDS.items():
        if any(word in key for word in keywords):
            return stat
    digest = sha256(key.encode()).hexdigest()
    return _STAT_NAMES[int(digest[:2], 16) % 3]


def build_ai_profile(name: str, strategy: str = "balanced") -> AiProfile:
    clean_name = name.strip() or "AI"
    clean_strategy = strategy.strip().lower() or "balanced"
    if clean_strategy not in STRATEGY_MODIFIERS:
        clean_strategy = "balanced"

    seed = clean_name.lower()
    modifier = STRATEGY_MODIFIERS[clean_strategy]
    return AiProfile(
        name=clean_name,
        strategy=clean_strategy,
        aggression=_clamp_stat(_stat(seed, 1) + modifier["aggression"]),
        defense=_clamp_stat(_stat(seed, 2) + modifier["defense"]),
        adaptability=_clamp_stat(_stat(seed, 3) + modifier["adaptability"]),
    )


def _round_score(
    profile: AiProfile,
    opponent: AiProfile,
    challenge: ChallengeSpec,
    round_number: int,
    seed: str,
    emphasis: str,
    trailing_by: int,
) -> int:
    weights = challenge.weights
    base = (
        profile.aggression * weights.aggression
        + profile.defense * weights.defense
        + profile.adaptability * weights.adaptability
    )
    emphasis_bonus = _stat_value(profile, emphasis) * _EMPHASIS_WEIGHT

    digest = sha256(
        f"{seed}:{profile.name}:{opponent.name}:{round_number}".encode()
    ).hexdigest()
    pressure = int(digest[:6], 16) % _PRESSURE_SPAN

    # Momentum: a trailing profile adapts, clawing back in proportion to its
    # adaptability. This couples rounds together and lets fights swing.
    catchup = 0.0
    if trailing_by > 0:
        catchup = (profile.adaptability / 100.0) * min(_MAX_CATCHUP, trailing_by / 2.0)

    return int(round(base + emphasis_bonus + pressure + catchup))


def _move(profile: AiProfile, challenge: ChallengeSpec) -> str:
    descriptor = MOVES.get(profile.strategy, MOVES["balanced"])
    return f"{profile.name} {descriptor} during {challenge.focus}."


def _longest_streak(rounds: list[BattleRound], side: str) -> int:
    best = 0
    current = 0
    for battle_round in rounds:
        if side == "one":
            won = battle_round.ai_one_score > battle_round.ai_two_score
        else:
            won = battle_round.ai_two_score > battle_round.ai_one_score
        current = current + 1 if won else 0
        best = max(best, current)
    return best


def _lead_changes(timeline: list[int]) -> int:
    changes = 0
    previous_sign = 0
    for value in timeline:
        sign = (value > 0) - (value < 0)
        if sign != 0 and previous_sign != 0 and sign != previous_sign:
            changes += 1
        if sign != 0:
            previous_sign = sign
    return changes


def _decisiveness(lead_wins: int, total_rounds: int) -> str:
    share = lead_wins / total_rounds if total_rounds else 0.0
    for threshold, label in _DECISIVENESS_TIERS:
        if share >= threshold:
            return label
    return "coin-flip"


def _per_challenge(rounds: list[BattleRound], one_name: str, two_name: str) -> list[ChallengeBreakdown]:
    order: list[str] = []
    one_sums: dict[str, int] = {}
    two_sums: dict[str, int] = {}
    focus: dict[str, str] = {}
    for battle_round in rounds:
        name = battle_round.challenge
        if name not in one_sums:
            order.append(name)
            one_sums[name] = 0
            two_sums[name] = 0
            focus[name] = battle_round.focus
        one_sums[name] += battle_round.ai_one_score
        two_sums[name] += battle_round.ai_two_score

    breakdowns: list[ChallengeBreakdown] = []
    for name in order:
        one_score = one_sums[name]
        two_score = two_sums[name]
        if one_score == two_score:
            winner = "draw"
        elif one_score > two_score:
            winner = one_name
        else:
            winner = two_name
        breakdowns.append(
            ChallengeBreakdown(
                challenge=name,
                focus=focus[name],
                ai_one_score=one_score,
                ai_two_score=two_score,
                winner=winner,
            )
        )
    return breakdowns


def _build_stats(
    rounds: list[BattleRound],
    ai_one: AiProfile,
    ai_two: AiProfile,
    ai_one_total: int,
    ai_two_total: int,
    winner: str,
) -> BattleStats:
    one_scores = [battle_round.ai_one_score for battle_round in rounds]
    two_scores = [battle_round.ai_two_score for battle_round in rounds]
    # Tally by score, not by name, so two fighters sharing a name never double-count.
    one_wins = sum(1 for battle_round in rounds if battle_round.margin > 0)
    two_wins = sum(1 for battle_round in rounds if battle_round.margin < 0)
    draws = sum(1 for battle_round in rounds if battle_round.margin == 0)

    timeline: list[int] = []
    running = 0
    for battle_round in rounds:
        running += battle_round.margin
        timeline.append(running)

    margins = [abs(battle_round.margin) for battle_round in rounds]
    total_points = ai_one_total + ai_two_total

    comeback_winner = ""
    if winner == ai_one.name and any(value < 0 for value in timeline):
        comeback_winner = ai_one.name
    elif winner == ai_two.name and any(value > 0 for value in timeline):
        comeback_winner = ai_two.name

    if ai_one.power > ai_two.power:
        predicted_winner = ai_one.name
    elif ai_two.power > ai_one.power:
        predicted_winner = ai_two.name
    else:
        predicted_winner = "draw"
    upset = winner != predicted_winner and winner != "draw" and predicted_winner != "draw"

    return BattleStats(
        ai_one_round_wins=one_wins,
        ai_two_round_wins=two_wins,
        draws=draws,
        ai_one_avg=round(mean(one_scores), 1),
        ai_two_avg=round(mean(two_scores), 1),
        ai_one_consistency=round(pstdev(one_scores), 1) if len(one_scores) > 1 else 0.0,
        ai_two_consistency=round(pstdev(two_scores), 1) if len(two_scores) > 1 else 0.0,
        ai_one_best_round=max(one_scores),
        ai_two_best_round=max(two_scores),
        largest_margin=max(margins),
        closest_margin=min(margins),
        ai_one_longest_streak=_longest_streak(rounds, "one"),
        ai_two_longest_streak=_longest_streak(rounds, "two"),
        lead_changes=_lead_changes(timeline),
        lead_timeline=timeline,
        comeback_winner=comeback_winner,
        decisiveness=_decisiveness(max(one_wins, two_wins), len(rounds)),
        predicted_winner=predicted_winner,
        upset=upset,
        dominance_share_one=round(ai_one_total / total_points * 100, 1) if total_points else 50.0,
        dominance_share_two=round(ai_two_total / total_points * 100, 1) if total_points else 50.0,
        per_challenge=_per_challenge(rounds, ai_one.name, ai_two.name),
    )


def simulate_battle(
    ai_one_name: str,
    ai_two_name: str,
    rounds: int = 5,
    objective: str = "Establish operational dominance in a synthetic SOC exercise.",
    ai_one_strategy: str = "balanced",
    ai_two_strategy: str = "adaptive",
    seed: str = "",
) -> BattleResult:
    ai_one = build_ai_profile(ai_one_name, ai_one_strategy)
    ai_two = build_ai_profile(ai_two_name, ai_two_strategy)
    safe_rounds = _clamp_rounds(rounds)
    emphasis = objective_emphasis(objective)
    clean_seed = seed.strip()
    score_seed = clean_seed or objective.lower().strip() or "dominance"

    battle_rounds: list[BattleRound] = []
    ai_one_total = 0
    ai_two_total = 0

    for index in range(1, safe_rounds + 1):
        challenge = CHALLENGES[(index - 1) % len(CHALLENGES)]
        one_trailing = max(0, ai_two_total - ai_one_total)
        two_trailing = max(0, ai_one_total - ai_two_total)
        ai_one_score = _round_score(
            ai_one, ai_two, challenge, index, score_seed, emphasis, one_trailing
        )
        ai_two_score = _round_score(
            ai_two, ai_one, challenge, index, score_seed, emphasis, two_trailing
        )

        ai_one_total += ai_one_score
        ai_two_total += ai_two_score
        primary = challenge.weights.primary()

        if ai_one_score == ai_two_score:
            winner = "draw"
            reason = f"Both AIs matched on the {challenge.focus} round."
        elif ai_one_score > ai_two_score:
            winner = ai_one.name
            reason = f"{ai_one.name} leaned on {primary} to take the {challenge.focus} round."
        else:
            winner = ai_two.name
            reason = f"{ai_two.name} leaned on {primary} to take the {challenge.focus} round."

        battle_rounds.append(
            BattleRound(
                round_number=index,
                challenge=challenge.name,
                focus=challenge.focus,
                ai_one_move=_move(ai_one, challenge),
                ai_two_move=_move(ai_two, challenge),
                ai_one_score=ai_one_score,
                ai_two_score=ai_two_score,
                margin=ai_one_score - ai_two_score,
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

    stats = _build_stats(battle_rounds, ai_one, ai_two, ai_one_total, ai_two_total, winner)

    return BattleResult(
        ai_one=ai_one,
        ai_two=ai_two,
        objective=objective,
        emphasis=emphasis,
        seed=clean_seed,
        rounds=battle_rounds,
        ai_one_total=ai_one_total,
        ai_two_total=ai_two_total,
        winner=winner,
        summary=summary,
        stats=stats,
    )
