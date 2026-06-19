from greynoc_dmz.ai_battle import (
    CHALLENGES,
    STRATEGY_MODIFIERS,
    build_ai_profile,
    objective_emphasis,
    simulate_battle,
)


def test_ai_battle_is_deterministic() -> None:
    first = simulate_battle("Sentinel", "Phantom", rounds=3)
    second = simulate_battle("Sentinel", "Phantom", rounds=3)

    assert first.to_dict() == second.to_dict()
    assert len(first.rounds) == 3
    assert first.winner in {"Sentinel", "Phantom", "draw"}


def test_ai_profile_unknown_strategy_falls_back_to_balanced() -> None:
    profile = build_ai_profile("Unknown", "not-real")

    assert profile.strategy == "balanced"
    assert 1 <= profile.aggression <= 100
    assert 1 <= profile.defense <= 100
    assert 1 <= profile.adaptability <= 100


def test_strategy_is_decoupled_from_base_stats() -> None:
    # Same name keeps the same base block; the strategy only reshapes it.
    balanced = build_ai_profile("Atlas", "balanced")
    aggressive = build_ai_profile("Atlas", "aggressive")

    assert aggressive.aggression > balanced.aggression
    assert aggressive.defense < balanced.defense


def test_strategy_modifiers_are_zero_sum() -> None:
    # Strategy is shape, not free power: every modifier nets to zero.
    for modifier in STRATEGY_MODIFIERS.values():
        assert modifier["aggression"] + modifier["defense"] + modifier["adaptability"] == 0


def test_stats_are_internally_consistent() -> None:
    result = simulate_battle("Sentinel", "Phantom", rounds=12)
    stats = result.stats

    assert stats.ai_one_round_wins + stats.ai_two_round_wins + stats.draws == len(result.rounds)
    assert len(stats.lead_timeline) == len(result.rounds)
    assert stats.lead_timeline[-1] == result.ai_one_total - result.ai_two_total
    assert round(stats.dominance_share_one + stats.dominance_share_two) == 100
    assert stats.decisiveness in {"blowout", "clear", "narrow", "coin-flip"}
    assert len(stats.per_challenge) == min(len(result.rounds), len(CHALLENGES))


def test_round_margin_matches_scores() -> None:
    result = simulate_battle("Sentinel", "Phantom", rounds=5)
    for battle_round in result.rounds:
        assert battle_round.margin == battle_round.ai_one_score - battle_round.ai_two_score


def test_shared_name_does_not_double_count_round_wins() -> None:
    # Fighters with the same name must still produce a coherent tally.
    result = simulate_battle("AI", "AI", rounds=9, ai_one_strategy="aggressive")
    stats = result.stats
    total = stats.ai_one_round_wins + stats.ai_two_round_wins + stats.draws
    assert total == len(result.rounds)


def test_identical_fighters_draw_every_round() -> None:
    result = simulate_battle("Mirror", "Mirror", rounds=8, ai_two_strategy="balanced")
    assert result.winner == "draw"
    assert result.stats.draws == len(result.rounds)


def test_objective_emphasis_reads_keywords() -> None:
    assert objective_emphasis("Preserve the evidence chain") == "defense"
    assert objective_emphasis("Establish operational dominance") == "aggression"
    assert objective_emphasis("Adapt to a constant change") == "adaptability"


def test_objective_sets_the_emphasis_field() -> None:
    defended = simulate_battle("A", "B", rounds=4, objective="Protect evidence integrity")
    assert defended.emphasis == "defense"


def test_seed_varies_outcome_but_stays_deterministic() -> None:
    first = simulate_battle("Sentinel", "Phantom", rounds=10, seed="alpha")
    again = simulate_battle("Sentinel", "Phantom", rounds=10, seed="alpha")
    other = simulate_battle("Sentinel", "Phantom", rounds=10, seed="bravo")

    assert first.to_dict() == again.to_dict()
    assert [r.ai_one_score for r in first.rounds] != [r.ai_one_score for r in other.rounds]


def test_round_focus_follows_challenge_rotation() -> None:
    result = simulate_battle("A", "B", rounds=len(CHALLENGES))
    assert [r.focus for r in result.rounds] == [c.focus for c in CHALLENGES]


def test_move_text_varies_by_challenge() -> None:
    result = simulate_battle("Sentinel", "Phantom", rounds=len(CHALLENGES))
    assert len({r.ai_one_move for r in result.rounds}) > 1
