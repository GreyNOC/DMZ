import json
from typing import Any

import pytest

from greynoc_dmz.ai.models import AIProviderError, AIResponse
from greynoc_dmz.live_battle import (
    Combatant,
    Team,
    run_collaborative_battle,
    run_live_battle,
)


class StubProvider:
    """Returns fixed text, ignoring the prompt."""

    def __init__(self, text: str) -> None:
        self._text = text

    def complete(self, prompt: str, system: str | None = None) -> AIResponse:
        return AIResponse(provider="stub", model="stub", text=self._text)


class ErrorProvider:
    def complete(self, prompt: str, system: str | None = None) -> AIResponse:
        raise AIProviderError("boom")


class DraftAwareProvider:
    """Reveals whether the prompt already carries a team draft."""

    def complete(self, prompt: str, system: str | None = None) -> AIResponse:
        text = "HAS_DRAFT" if "Current team draft" in prompt else "NO_DRAFT"
        return AIResponse(provider="stub", model="stub", text=text)


class FixedJudge:
    """A judge that always returns the same scoring JSON."""

    def __init__(self, payload: dict[str, Any]) -> None:
        self._payload = payload

    def complete(self, prompt: str, system: str | None = None) -> AIResponse:
        return AIResponse(provider="judge", model="judge", text=json.dumps(self._payload))


class RawJudge:
    def __init__(self, text: str) -> None:
        self._text = text

    def complete(self, prompt: str, system: str | None = None) -> AIResponse:
        return AIResponse(provider="judge", model="judge", text=self._text)


def _judge(payload: dict[str, Any]) -> Combatant:
    return Combatant("Judge", FixedJudge(payload))


def test_live_battle_aggregates_judge_scores() -> None:
    combatants = [Combatant("Alpha", StubProvider("a")), Combatant("Beta", StubProvider("b"))]
    judge = _judge({"scores": {"Alpha": 8, "Beta": 5}, "winner": "Alpha", "rationale": "alpha led"})

    result = run_live_battle(combatants, judge, rounds=3)

    assert result.winner == "Alpha"
    assert result.totals == {"Alpha": 24, "Beta": 15}
    assert len(result.rounds) == 3
    assert result.rounds[0].scores == {"Alpha": 8, "Beta": 5}
    assert result.rounds[0].rationale == "alpha led"
    assert result.summary.startswith("Alpha won")
    assert result.to_dict()["mode"] == "live"


def test_errored_fighter_is_forced_to_zero() -> None:
    combatants = [Combatant("Alpha", StubProvider("a")), Combatant("Beta", ErrorProvider())]
    # The judge tries to award Beta 9, but Beta produced no response.
    judge = _judge({"scores": {"Alpha": 7, "Beta": 9}, "winner": "Beta"})

    result = run_live_battle(combatants, judge, rounds=1)

    assert result.rounds[0].scores["Beta"] == 0
    assert result.rounds[0].responses[1].error
    assert result.winner == "Alpha"


def test_unparseable_judge_falls_back_to_neutral_scores() -> None:
    combatants = [Combatant("Alpha", StubProvider("a")), Combatant("Beta", StubProvider("b"))]
    judge = Combatant("Judge", RawJudge("the answers were both fine"))

    result = run_live_battle(combatants, judge, rounds=1)

    assert result.rounds[0].scores == {"Alpha": 5, "Beta": 5}
    assert result.rounds[0].winner == "draw"
    assert "could not be parsed" in result.rounds[0].rationale


def test_unavailable_judge_falls_back() -> None:
    combatants = [Combatant("Alpha", StubProvider("a")), Combatant("Beta", ErrorProvider())]
    judge = Combatant("Judge", ErrorProvider())

    result = run_live_battle(combatants, judge, rounds=1)

    # Alpha responded (neutral 5), Beta errored (0): Alpha wins despite no judge.
    assert result.rounds[0].scores == {"Alpha": 5, "Beta": 0}
    assert result.winner == "Alpha"
    assert "judge unavailable" in result.rounds[0].rationale


def test_live_draw_reports_draw_summary() -> None:
    combatants = [Combatant("Alpha", StubProvider("a")), Combatant("Beta", StubProvider("b"))]
    judge = _judge({"scores": {"Alpha": 5, "Beta": 5}, "winner": "draw"})

    result = run_live_battle(combatants, judge, rounds=1)

    assert result.winner == "draw"
    assert "draw" in result.summary
    assert "No AI" in result.summary


def test_malformed_judge_score_does_not_crash() -> None:
    # A judge that emits a non-numeric/garbage score (e.g. "--5") must fall back,
    # not raise out of the battle.
    combatants = [Combatant("Alpha", StubProvider("a")), Combatant("Beta", StubProvider("b"))]
    judge = _judge({"scores": {"Alpha": "--5", "Beta": 7}, "winner": "Beta"})

    result = run_live_battle(combatants, judge, rounds=1)

    assert result.rounds[0].scores == {"Alpha": 5, "Beta": 7}
    assert result.winner == "Beta"


def test_judge_json_recovered_from_surrounding_prose() -> None:
    combatants = [Combatant("Alpha", StubProvider("a")), Combatant("Beta", StubProvider("b"))]
    judge = Combatant(
        "Judge",
        RawJudge('I think {A} did great. {"scores": {"Alpha": 8, "Beta": 3}, "winner": "Alpha"}'),
    )

    result = run_live_battle(combatants, judge, rounds=1)

    assert result.rounds[0].scores == {"Alpha": 8, "Beta": 3}
    assert result.rounds[0].winner == "Alpha"
    assert "could not be parsed" not in result.rounds[0].rationale


def test_live_battle_requires_two_combatants() -> None:
    with pytest.raises(ValueError):
        run_live_battle([Combatant("Solo", StubProvider("x"))], _judge({}), rounds=1)


def test_live_battle_rejects_duplicate_combatant_names() -> None:
    with pytest.raises(ValueError):
        run_live_battle(
            [Combatant("A", StubProvider("x")), Combatant("A", StubProvider("y"))],
            _judge({}),
            rounds=1,
        )


def test_collaborative_battle_scores_teams() -> None:
    red = Team("Red", [Combatant("A1", StubProvider("draftA")), Combatant("A2", StubProvider("refinedA"))])
    blue = Team("Blue", [Combatant("B1", StubProvider("draftB"))])
    judge = _judge({"scores": {"Red": 9, "Blue": 4}, "winner": "Red", "rationale": "red led"})

    result = run_collaborative_battle([red, blue], judge, rounds=2)

    assert result.winner == "Red"
    assert result.totals == {"Red": 18, "Blue": 8}
    assert result.rounds[0].team_answers == {"Red": "refinedA", "Blue": "draftB"}
    red_contributions = [c for c in result.rounds[0].contributions if c.team == "Red"]
    assert [c.member for c in red_contributions] == ["A1", "A2"]
    assert result.summary.startswith("Red won")
    assert result.to_dict()["teams"]["Red"] == ["A1", "A2"]


def test_collaborative_member_error_preserves_prior_draft() -> None:
    # A teammate erroring after a good draft must not wipe the team's answer.
    team = Team("Duo", [Combatant("A", StubProvider("good")), Combatant("B", ErrorProvider())])
    judge = _judge({"scores": {"Duo": 6}, "winner": "Duo"})

    result = run_collaborative_battle([team], judge, rounds=1)

    assert result.rounds[0].team_answers["Duo"] == "good"
    contributions = result.rounds[0].contributions
    assert contributions[1].member == "B"
    assert contributions[1].error
    # Scored from the surviving non-empty answer (judge's 6), not forced to 0.
    assert result.rounds[0].scores["Duo"] == 6


def test_collaborative_within_round_members_build_on_each_other() -> None:
    duo = Team("Duo", [Combatant("A", StubProvider("first")), Combatant("B", DraftAwareProvider())])
    judge = _judge({"scores": {"Duo": 5}})

    result = run_collaborative_battle([duo], judge, rounds=1)

    # B saw A's draft, so it returned HAS_DRAFT — and that becomes the team answer.
    assert result.rounds[0].team_answers["Duo"] == "HAS_DRAFT"
    contributions = result.rounds[0].contributions
    assert contributions[0].text == "first"
    assert contributions[1].text == "HAS_DRAFT"


def test_collaborative_carries_draft_across_rounds() -> None:
    solo = Team("Solo", [Combatant("A", DraftAwareProvider())])
    judge = _judge({"scores": {"Solo": 5}})

    result = run_collaborative_battle([solo], judge, rounds=2)

    assert result.rounds[0].team_answers["Solo"] == "NO_DRAFT"
    assert result.rounds[1].team_answers["Solo"] == "HAS_DRAFT"


def test_collaborative_team_with_no_output_scores_zero() -> None:
    solo = Team("Solo", [Combatant("A", ErrorProvider())])
    judge = _judge({"scores": {"Solo": 9}, "winner": "Solo"})

    result = run_collaborative_battle([solo], judge, rounds=1)

    assert result.rounds[0].scores["Solo"] == 0
    assert result.winner == "draw"
    assert "draw" in result.summary
    assert "team" in result.summary


def test_collaborative_battle_requires_a_team() -> None:
    with pytest.raises(ValueError):
        run_collaborative_battle([], _judge({}), rounds=1)


def test_collaborative_rejects_empty_team() -> None:
    with pytest.raises(ValueError):
        run_collaborative_battle([Team("Empty", [])], _judge({}), rounds=1)


def test_collaborative_rejects_duplicate_team_names() -> None:
    with pytest.raises(ValueError):
        run_collaborative_battle(
            [Team("Red", [Combatant("A", StubProvider("a"))]),
             Team("Red", [Combatant("B", StubProvider("b"))])],
            _judge({}),
            rounds=1,
        )
