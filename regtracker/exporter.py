"""
Export engine for registry diff results.
Supports exporting DiffResult objects to CSV, HTML, and Markdown.
"""

import csv
from typing import TextIO
from regtracker.diff import DiffResult

# ---------------------------------------------------------------------------
# HTML Template
# ---------------------------------------------------------------------------
_HTML_TEMPLATE = """<!DOCTYPE html>
<html>
<head>
    <title>Registry Diff Report</title>
    <style>
        body {{ font-family: system-ui, -apple-system, sans-serif; background: #f8f9fa; margin: 2rem; color: #333; }}
        h1 {{ color: #2c3e50; border-bottom: 2px solid #eee; padding-bottom: 10px; }}
        .summary {{ background: white; padding: 20px; border-radius: 8px; box-shadow: 0 2px 4px rgba(0,0,0,0.1); margin-bottom: 20px; }}
        .badge {{ padding: 4px 8px; border-radius: 4px; font-weight: bold; color: white; display: inline-block; margin-right: 10px; }}
        .badge.added {{ background: #2ecc71; }}
        .badge.deleted {{ background: #e74c3c; }}
        .badge.modified {{ background: #f1c40f; color: #333; }}
        table {{ width: 100%; border-collapse: collapse; background: white; box-shadow: 0 2px 4px rgba(0,0,0,0.1); }}
        th, td {{ padding: 12px 15px; text-align: left; border-bottom: 1px solid #ddd; }}
        th {{ background-color: #2c3e50; color: white; }}
        tr.added td:first-child {{ border-left: 4px solid #2ecc71; background: #eafaf1; }}
        tr.deleted td:first-child {{ border-left: 4px solid #e74c3c; background: #fdedec; }}
        tr.modified td:first-child {{ border-left: 4px solid #f1c40f; background: #fef9e7; }}
        .path {{ font-family: monospace; font-size: 0.9em; }}
        .value {{ font-family: monospace; white-space: pre-wrap; word-break: break-all; }}
    </style>
</head>
<body>
    <h1>Registry Diff Report</h1>
    <div class="summary">
        Comparing <span class="path">{snap_a}</span> with <span class="path">{snap_b}</span><br><br>
        <div class="badge added">Added: {added_count}</div>
        <div class="badge deleted">Deleted: {deleted_count}</div>
        <div class="badge modified">Modified: {modified_count}</div>
    </div>
    
    <table>
        <thead>
            <tr>
                <th>Type</th>
                <th>Path</th>
                <th>Value Name</th>
                <th>Old Value</th>
                <th>New Value</th>
            </tr>
        </thead>
        <tbody>
            {rows}
        </tbody>
    </table>
</body>
</html>
"""

def _escape_html(text: str) -> str:
    return str(text).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def export_html(diff: DiffResult, file: TextIO):
    rows = []
    
    # Deleted
    for (kpath, vname), entry in sorted(diff.deleted.items()):
        disp = vname if vname else "(Default)"
        rows.append(f'<tr class="deleted"><td>Removed</td><td class="path">{_escape_html(kpath)}</td><td>{_escape_html(disp)}</td><td class="value">{_escape_html(entry.value_data)}</td><td>-</td></tr>')
        
    # Added
    for (kpath, vname), entry in sorted(diff.added.items()):
        disp = vname if vname else "(Default)"
        rows.append(f'<tr class="added"><td>Added</td><td class="path">{_escape_html(kpath)}</td><td>{_escape_html(disp)}</td><td>-</td><td class="value">{_escape_html(entry.value_data)}</td></tr>')
        
    # Modified
    for (kpath, vname), (old_e, new_e) in sorted(diff.modified.items()):
        disp = vname if vname else "(Default)"
        rows.append(f'<tr class="modified"><td>Modified</td><td class="path">{_escape_html(kpath)}</td><td>{_escape_html(disp)}</td><td class="value">{_escape_html(old_e.value_data)}</td><td class="value">{_escape_html(new_e.value_data)}</td></tr>')

    html = _HTML_TEMPLATE.format(
        snap_a=diff.snapshot_a_id,
        snap_b=diff.snapshot_b_id,
        added_count=len(diff.added),
        deleted_count=len(diff.deleted),
        modified_count=len(diff.modified),
        rows="\\n".join(rows)
    )
    file.write(html)


def export_csv(diff: DiffResult, file: TextIO):
    writer = csv.writer(file)
    writer.writerow(["Change Type", "Key Path", "Value Name", "Value Type", "Old Value", "New Value"])
    
    for (kpath, vname), entry in sorted(diff.deleted.items()):
        writer.writerow(["DELETED", kpath, vname, entry.value_type, entry.value_data, ""])
        
    for (kpath, vname), entry in sorted(diff.added.items()):
        writer.writerow(["ADDED", kpath, vname, entry.value_type, "", entry.value_data])
        
    for (kpath, vname), (old_e, new_e) in sorted(diff.modified.items()):
        writer.writerow(["MODIFIED", kpath, vname, new_e.value_type, old_e.value_data, new_e.value_data])


def export_markdown(diff: DiffResult, file: TextIO):
    lines = [
        f"# Registry Diff Report",
        f"**Baseline:** `{diff.snapshot_a_id}` | **Target:** `{diff.snapshot_b_id}`\\n",
        f"🟢 Added: {len(diff.added)} | 🔴 Deleted: {len(diff.deleted)} | 🟡 Modified: {len(diff.modified)}\\n",
        "| Change | Path | Name | Old Value | New Value |",
        "|---|---|---|---|---|"
    ]
    
    for (kpath, vname), entry in sorted(diff.deleted.items()):
        lines.append(f"| 🔴 Deleted | `{kpath}` | `{vname}` | `{entry.value_data}` | - |")
        
    for (kpath, vname), entry in sorted(diff.added.items()):
        lines.append(f"| 🟢 Added | `{kpath}` | `{vname}` | - | `{entry.value_data}` |")
        
    for (kpath, vname), (old_e, new_e) in sorted(diff.modified.items()):
        lines.append(f"| 🟡 Modified | `{kpath}` | `{vname}` | `{old_e.value_data}` | `{new_e.value_data}` |")
        
    file.write("\\n".join(lines) + "\\n")
