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
    check_ai_readiness,
    load_ai_config,
    run_live_check,
    run_scenario_review,
)
from .ai_battle import simulate_battle
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
