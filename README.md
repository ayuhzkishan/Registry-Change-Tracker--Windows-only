# 🔍 Registry Change Tracker (Windows)

A powerful command-line tool for tracking, comparing, and monitoring Windows Registry changes. Built for **malware analysts**, **system administrators**, and **software debuggers**.

## ✨ Features

- **Targeted Snapshots** — Capture specific registry hives (e.g., `HKCU\Software`) instead of scanning the entire registry
- **Snapshot Storage** — Persist snapshots in a local SQLite database with metadata (timestamp, hostname, OS version)
- **Diff Engine** — Compare two snapshots to find Added, Deleted, and Modified keys/values
- **Noise Filtering** — Automatically exclude volatile keys (MRU lists, caches, window positions)
- **Real-time Monitoring** — Watch specific registry paths for live changes with process attribution
- **Export** — Generate reports in HTML, CSV, or Markdown
- **Rollback Generation** — Automatically generate `.reg` files to undo detected changes

## 🚀 Quick Start

### Prerequisites

- Python 3.9+
- Windows 10 / 11

### Installation

```bash
git clone https://github.com/yourusername/Registry-Change-Tracker--Windows-only.git
cd Registry-Change-Tracker--Windows-only
pip install -r requirements.txt
```

### Usage

**Take a snapshot:**
```bash
python cli.py snapshot take --hive "HKCU\Software" --label "before_install"
```

**List all snapshots:**
```bash
python cli.py snapshot list
```

**Compare two snapshots:**
```bash
python cli.py diff <snapshot_id_1> <snapshot_id_2>
```

## 🗺️ Roadmap

- [x] **Phase 1:** Snapshot engine + SQLite storage
- [x] **Phase 2:** Diffing engine with noise filtering
- [x] **Phase 3:** Real-time monitoring + process attribution
- [x] **Phase 4:** Multi-format export + rollback `.reg` generation
- [x] **Phase 5:** Web dashboard + PyInstaller packaging

## 📄 License

MIT License

## 🤝 Contributing

Contributions, issues, and feature requests are welcome!
