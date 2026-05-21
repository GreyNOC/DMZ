from __future__ import annotations

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
from .dashboard import serve
from .engine import run_scenario, validate_all
from .integrations import (
    PublishOutcome,
    check_integration_config,
    load_integrations,
    publish_all,
)
from .reporting import write_report
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
    result = run_scenario(
        scenario,
        root / "detections" / "rules",
        root / "evidence" if write_evidence else None,
        root / ".dmz",
    )
    if write_markdown_report:
        report_path = write_report(result, root / "reports")
        console.print(f"report: {report_path}")
    console.print(f"{result.scenario_id}: {'PASS' if result.passed else 'FAIL'}")
    if not result.passed:
        raise typer.Exit(code=1)


@app.command("validate-all")
def validate_all_cmd() -> None:
    results = validate_all(_root())
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
        write_report(result, _root() / "reports")
    console.print(table)
    if failed:
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
        table.add_row(
            check.name, check.kind.value, check.adapter, check.status.value, check.detail
        )
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
