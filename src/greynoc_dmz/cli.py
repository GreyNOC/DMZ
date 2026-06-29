from __future__ import annotations

import os
import socket
import webbrowser
from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .ai import (
    AIProviderError,
    AIReadinessStatus,
    Fighter,
    check_ai_readiness,
    check_fighter_readiness,
    load_ai_config,
    load_roster,
    run_live_check,
    run_scenario_review,
)
from .ai.roster import ROSTER_RELATIVE_PATH
from .ai_battle import simulate_battle
from .arena import (
    ArenaError,
    parse_teams,
    resolve_judge,
    select_fighters,
    to_combatant,
    to_team,
    unready_fighters,
)
from .config import load_lab_config
from .coverage import coverage_for_root
from .dashboard import serve
from .dataset import DatasetFormat, build_dataset, run_lab, write_dataset
from .engine import run_scenario, validate_all
from .integrations import (
    PublishOutcome,
    check_integration_config,
    load_integrations,
    publish_all,
)
from .lint import has_errors, lint_repo
from .live_battle import (
    DEFAULT_COLLAB_OBJECTIVE,
    DEFAULT_LIVE_OBJECTIVE,
    run_collaborative_battle,
    run_live_battle,
)
from .reporting import write_report
from .ruletest import has_failures, run_rule_tests
from .runtime import resolve_lab_root
from .security import scan_repo

app = typer.Typer(help="GreyNOC DMZ detection validation CLI")
console = Console()


def _root() -> Path:
    return resolve_lab_root(Path.cwd())


def _available_port(host: str, start: int, attempts: int = 20) -> int:
    for port in range(start, start + attempts):
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            if sock.connect_ex((host, port)) != 0:
                return port
    raise RuntimeError(f"no available port found from {start} to {start + attempts - 1}")


def launch_desktop(host: str = "127.0.0.1", port: int = 8787) -> None:
    root = _root()
    selected_port = _available_port(host, port)
    url = f"http://{host}:{selected_port}"
    console.print("GreyNOC DMZ desktop launcher")
    console.print(f"Lab root: {root}")
    console.print(f"Dashboard: {url}")
    console.print("Close this window to stop the dashboard.")
    if os.environ.get("GREYNOC_DMZ_NO_BROWSER") != "1":
        webbrowser.open(url)
    serve(root, host, selected_port)


@app.command("run-scenario")
def run_scenario_cmd(
    scenario: Annotated[Path, typer.Option("--scenario", exists=True, readable=True)],
    write_evidence: Annotated[bool, typer.Option("--evidence/--no-evidence")] = True,
    write_markdown_report: Annotated[bool, typer.Option("--report/--no-report")] = True,
) -> None:
    root = _root()
    config = load_lab_config(root)
    result = run_scenario(
        scenario,
        root / "detections" / "rules",
        root / config.evidence_dir if write_evidence else None,
        root / ".dmz",
        telemetry_root=root,
    )
    if write_markdown_report:
        report_path = write_report(result, root / config.report_dir)
        console.print(f"report: {report_path}")
    console.print(f"{result.scenario_id}: {'PASS' if result.passed else 'FAIL'}")
    if not result.passed:
        raise typer.Exit(code=1)


@app.command("validate-all")
def validate_all_cmd() -> None:
    root = _root()
    config = load_lab_config(root)
    results = validate_all(root)
    table = Table(title="GreyNOC DMZ Validation")
    table.add_column("Scenario")
    table.add_column("Status")
    table.add_column("Fired")
    table.add_column("Missing")
    failed = False
    for result in results:
        failed = failed or not result.passed
        table.add_row(
            result.scenario_id,
            "PASS" if result.passed else "FAIL",
            ", ".join(result.fired_rules) or "none",
            ", ".join(result.missing_rules) or "none",
        )
        write_report(result, root / config.report_dir)
    console.print(table)
    if failed:
        raise typer.Exit(code=1)


@app.command("ai-battle")
def ai_battle_cmd(
    ai_one: Annotated[str, typer.Option("--ai-one")] = "Sentinel",
    ai_two: Annotated[str, typer.Option("--ai-two")] = "Phantom",
    rounds: Annotated[int, typer.Option("--rounds", min=1, max=25)] = 5,
    objective: Annotated[str, typer.Option("--objective")] = "Establish operational dominance in a synthetic SOC exercise.",
    ai_one_strategy: Annotated[str, typer.Option("--ai-one-strategy")] = "balanced",
    ai_two_strategy: Annotated[str, typer.Option("--ai-two-strategy")] = "adaptive",
    seed: Annotated[str, typer.Option("--seed", help="Optional rematch seed for a varied outcome.")] = "",
) -> None:
    result = simulate_battle(
        ai_one, ai_two, rounds, objective, ai_one_strategy, ai_two_strategy, seed
    )
    stats = result.stats
    one = result.ai_one
    two = result.ai_two

    fighters = Table(title="Fighters")
    fighters.add_column("AI")
    fighters.add_column("Strategy")
    fighters.add_column("Agg", justify="right")
    fighters.add_column("Def", justify="right")
    fighters.add_column("Adapt", justify="right")
    fighters.add_column("Power", justify="right")
    for profile in (one, two):
        fighters.add_row(
            profile.name,
            profile.strategy,
            str(profile.aggression),
            str(profile.defense),
            str(profile.adaptability),
            str(profile.power),
        )
    console.print(fighters)

    table = Table(title="GreyNOC DMZ AI Battle")
    table.add_column("Round")
    table.add_column("Challenge focus")
    table.add_column(one.name, justify="right")
    table.add_column(two.name, justify="right")
    table.add_column("Margin", justify="right")
    table.add_column("Winner")
    for battle_round in result.rounds:
        table.add_row(
            str(battle_round.round_number),
            battle_round.focus,
            str(battle_round.ai_one_score),
            str(battle_round.ai_two_score),
            f"{battle_round.margin:+d}",
            battle_round.winner,
        )
    console.print(table)

    stats_table = Table(title="Battle stats")
    stats_table.add_column("Metric")
    stats_table.add_column(one.name, justify="right")
    stats_table.add_column(two.name, justify="right")
    stats_table.add_row("Total score", str(result.ai_one_total), str(result.ai_two_total))
    stats_table.add_row("Round wins", str(stats.ai_one_round_wins), str(stats.ai_two_round_wins))
    stats_table.add_row("Avg / round", str(stats.ai_one_avg), str(stats.ai_two_avg))
    stats_table.add_row(
        "Consistency (lower=steadier)",
        str(stats.ai_one_consistency),
        str(stats.ai_two_consistency),
    )
    stats_table.add_row("Best round", str(stats.ai_one_best_round), str(stats.ai_two_best_round))
    stats_table.add_row(
        "Longest streak", str(stats.ai_one_longest_streak), str(stats.ai_two_longest_streak)
    )
    stats_table.add_row(
        "Dominance share %", str(stats.dominance_share_one), str(stats.dominance_share_two)
    )
    console.print(stats_table)

    console.print(
        f"draws: {stats.draws}  |  lead changes: {stats.lead_changes}  |  "
        f"decisiveness: {stats.decisiveness}"
    )
    console.print(
        f"largest margin: {stats.largest_margin}  |  closest margin: {stats.closest_margin}  |  "
        f"objective rewards: {result.emphasis}"
    )
    predicted = f"predicted by power: {stats.predicted_winner}"
    console.print(predicted + ("  [UPSET]" if stats.upset else ""))
    if stats.comeback_winner:
        console.print(f"comeback: {stats.comeback_winner} won after trailing")
    console.print(f"winner: {result.winner}")
    console.print(result.summary)


@app.command("coverage")
def coverage_cmd() -> None:
    report = coverage_for_root(_root())
    covered, total = report.tactic_coverage_ratio

    table = Table(title=f"GreyNOC DMZ MITRE ATT&CK Coverage ({covered}/{total} tactics)")
    table.add_column("Tactic")
    table.add_column("Name")
    table.add_column("Status")
    table.add_column("Rules")
    for tactic in report.tactics:
        table.add_row(
            tactic.tactic_id,
            tactic.name,
            "covered" if tactic.covered else "gap",
            ", ".join(tactic.rule_ids) or "none",
        )
    console.print(table)
    console.print(f"techniques mapped: {', '.join(report.techniques) or 'none'}")
    if report.unmapped_rules:
        console.print(f"rules without MITRE mapping: {', '.join(report.unmapped_rules)}")


@app.command("lint")
def lint_cmd() -> None:
    findings = lint_repo(_root())
    if not findings:
        console.print("lint: PASS")
        return

    table = Table(title="GreyNOC DMZ Rule Lint")
    table.add_column("Target")
    table.add_column("Level")
    table.add_column("Message")
    for finding in findings:
        table.add_row(finding.target, finding.level, finding.message)
    console.print(table)
    if has_errors(findings):
        raise typer.Exit(code=1)


@app.command("test-rules")
def test_rules_cmd() -> None:
    results = run_rule_tests(_root())
    if not results:
        console.print("test-rules: no rule tests found")
        return

    table = Table(title="GreyNOC DMZ Rule Tests")
    table.add_column("Rule")
    table.add_column("Status")
    table.add_column("Detail")
    for result in results:
        table.add_row(result.rule_id, "PASS" if result.passed else "FAIL", result.detail)
    console.print(table)
    if has_failures(results):
        raise typer.Exit(code=1)


@app.command("integration-check")
def integration_check_cmd() -> None:
    table = Table(title="GreyNOC DMZ Integrations")
    table.add_column("Name")
    table.add_column("Kind")
    table.add_column("Adapter")
    table.add_column("Status")
    table.add_column("Detail")
    for config in load_integrations(_root()):
        check = check_integration_config(config)
        table.add_row(check.name, check.kind.value, check.adapter, check.status.value, check.detail)
    console.print(table)


@app.command("integration-publish")
def integration_publish_cmd(
    send: Annotated[
        bool,
        typer.Option("--send/--dry-run", help="Transmit to integrations instead of a dry run"),
    ] = False,
) -> None:
    root = _root()
    results = validate_all(root)
    outcomes = publish_all(results, load_integrations(root), dry_run=not send, root=root)
    if not outcomes:
        console.print(
            "integration-publish: no ready integrations; run integration-check for details"
        )
        return

    table = Table(title=f"GreyNOC DMZ Publish ({'send' if send else 'dry-run'})")
    table.add_column("Integration")
    table.add_column("Adapter")
    table.add_column("Scenario")
    table.add_column("Outcome")
    table.add_column("Detail")
    problems = 0
    for outcome in outcomes:
        if outcome.outcome in {PublishOutcome.error, PublishOutcome.blocked}:
            problems += 1
        table.add_row(
            outcome.integration,
            outcome.adapter,
            outcome.scenario_id,
            outcome.outcome.value,
            outcome.detail,
        )
    console.print(table)
    if problems:
        raise typer.Exit(code=1)


@app.command("ai-check")
def ai_check_cmd(
    live: Annotated[
        bool,
        typer.Option("--live", help="Make a live provider call to confirm connectivity"),
    ] = False,
) -> None:
    config = load_ai_config()
    readiness = check_ai_readiness(config)
    table = Table(title="GreyNOC DMZ AI Provider")
    table.add_column("Field")
    table.add_column("Value")
    table.add_row("Status", readiness.status.value)
    table.add_row("Provider", readiness.provider)
    table.add_row("Model", readiness.model or "not set")
    table.add_row("External", "yes" if readiness.external else "no")
    table.add_row("Detail", readiness.detail)
    console.print(table)
    if not live:
        return
    if readiness.status is not AIReadinessStatus.ready:
        console.print("ai-check --live: provider is not ready")
        raise typer.Exit(code=1)
    try:
        response = run_live_check(config)
    except AIProviderError as error:
        console.print(f"ai-check --live: failed: {error}")
        raise typer.Exit(code=1) from error
    console.print(f"ai-check --live: ok ({response.provider} / {response.model})")


@app.command("ai-review")
def ai_review_cmd() -> None:
    config = load_ai_config()
    readiness = check_ai_readiness(config)
    if readiness.status is not AIReadinessStatus.ready:
        console.print(f"ai-review: AI provider is not ready ({readiness.detail})")
        raise typer.Exit(code=1)
    results = validate_all(_root())
    try:
        review = run_scenario_review(config, results)
    except AIProviderError as error:
        console.print(f"ai-review: failed: {error}")
        raise typer.Exit(code=1) from error
    console.print("AI-assisted advisory review", style="bold")
    console.print(review.text, markup=False)


def _roster_path(roster: Path | None) -> Path:
    return roster if roster is not None else _root() / ROSTER_RELATIVE_PATH


def _load_roster_or_exit(roster: Path | None) -> tuple[Path, list[Fighter]]:
    path = _roster_path(roster)
    fighters = load_roster(path)
    if not fighters:
        console.print(f"no fighters found in roster: {path}")
        console.print("Add fighters to configs/ai-roster.json (see README: AI battle arena).")
        raise typer.Exit(code=1)
    return path, fighters


def _select_fighters(roster: list[Fighter], names_csv: str) -> list[Fighter]:
    if not names_csv.strip():
        return roster[:2]
    try:
        return select_fighters(roster, names_csv.split(","))
    except ArenaError as error:
        raise typer.BadParameter(str(error)) from error


def _resolve_judge(roster: list[Fighter], combatants: list[Fighter], judge_name: str) -> Fighter:
    try:
        return resolve_judge(roster, combatants, judge_name)
    except ArenaError as error:
        raise typer.BadParameter(str(error)) from error


def _require_ready(fighters: list[Fighter], allow_external: bool) -> None:
    not_ready = unready_fighters(fighters, allow_external)
    if not_ready:
        for name, detail in not_ready:
            console.print(f"not ready: {name} - {detail}")
        if not allow_external:
            console.print("Hosted providers are external; re-run with --allow-external to permit them.")
        raise typer.Exit(code=1)


def _truncate(text: str, limit: int = 240) -> str:
    clean = " ".join(text.split())
    return clean if len(clean) <= limit else clean[: limit - 1] + "…"


@app.command("ai-roster")
def ai_roster_cmd(
    roster: Annotated[Path | None, typer.Option("--roster", help="Roster JSON path")] = None,
    allow_external: Annotated[
        bool, typer.Option("--allow-external", help="Treat external endpoints as permitted")
    ] = False,
) -> None:
    path = _roster_path(roster)
    fighters = load_roster(path)
    if not fighters:
        console.print(f"ai-roster: no fighters found in {path}")
        return
    table = Table(title=f"GreyNOC DMZ AI Roster ({len(fighters)} fighters)")
    table.add_column("Name")
    table.add_column("Provider")
    table.add_column("Model")
    table.add_column("Endpoint")
    table.add_column("Status")
    table.add_column("Detail")
    for fighter in fighters:
        readiness = check_fighter_readiness(fighter, allow_external)
        table.add_row(
            fighter.name,
            fighter.provider,
            fighter.model or "not set",
            "external" if readiness.external else "local",
            readiness.status.value,
            readiness.detail,
        )
    console.print(table)


@app.command("live-battle")
def live_battle_cmd(
    fighters: Annotated[
        str, typer.Option("--fighters", help="Comma-separated fighter names (default: first two)")
    ] = "",
    judge: Annotated[str, typer.Option("--judge", help="Fighter name to score the battle")] = "",
    rounds: Annotated[int, typer.Option("--rounds", min=1, max=24)] = 5,
    objective: Annotated[str, typer.Option("--objective")] = DEFAULT_LIVE_OBJECTIVE,
    roster: Annotated[Path | None, typer.Option("--roster", help="Roster JSON path")] = None,
    allow_external: Annotated[
        bool, typer.Option("--allow-external", help="Permit external AI endpoints")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit the result as JSON")] = False,
) -> None:
    _, all_fighters = _load_roster_or_exit(roster)
    selected = _select_fighters(all_fighters, fighters)
    if len(selected) < 2:
        console.print("live-battle: need at least two fighters (use --fighters A,B)")
        raise typer.Exit(code=1)
    judge_fighter = _resolve_judge(all_fighters, selected, judge)
    _require_ready([*selected, judge_fighter], allow_external)

    combatants = [to_combatant(fighter, allow_external) for fighter in selected]
    judge_combatant = to_combatant(judge_fighter, allow_external)
    result = run_live_battle(combatants, judge_combatant, objective, rounds)

    if as_json:
        console.print_json(data=result.to_dict())
        return

    console.print(f"Judge: {result.judge}  |  Objective: {result.objective}", style="bold")
    for battle_round in result.rounds:
        console.print(f"\nRound {battle_round.round_number} - {battle_round.focus}", style="bold")
        for response in battle_round.responses:
            score = battle_round.scores.get(response.fighter, 0)
            body = f"({response.error})" if response.error else _truncate(response.text)
            console.print(f"  {response.fighter} [{score}]: {body}", markup=False)
        console.print(f"  winner: {battle_round.winner} - {battle_round.rationale}", markup=False)

    table = Table(title="Live battle scoreboard")
    table.add_column("Fighter")
    table.add_column("Total", justify="right")
    for name, total in sorted(result.totals.items(), key=lambda item: item[1], reverse=True):
        table.add_row(name, str(total))
    console.print(table)
    console.print(f"winner: {result.winner}")
    console.print(result.summary)


@app.command("collab-battle")
def collab_battle_cmd(
    teams: Annotated[
        str,
        typer.Option(
            "--teams",
            help='Teams spec, e.g. "Red=Claude,GPT;Blue=Gemini". One team is allowed.',
        ),
    ],
    judge: Annotated[str, typer.Option("--judge", help="Fighter name to score the teams")] = "",
    rounds: Annotated[int, typer.Option("--rounds", min=1, max=24)] = 3,
    objective: Annotated[str, typer.Option("--objective")] = DEFAULT_COLLAB_OBJECTIVE,
    roster: Annotated[Path | None, typer.Option("--roster", help="Roster JSON path")] = None,
    allow_external: Annotated[
        bool, typer.Option("--allow-external", help="Permit external AI endpoints")
    ] = False,
    as_json: Annotated[bool, typer.Option("--json", help="Emit the result as JSON")] = False,
) -> None:
    _, all_fighters = _load_roster_or_exit(roster)
    parsed_teams = _parse_teams(teams, all_fighters)
    members = [fighter for _name, roster_members in parsed_teams for fighter in roster_members]
    judge_fighter = _resolve_judge(all_fighters, members, judge)
    _require_ready([*members, judge_fighter], allow_external)

    battle_teams = [
        to_team(name, roster_members, allow_external) for name, roster_members in parsed_teams
    ]
    judge_combatant = to_combatant(judge_fighter, allow_external)
    result = run_collaborative_battle(battle_teams, judge_combatant, objective, rounds)

    if as_json:
        console.print_json(data=result.to_dict())
        return

    console.print(f"Judge: {result.judge}  |  Objective: {result.objective}", style="bold")
    for name, member_names in result.teams.items():
        console.print(f"Team {name}: {', '.join(member_names)}")
    for battle_round in result.rounds:
        console.print(f"\nRound {battle_round.round_number} - {battle_round.focus}", style="bold")
        for team_name, answer in battle_round.team_answers.items():
            score = battle_round.scores.get(team_name, 0)
            console.print(f"  {team_name} [{score}]: {_truncate(answer)}", markup=False)
        console.print(f"  winner: {battle_round.winner} - {battle_round.rationale}", markup=False)

    table = Table(title="Collaborative battle scoreboard")
    table.add_column("Team")
    table.add_column("Total", justify="right")
    for name, total in sorted(result.totals.items(), key=lambda item: item[1], reverse=True):
        table.add_row(name, str(total))
    console.print(table)
    console.print(f"winner: {result.winner}")
    console.print(result.summary)


def _parse_teams(spec: str, roster: list[Fighter]) -> list[tuple[str, list[Fighter]]]:
    try:
        return parse_teams(spec, roster)
    except ArenaError as error:
        raise typer.BadParameter(str(error)) from error


@app.command("export-dataset")
def export_dataset_cmd(
    output_format: Annotated[
        DatasetFormat, typer.Option("--format", help="Dataset format: raw or chat")
    ] = DatasetFormat.raw,
    out: Annotated[Path, typer.Option("--out", help="Output JSONL path")] = Path(
        "datasets/dmz-dataset.jsonl"
    ),
    with_ai: Annotated[
        bool, typer.Option("--with-ai", help="Add a per-scenario AI analysis note")
    ] = False,
) -> None:
    root = _root()
    runs = run_lab(root)
    ai_notes: dict[str, str] | None = None
    if with_ai:
        config = load_ai_config()
        readiness = check_ai_readiness(config)
        if readiness.status is not AIReadinessStatus.ready:
            console.print(
                f"export-dataset: --with-ai needs a ready AI provider ({readiness.detail})"
            )
            raise typer.Exit(code=1)
        ai_notes = {}
        for run in runs:
            try:
                ai_notes[run.scenario.id] = run_scenario_review(config, [run.result]).text
            except AIProviderError as error:
                console.print(f"export-dataset: AI note skipped for {run.scenario.id}: {error}")
    records = build_dataset(runs, output_format, ai_notes=ai_notes)
    out_path = out if out.is_absolute() else root / out
    write_dataset(records, out_path)
    console.print(
        f"export-dataset: wrote {len(records)} {output_format.value} record(s) to {out_path}"
    )


@app.command("security-check")
def security_check_cmd() -> None:
    findings = scan_repo(_root())
    if not findings:
        console.print("security-check: PASS")
        return

    table = Table(title="GreyNOC DMZ Security Findings")
    table.add_column("File")
    table.add_column("Line")
    table.add_column("Reason")
    for finding in findings:
        table.add_row(finding.path, str(finding.line), finding.reason)
    console.print(table)
    raise typer.Exit(code=1)


@app.command("dashboard")
def dashboard_cmd(
    host: Annotated[str, typer.Option("--host")] = "127.0.0.1",
    port: Annotated[int, typer.Option("--port")] = 8787,
) -> None:
    console.print(f"GreyNOC DMZ dashboard: http://{host}:{port}")
    serve(_root(), host, port)
