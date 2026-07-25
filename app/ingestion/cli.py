from __future__ import annotations

import json
import logging
import time
from pathlib import Path

import typer
from rich.console import Console
from rich.table import Table

from .config import EXTENSION_DESCRIPTION, IngestionConfig, SUPPORTED_EXTENSIONS
from .parsers import list_available
from .pipeline import IngestionPipeline

ingest_app = typer.Typer(help="Ingest files into the knowledge base")
console = Console()
logger = logging.getLogger(__name__)


def _shorten(path: str, max_len: int = 60) -> str:
    return path if len(path) <= max_len else "..." + path[-(max_len - 3):]


# ---------------------------------------------------------------------------
# rag ingest init
# ---------------------------------------------------------------------------

@ingest_app.command()
def init(
    source_dir: str = typer.Argument(..., help="Directory containing files to ingest"),
    config: str = typer.Option("ingestion-config.yaml", "--config", "-c", help="Output config path"),
    recursive: bool = typer.Option(True, "--recursive/--no-recursive", help="Scan subdirectories"),
):
    """Generate a scaffold ingestion-config.yaml for the given source directory."""
    cfg = IngestionConfig(source_dir=source_dir, recursive=recursive)
    cfg.to_yaml(config)
    console.print("[green]Config written to {}[/green]".format(config))
    console.print()
    console.print("[bold]Supported file types:[/bold]")
    for ext, desc in sorted(EXTENSION_DESCRIPTION.items()):
        console.print("  {:<8} {}".format(ext, desc))
    console.print()
    console.print("[yellow]Edit the config file before running: rag ingest run --config {}[/yellow]".format(config))


# ---------------------------------------------------------------------------
# rag ingest run
# ---------------------------------------------------------------------------

@ingest_app.command()
def run(
    config: str = typer.Option("ingestion-config.yaml", "--config", "-c", help="Path to config YAML"),
    dry_run: bool = typer.Option(False, "--dry-run", "-n", help="Scan and diff only, no ingestion"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Emit report as JSON to stdout"),
):
    """Run the ingestion pipeline: scan, diff, parse, chunk, embed, index."""
    cfg = IngestionConfig.from_yaml(config)

    source = cfg.resolve_source_dir()
    if not source.is_dir():
        console.print("[red]Source directory not found: {}[/red]".format(source))
        raise typer.Exit(code=1)

    console.print("[bold]Ingestion pipeline[/bold]")
    console.print("  Source : {}".format(source))
    console.print("  Config : {}".format(Path(config).resolve()))
    console.print()

    avail = list_available()
    console.print("[bold]Available parsers:[/bold]")
    for line in avail:
        console.print("  {}".format(line))
    console.print()
    console.print("[bold]Supported extensions:[/bold] {}".format(", ".join(sorted(cfg.supported_extensions))))
    console.print("  Manifest : {}".format(cfg.resolve_manifest_path()))
    console.print("  Chunking : {} chars, {} overlap".format(cfg.chunk_size, cfg.chunk_overlap))
    console.print("  Batch    : {} files, {} retries".format(cfg.batch_size, cfg.max_retries))
    console.print()

    if dry_run:
        _dry_run(cfg)
        return

    pipeline = IngestionPipeline(cfg)
    report = pipeline.run_with_lock()

    if report is None:
        console.print("[yellow]Pipeline is already running (another process holds the lock).[/yellow]")
        raise typer.Exit(code=1)

    _print_report(report, fmt="json" if json_output else "table")


# ---------------------------------------------------------------------------
# rag ingest check
# ---------------------------------------------------------------------------

@ingest_app.command()
def check(
    config: str = typer.Option("ingestion-config.yaml", "--config", "-c", help="Path to config YAML"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Emit result as JSON"),
):
    """Scan and diff without ingesting (summary of what would change)."""
    cfg = IngestionConfig.from_yaml(config)
    _dry_run(cfg, json_output=json_output)


# ---------------------------------------------------------------------------
# Dry-run helper
# ---------------------------------------------------------------------------

def _dry_run(cfg: IngestionConfig, json_output: bool = False) -> None:
    from .scanner import Manifest, Scanner

    source = cfg.resolve_source_dir()
    if not source.is_dir():
        console.print("[red]Source directory not found: {}[/red]".format(source))
        raise typer.Exit(code=1)

    scanner = Scanner(cfg)
    manifest = Manifest(cfg)

    with console.status("[bold]Scanning…[/bold]"):
        current = scanner.scan()
        manifest.load()
        diff = manifest.diff(current)

    console.print()
    console.print("[bold]Summary[/bold] — {} files found".format(len(current)))
    table = Table("Status", "Count", "Files")
    table.add_row("[green]new[/green]", str(len(diff.new)), _shorten(diff.new[0].rel_path) if diff.new else "-")
    table.add_row("[yellow]modified[/yellow]", str(len(diff.modified)), _shorten(diff.modified[0].rel_path) if diff.modified else "-")
    table.add_row("[red]deleted[/red]", str(len(diff.deleted)), _shorten(diff.deleted[0].rel_path) if diff.deleted else "-")
    table.add_row("unchanged", str(len(diff.unchanged)), "-")
    console.print(table)

    if json_output:
        data = {
            "scanned": len(current),
            "new": len(diff.new),
            "modified": len(diff.modified),
            "deleted": len(diff.deleted),
            "unchanged": len(diff.unchanged),
            "to_process": len(diff.to_process),
        }
        console.print(json.dumps(data, indent=2))

    if len(diff.to_process) == 0:
        console.print("[green]Everything up to date. No ingestion needed.[/green]")
    else:
        console.print("\n[yellow]{} file(s) to process[/yellow]".format(len(diff.to_process)))


# ---------------------------------------------------------------------------
# Report printer
# ---------------------------------------------------------------------------

def _print_report(report, fmt: str = "table") -> None:
    if fmt == "json":
        data = {
            "pipeline_id": report.pipeline_id,
            "started_at": report.started_at.isoformat(),
            "duration_ms": report.duration_ms,
            "scanned": report.scanned,
            "processed": report.processed,
            "succeeded": report.succeeded,
            "failed": report.failed,
            "deleted": report.deleted,
            "total_chunks": report.total_chunks,
            "files": [
                {
                    "path": fr.rel_path,
                    "status": fr.status,
                    "chunks": fr.chunks,
                    "error": fr.error,
                    "duration_ms": round(fr.duration_ms, 1),
                }
                for fr in report.file_results
            ],
        }
        console.print(json.dumps(data, indent=2))
        return

    console.print()
    console.print("[bold]Ingestion Report[/bold]")
    console.print("  Pipeline : {}".format(report.pipeline_id))
    console.print("  Started  : {}".format(report.started_at.strftime("%Y-%m-%d %H:%M:%S")))
    console.print("  Duration : {:.2f}s".format(report.duration_ms / 1000))
    console.print("  Source   : {}".format(report.config_source))
    console.print()

    summary = Table("Metric", "Value")
    summary.add_row("Files scanned", str(report.scanned))
    summary.add_row("Files processed", str(report.processed))
    summary.add_row("[green]Succeeded[/green]", str(report.succeeded))
    summary.add_row("[red]Failed[/red]", str(report.failed))
    summary.add_row("Deleted (cleanup)", str(report.deleted))
    summary.add_row("Total chunks created", str(report.total_chunks))
    console.print(summary)
    console.print()

    if report.file_results:
        file_table = Table("File", "Status", "Chunks", "Time", "Error")
        for fr in report.file_results:
            status_style = {
                "success": "[green]success[/green]",
                "failed": "[red]failed[/red]",
                "skipped": "[yellow]skipped[/yellow]",
            }.get(fr.status, fr.status)
            file_table.add_row(
                _shorten(fr.rel_path, 50),
                status_style,
                str(fr.chunks),
                "{:.2f}s".format(fr.duration_ms / 1000),
                fr.error or "-",
            )
        console.print(file_table)
