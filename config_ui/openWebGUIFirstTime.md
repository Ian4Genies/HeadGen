# Config UI — first-time setup

Web editor for pipeline JSON at **http://127.0.0.1:8420**. No Node/npm required.

## Prerequisites

1. Clone the HeadGen repo locally.
2. Install **Python 3.11+** from [python.org](https://www.python.org/downloads/).
   - On Windows, check **“Add python.exe to PATH”** during install.
   - Or install the **py launcher** (included with the official installer).

Verify in a new terminal:

```powershell
python --version
# or
py -3 --version
```

## Launch (Windows)

Double-click or run from repo root:

```
config_ui\open.bat
```

PowerShell alternative:

```powershell
.\config_ui\start.ps1
```

On first run, the script will:

1. Create `.venv` in the repo root (if missing)
2. Install `config_ui/requirements.txt` into that venv
3. Open your browser and start the server on port **8420**

Leave the terminal window open while you use the UI. Press **Ctrl+C** to stop the server.

## If the window closes immediately

The updated `open.bat` pauses on errors instead of exiting silently. Re-run it and read the message.

| Error | Fix |
|-------|-----|
| `Python not found` | Install Python 3.11+ and ensure it is on PATH, or use `py -3`. |
| `data\config not found` | Run `open.bat` from this repo — not a copied shortcut pointing elsewhere. |
| `Failed to create .venv` | Python install may be broken or too old; reinstall 3.11+. |
| `pip install failed` | Check network/proxy; run the bat again after fixing connectivity. |
| `Server exited with an error` | Read the traceback above the pause line in the terminal. |
| `No module named 'bpy'` | Pull latest repo — config UI does not need Blender or `bpy`. Re-run `open.bat` to recreate deps. |
| `No module named 'numpy'` | Re-run `open.bat` — latest `config_ui/requirements.txt` includes numpy. |

## Blender vs config UI

The config web UI uses only `synth_head/core/` (pure Python). **Blender and the `bpy` package are not required** to run `open.bat`.

Blender is only needed for running the addon inside Blender (Blender Development extension or manual install). That is separate from the config UI setup.

## Shortcut note

Prefer running `config_ui\open.bat` directly. A desktop `.lnk` shortcut only works if its **Target** points at the bat file inside your local clone.

## Manual start (optional)

From repo root:

```powershell
python -m venv .venv
.\.venv\Scripts\pip.exe install -r config_ui\requirements.txt
.\.venv\Scripts\python.exe -m config_ui.server
```

Then open **http://127.0.0.1:8420** in your browser.

## More docs

See [README.md](README.md) for profiles, manifests, and the optional React build.
