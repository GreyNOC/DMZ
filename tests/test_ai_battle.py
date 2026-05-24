from greynoc_dmz.ai_battle import build_ai_profile, simulate_battle


def test_ai_battle_is_deterministic() -> None:
    first = simulate_battle("Sentinel", "Phantom", rounds=3)
    second = simulate_battle("Sentinel", "Phantom", rounds=3)

    assert first.model_dump() == second.model_dump()
    assert len(first.rounds) == 3
    assert first.winner in {"Sentinel", "Phantom", "draw"}


def test_ai_profile_unknown_strategy_falls_back_to_balanced() -> None:
    profile = build_ai_profile("Unknown", "not-real")

    assert profile.strategy == "balanced"
    assert 1 <= profile.aggression <= 100
    assert 1 <= profile.defense <= 100
    assert 1 <= profile.adaptability <= 100
