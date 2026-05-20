from __future__ import annotations

from pathlib import Path
from typing import Annotated

import typer
from rich.console import Console
from rich.table import Table

from .dashboard import serve
from .engine import run_scenario, validate_all
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
