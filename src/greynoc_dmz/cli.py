from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .ai_battle import simulate_battle
from .config import load_lab_config
from .coverage import coverage_for_root
from .dashboard import serve
from .engine import run_scenario, validate_all
from .integrations import check_integration_config, default_integrations
from .lint import has_errors, lint_repo
from .reporting import write_report
from .ruletest import has_failures, run_rule_tests
from .security import scan_repo

app = typer.Typer(help="GreyNOC DMZ detection validation CLI")
console = Console()


def _root() -> Path:
    return Path.cwd()


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
) -> None:
    result = simulate_battle(ai_one, ai_two, rounds, objective, ai_one_strategy, ai_two_strategy)

    table = Table(title="GreyNOC DMZ AI Battle")
    table.add_column("Round")
    table.add_column("Challenge")
    table.add_column(result.ai_one.name)
    table.add_column(result.ai_two.name)
    table.add_column("Winner")

    for battle_round in result.rounds:
        table.add_row(
            str(battle_round.round_number),
            battle_round.challenge,
            str(battle_round.ai_one_score),
            str(battle_round.ai_two_score),
            battle_round.winner,
        )

    console.print(table)
    console.print(f"{result.ai_one.name}: {result.ai_one_total}")
    console.print(f"{result.ai_two.name}: {result.ai_two_total}")
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
    table.add_column("Status")
    table.add_column("Detail")
    for config in default_integrations():
        check = check_integration_config(config)
        table.add_row(check.name, check.kind.value, check.status.value, check.detail)
    console.print(table)


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
