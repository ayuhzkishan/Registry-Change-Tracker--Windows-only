"""
Registry Change Tracker — CLI entry point.

Usage:
    python cli.py snapshot take --hive "HKCU\\Software" --label "before_install"
    python cli.py snapshot list
    python cli.py snapshot info <snapshot_id>
    python cli.py snapshot delete <snapshot_id>
"""

from __future__ import annotations

import time
import typer
from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.text import Text

from regtracker.snapshot import take_snapshot
from regtracker.storage import (
    save_snapshot,
    list_snapshots,
    get_snapshot_meta,
    delete_snapshot,
    load_snapshot_entries,
)
from regtracker.diff import compare_snapshots
from regtracker.config import VALUE_TYPE_NAMES

# ---------------------------------------------------------------------------
# App setup
# ---------------------------------------------------------------------------

app = typer.Typer(
    name="regtracker",
    help="🔍 Registry Change Tracker — Snapshot, compare, and monitor Windows Registry changes.",
    rich_markup_mode="rich",
    no_args_is_help=True,
)

snapshot_app = typer.Typer(
    name="snapshot",
    help="📸 Take, list, inspect, and delete registry snapshots.",
    no_args_is_help=True,
)
app.add_typer(snapshot_app, name="snapshot")

console = Console()

# ---------------------------------------------------------------------------
# Snapshot commands
# ---------------------------------------------------------------------------


@snapshot_app.command("take")
def snapshot_take(
    hive: str = typer.Option(
        ...,
        "--hive", "-h",
        help="Registry path to snapshot, e.g. 'HKCU\\\\Software' or 'HKLM\\\\SYSTEM'.",
    ),
    label: str = typer.Option(
        "unnamed",
        "--label", "-l",
        help="A descriptive label for this snapshot.",
    ),
):
    """Take a new snapshot of a registry hive/path."""
    start = time.time()

    try:
        result = take_snapshot(hive)
    except ValueError as e:
        console.print(f"\n[bold red]❌ Error:[/] {e}\n")
        raise typer.Exit(code=1)

    elapsed = time.time() - start

    # Save to database
    snapshot_id = save_snapshot(result, label)

    # Summary panel
    summary = Text()
    summary.append(f"  Snapshot ID:    ", style="dim")
    summary.append(f"{snapshot_id}\n", style="bold green")
    summary.append(f"  Label:          ", style="dim")
    summary.append(f"{label}\n", style="white")
    summary.append(f"  Hive:           ", style="dim")
    summary.append(f"{result.hive_name}\\{result.root_path}\n", style="yellow")
    summary.append(f"  Keys scanned:   ", style="dim")
    summary.append(f"{result.keys_scanned:,}\n", style="cyan")
    summary.append(f"  Values captured: ", style="dim")
    summary.append(f"{len(result.entries):,}\n", style="cyan")
    summary.append(f"  Access denied:  ", style="dim")
    summary.append(f"{result.keys_denied:,}\n", style="red" if result.keys_denied > 0 else "green")
    summary.append(f"  Time taken:     ", style="dim")
    summary.append(f"{elapsed:.2f}s", style="white")

    console.print()
    console.print(Panel(
        summary,
        title="[bold green]✅ Snapshot Saved[/]",
        border_style="green",
        padding=(1, 2),
    ))
    console.print()


@snapshot_app.command("list")
def snapshot_list():
    """List all saved snapshots."""
    snapshots = list_snapshots()

    if not snapshots:
        console.print("\n[yellow]⚠️  No snapshots found.[/] Take one with: [cyan]python cli.py snapshot take --hive \"HKCU\\\\Software\"[/]\n")
        raise typer.Exit()

    table = Table(
        title="📸 Saved Snapshots",
        show_header=True,
        header_style="bold magenta",
        border_style="dim",
        padding=(0, 1),
    )

    table.add_column("ID", style="bold green", min_width=14)
    table.add_column("Label", style="white", min_width=15)
    table.add_column("Hive Path", style="yellow")
    table.add_column("Entries", justify="right", style="cyan")
    table.add_column("Keys", justify="right", style="cyan")
    table.add_column("Denied", justify="right", style="red")
    table.add_column("Timestamp", style="dim")

    for s in snapshots:
        # Format timestamp for display
        ts = s.timestamp
        if "T" in ts:
            ts = ts.replace("T", " ")[:19]

        hive_path = f"{s.hive}\\{s.root_path}" if s.root_path else s.hive

        table.add_row(
            s.id,
            s.label,
            hive_path,
            f"{s.entry_count:,}",
            f"{s.keys_scanned:,}",
            f"{s.keys_denied:,}",
            ts,
        )

    console.print()
    console.print(table)
    console.print(f"\n  [dim]Total: {len(snapshots)} snapshot(s)[/]\n")


@snapshot_app.command("info")
def snapshot_info(
    snapshot_id: str = typer.Argument(..., help="The snapshot ID to inspect."),
):
    """Show detailed metadata for a specific snapshot."""
    meta = get_snapshot_meta(snapshot_id)

    if meta is None:
        console.print(f"\n[bold red]❌ Snapshot '{snapshot_id}' not found.[/]\n")
        raise typer.Exit(code=1)

    hive_path = f"{meta.hive}\\{meta.root_path}" if meta.root_path else meta.hive

    info = Text()
    info.append(f"  ID:             ", style="dim")
    info.append(f"{meta.id}\n", style="bold green")
    info.append(f"  Label:          ", style="dim")
    info.append(f"{meta.label}\n", style="white")
    info.append(f"  Hive Path:      ", style="dim")
    info.append(f"{hive_path}\n", style="yellow")
    info.append(f"  Timestamp:      ", style="dim")
    info.append(f"{meta.timestamp}\n", style="white")
    info.append(f"  Hostname:       ", style="dim")
    info.append(f"{meta.hostname}\n", style="white")
    info.append(f"  OS Version:     ", style="dim")
    info.append(f"{meta.os_version}\n", style="white")
    info.append(f"  User:           ", style="dim")
    info.append(f"{meta.username}\n", style="white")
    info.append(f"  Keys scanned:   ", style="dim")
    info.append(f"{meta.keys_scanned:,}\n", style="cyan")
    info.append(f"  Values captured: ", style="dim")
    info.append(f"{meta.entry_count:,}\n", style="cyan")
    info.append(f"  Access denied:  ", style="dim")
    info.append(f"{meta.keys_denied:,}", style="red" if meta.keys_denied > 0 else "green")

    console.print()
    console.print(Panel(
        info,
        title=f"[bold cyan]📋 Snapshot Details[/]",
        border_style="cyan",
        padding=(1, 2),
    ))
    console.print()


@snapshot_app.command("delete")
def snapshot_delete_cmd(
    snapshot_id: str = typer.Argument(..., help="The snapshot ID to delete."),
    force: bool = typer.Option(
        False, "--force", "-f",
        help="Skip confirmation prompt.",
    ),
):
    """Delete a snapshot from the database."""
    meta = get_snapshot_meta(snapshot_id)

    if meta is None:
        console.print(f"\n[bold red]❌ Snapshot '{snapshot_id}' not found.[/]\n")
        raise typer.Exit(code=1)

    if not force:
        hive_path = f"{meta.hive}\\{meta.root_path}" if meta.root_path else meta.hive
        console.print(
            f"\n[yellow]⚠️  About to delete snapshot [bold]{snapshot_id}[/bold] "
            f"('{meta.label}', {hive_path}, {meta.entry_count:,} entries)[/]"
        )
        confirm = typer.confirm("Are you sure?")
        if not confirm:
            console.print("[dim]Cancelled.[/]\n")
            raise typer.Exit()

    deleted = delete_snapshot(snapshot_id)
    if deleted:
        console.print(f"\n[green]✅ Snapshot '{snapshot_id}' deleted.[/]\n")
    else:
        console.print(f"\n[red]❌ Failed to delete snapshot '{snapshot_id}'.[/]\n")

# ---------------------------------------------------------------------------
# Diff logic
# ---------------------------------------------------------------------------

@app.command("diff")
def diff_cmd(
    snapshot_a: str = typer.Argument(..., help="The FIRST (baseline) snapshot ID."),
    snapshot_b: str = typer.Argument(..., help="The SECOND (new) snapshot ID."),
    no_filter: bool = typer.Option(
        False, "--no-filter",
        help="Disable noise filtering (show all changes including MRU caches/window positions).",
    ),
):
    """Compare two snapshots and show what changed."""
    # 1. Fetch metadata first to ensure both exist and to show context
    meta_a = get_snapshot_meta(snapshot_a)
    meta_b = get_snapshot_meta(snapshot_b)
    
    if not meta_a:
        console.print(f"\n[bold red]❌ Baseline snapshot '{snapshot_a}' not found.[/]\n")
        raise typer.Exit(1)
    if not meta_b:
        console.print(f"\n[bold red]❌ Target snapshot '{snapshot_b}' not found.[/]\n")
        raise typer.Exit(1)

    # Sanity check: warn if diffing completely different hives
    if meta_a.hive != meta_b.hive or meta_a.root_path != meta_b.root_path:
        console.print("[yellow]⚠️  Warning: Comparing snapshots from different registry paths.[/]")
        console.print(f"  A: {meta_a.hive}\\{meta_a.root_path}")
        console.print(f"  B: {meta_b.hive}\\{meta_b.root_path}\n")

    # 2. Load entries
    with console.status("[cyan]Loading snapshot data...[/]"):
        entries_a = load_snapshot_entries(snapshot_a)
        entries_b = load_snapshot_entries(snapshot_b)

    # 3. Compute Diff
    with console.status("[cyan]Calculating differences...[/]"):
        result = compare_snapshots(
            snapshot_a, entries_a, snapshot_b, entries_b, apply_filters=not no_filter
        )

    # 4. Display Results
    if result.total_changes == 0:
        console.print(Panel(
            "[bold green]No differences found![/]",
            title="🔍 Diff Results", border_style="green", padding=(1,2)
        ))
        raise typer.Exit()

    # Display Deletions First (Red)
    if result.deleted:
        console.print("\n[bold red]🔴 DELETED[/]")
        for (kpath, vname), entry in sorted(result.deleted.items()):
            display_name = vname if vname else "(Default)"
            console.print(f"  [dim]{kpath}\\[/]{display_name}")

    # Display Additions (Green)
    if result.added:
        console.print("\n[bold green]🟢 ADDED[/]")
        for (kpath, vname), entry in sorted(result.added.items()):
            display_name = vname if vname else "(Default)"
            console.print(f"  [dim]{kpath}\\[/]{display_name} = [green]{entry.value_data}[/]")

    # Display Modifications (Yellow)
    if result.modified:
        console.print("\n[bold yellow]🟡 MODIFIED[/]")
        for (kpath, vname), (old_e, new_e) in sorted(result.modified.items()):
            display_name = vname if vname else "(Default)"
            console.print(f"  [dim]{kpath}\\[/]{display_name}")
            console.print(f"    [dim]Old:[/] {old_e.value_data}")
            console.print(f"    [yellow]New:[/] {new_e.value_data}")

    # Summary Panel
    summary = Text()
    summary.append(f"  🟢 Added:    {len(result.added):,}\n", style="green")
    summary.append(f"  🔴 Deleted:  {len(result.deleted):,}\n", style="red")
    summary.append(f"  🟡 Modified: {len(result.modified):,}\n", style="yellow")
    
    if not no_filter:
        summary.append(f"\n  🛡️  Filtered Noise: {result.filtered_count:,} items", style="dim")

    console.print()
    console.print(Panel(
        summary,
        title="[bold blue]📊 Diff Summary[/]",
        border_style="blue",
        padding=(0, 2),
    ))
    console.print()


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    app()
