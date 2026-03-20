# Blender + Cursor — Python Development Environment
### Onboarding Guide
*For developers with intermediate Python and Blender experience*

---

## 1. What We Are Building

We maintain a Blender addon codebase that needs to work reliably across three distinct contexts:

- **External (Cursor IDE)** — writing and editing code with full autocomplete and linting
- **Headless / local testing** — running automated tests without opening Blender
- **GHA (GitHub Actions CI)** — running the same tests automatically on every push

To achieve this, we use two parallel development environments that complement each other. They share the same source code — no conditional imports, no environment flags, no code changes needed when switching contexts.

### The Two Environments at a Glance

| Aspect | venv + pytest | Blender Extension |
|---|---|---|
| Python source | `bpy` pip package | Blender bundled Python |
| Autocomplete | `fake-bpy-module` | Built-in to Blender |
| Test runner | pytest directly | Visual / operator output |
| Feedback loop | Terminal output | Live Blender viewport |
| Used for | Unit tests, CI/GHA | Visual/interactive dev |
| Code changes needed? | None | None |

> **NOTE:** These two environments are parallel, not competing. They are both active at the same time and serve different purposes. You will use both regularly.

---

## 2. Why This Approach

Blender bundles its own Python interpreter. Normally, this means your IDE cannot see the `bpy` API, you cannot run tests without opening Blender, and CI pipelines require a full Blender installation just to run a unit test.

The modern solution is the `bpy` package on PyPI — Blender's Python API installable as a regular package. This means the same `import bpy` line in your code works identically in Cursor, in a headless test run, and in a GHA runner. No special handling needed.

The **Blender Development extension** (by Jacques Lucke) solves the remaining problem: live interactive testing. It launches Blender from Cursor, creates a symlink so Blender reads your live source files directly, and reloads your addon on every save. This gives you a sub-second feedback loop without any manual reinstall or restart.

The key architectural principle that makes this work cleanly is keeping your code in two layers:

- `core.py` — pure Python business logic, no `bpy` dependency where possible
- `operators.py` — thin Blender-facing layer that calls into core

The thinner the operator layer, the more of your code is testable with plain pytest without needing Blender at all.

---

## 3. Prerequisites

Before setting up either environment, confirm you have the following installed:

- Cursor IDE (cursor.com)
- Blender 5.0.1 installed locally
- Python 3.11 installed on your system — this must match the version Blender 5.0 bundles
- Git

> ⚠️ **Python version must be exactly 3.11.** The `bpy` pip package is version-locked to match Blender. Using 3.12 or 3.13 will cause `bpy` installation to fail.

To verify Python 3.11 is available on your system:

```bash
python3.11 --version        # mac / linux
py -3.11 --version          # windows
```

If you do not have Python 3.11, download it from python.org and install it alongside your system Python. You do not need to change your default Python — you only need 3.11 to be available.

---

## 4. Required Project Structure

Your addon must be a folder-based Python package — not a single `.py` file. This is required by both the Blender extension and by Python's import system.

```
my-blender-addon/
  __init__.py          ← required — entry point Blender loads
  core.py              ← pure Python logic (no bpy where possible)
  operators.py         ← thin Blender operator layer
  tests/
    test_core.py       ← pytest tests against core.py
  .venv/               ← virtual environment (not committed to git)
  requirements.txt     ← package list (committed to git)
  .gitignore
```

> **NOTE:** If you are starting a new project, use **Blender: New Addon** from the Cursor command palette. It scaffolds this structure for you automatically.

---

## 5. Setting Up the Python Virtual Environment

The virtual environment (venv) is an isolated Python sandbox that lives inside your project folder. It contains a specific Python version and only the packages your project needs. It is not committed to git — only the `requirements.txt` file that describes what it contains is committed.

### Step 1 — Navigate to your project folder

```bash
cd path/to/my-blender-addon
```

### Step 2 — Create the venv using Python 3.11

Specify 3.11 explicitly — do not use just `python` or `python3`, as those may point to a different version.

```bash
python3.11 -m venv .venv       # mac / linux
py -3.11 -m venv .venv         # windows
```

### Step 3 — Activate the venv

Activation temporarily rewires your terminal so that `python` and `pip` point to the ones inside `.venv`.

```bash
source .venv/bin/activate       # mac / linux
.venv\Scripts\Activate.ps1      # windows powershell
```

Your terminal prompt will show `(.venv)` when active.

### Step 4 — Install required packages

```bash
pip install bpy==5.0.1
pip install fake-bpy-module-5.0
pip install pytest
```

- `bpy` — Blender's Python API as a pip package. Enables `import bpy` in tests and in Cursor.
- `fake-bpy-module` — Provides type stubs so Cursor shows autocomplete for the `bpy` API.
- `pytest` — Test runner for automated and CI tests.

### Step 5 — Save the package list

```bash
pip freeze > requirements.txt
```

Commit this file to git. Anyone can recreate your exact venv from scratch with:

```bash
pip install -r requirements.txt
```

### Step 6 — Add `.venv` to `.gitignore`

Create or edit `.gitignore` in your project root:

```
.venv/
__pycache__/
*.pyc
```

### Step 7 — Point Cursor at the venv

Open the command palette (`Ctrl+Shift+P` / `Cmd+Shift+P`) and run **Python: Select Interpreter**. Choose the interpreter inside `.venv` — it will appear as `./.venv/bin/python`.

From this point on, Cursor uses your venv for autocomplete, linting, and the integrated terminal. You will not need to manually activate the venv for normal development.

---

## 6. Setting Up the Blender Development Extension

The Blender Development extension (by Jacques Lucke) bridges Cursor and a live running Blender session. It creates a symlink from your project folder into Blender's addon directory, so Blender always reads your live source files. When you save in Cursor, Blender reloads your addon automatically.

### Step 1 — Install the extension in Cursor

Open the Extensions panel (`Ctrl+Shift+X`) and search for:

```
JacquesLucke.blender-development
```

Install it. This is the same extension registry as VS Code — Cursor is fully compatible.

### Step 2 — Open your addon folder in Cursor

Use **File > Open Folder** and open the root of your addon (the folder containing `__init__.py`). The extension works per-workspace and expects exactly one addon per folder.

### Step 3 — Point the extension at your Blender executable

Open the command palette and run **Blender: Start**. On first run it will ask you to locate your Blender executable.

- **Windows:** `C:\Program Files\Blender Foundation\Blender 5.0\blender.exe`
- **Mac:** `/Applications/Blender.app/Contents/MacOS/Blender`
- **Linux:** `/usr/bin/blender` or wherever you installed it

Blender will launch. On first launch the extension installs some Python dependencies into Blender — keep a stable internet connection and wait for it to complete.

### Step 4 — Enable reload on save

Open Cursor settings (`Ctrl+,`) and search for `blender.addon.reloadOnSave`. Enable it.

From this point on, every time you save a file in Cursor (`Ctrl+S`), your addon reloads in the live Blender session automatically.

### Step 5 — (Optional) Isolate from your personal Blender profile

To keep development separate from your normal Blender setup, add this to `.vscode/settings.json`:

```json
"blender.environmentVariables": {
  "BLENDER_USER_RESOURCES": "${workspaceFolder}/blender_vscode_development"
}
```

> **NOTE:** This is recommended. Without it, the development symlink will appear in your personal Blender installation.

---

## 7. Using the venv During Development

### Autocomplete and linting in Cursor

Once Cursor is pointed at the `.venv` interpreter, autocomplete for `bpy` works automatically via `fake-bpy-module`. Just write code.

### Running tests locally

Open the Cursor integrated terminal (`` Ctrl+` ``). Run:

```bash
pytest                          # run all tests
pytest tests/test_core.py       # run a specific file
pytest -v                       # verbose output
```

> **NOTE:** Tests run against the `bpy` pip package, not a live Blender session. They are fast and require no Blender window.

### Recreating the venv from scratch

If your venv becomes corrupted or you are setting up on a new machine:

```bash
rm -rf .venv                          # delete the old one
python3.11 -m venv .venv              # recreate it
source .venv/bin/activate             # activate
pip install -r requirements.txt       # restore all packages
```

### Adding new packages

```bash
pip install some-package
pip freeze > requirements.txt
```

Commit the updated `requirements.txt` so teammates and GHA stay in sync.

---

## 8. Using the Blender Extension During Development

### The save-to-reload loop

With `reloadOnSave` enabled, your normal workflow is:

1. Edit code in Cursor
2. Hit `Ctrl+S`
3. Blender reloads your addon automatically (sub-second)
4. Test visually in the Blender viewport

Terminal output from Blender (`print` statements, errors, tracebacks) appears directly in the Cursor terminal panel — you do not need to look at Blender's system console separately.

### Breakpoint debugging

1. Launch Blender via **Blender: Start** (not by opening Blender directly)
2. Set breakpoints in Cursor by clicking the gutter next to a line number
3. Trigger the relevant operator in Blender
4. Cursor will pause at your breakpoint with full variable inspection

> ⚠️ **Debugging only works when Blender was launched via the extension.** Opening Blender independently will not connect to Cursor's debugger.

### Manual reload

If you need to force a reload without saving (e.g. after a Blender crash and restart):

```
Ctrl+Shift+P → Blender: Reload Addons
```

### Module reload boilerplate

If your addon has multiple files, Python's module cache can cause stale code to persist across reloads. Add this pattern to the top of your `__init__.py`:

```python
import importlib

if "bpy" in locals():
    importlib.reload(core)
    importlib.reload(operators)

import bpy
from . import core, operators
```

Add one `importlib.reload()` line per module in your addon. This ensures every save picks up changes to all files, not just the one you edited.

---

## 9. Switching Between Environments

Both environments are always available simultaneously — there is no mode switch or configuration change required.

| I want to... | Use | How |
|---|---|---|
| Write / edit code with autocomplete | venv (always active) | Cursor selects interpreter automatically |
| Run unit tests locally | venv | `pytest` in Cursor terminal |
| See results live in Blender | Blender Extension | `Ctrl+S` triggers auto-reload |
| Debug with breakpoints | Blender Extension | Blender: Start, set breakpoints in Cursor |
| Run tests in CI / GHA | venv | `pip install -r requirements.txt`, then `pytest` |
| Test against real Blender binary | Blender Extension | Blender: Start |

### The golden rule

Write code once. Test logic with pytest (fast, no Blender needed). Verify visual behavior in Blender (interactive, real API). Run the same pytest suite in GHA (automated, no Blender needed).

If you find yourself writing code that behaves differently in one environment than another, that is a sign the operator layer is too thick — move logic into `core.py`.

### What each environment cannot do

- The **venv / pytest** environment cannot test rendering, viewport behavior, or any UI interaction. Use the Blender extension for that.
- The **Blender extension** environment does not run pytest automatically or report to CI. Use the venv for that.
- **Neither environment requires code changes to switch between them.** If you are adding environment guards, stop and reconsider the architecture.

### Keeping both environments healthy

- After adding any new dependency: `pip freeze > requirements.txt` and commit it.
- After updating Blender to a new version: update `bpy` and `fake-bpy-module` versions in `requirements.txt` to match, and recreate `.venv`.
- If Blender fails to reload after a save: run **Blender: Reload Addons** manually, then check the Cursor terminal for the error.
- If pytest fails with import errors: confirm `.venv` is selected as the Cursor interpreter and that `bpy` is installed in it.
- The `.venv` folder and `blender_vscode_development` folder are both safe to delete and recreate at any time — they contain no source code.

---

## 10. GitHub Actions CI

Because tests run against the `bpy` pip package, GHA setup is straightforward. Add this workflow file to your repository:

```yaml
# .github/workflows/test.yml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: '3.11'     # must match Blender 5.0

      - run: pip install -r requirements.txt

      - run: pytest
```

> **NOTE:** The `python-version` in the GHA workflow must match the version used to create your `.venv`. For Blender 5.0, that is `3.11`.

---

## Quick Reference

### venv

```bash
source .venv/bin/activate            # activate (mac/linux)
.venv\Scripts\Activate.ps1           # activate (windows)
pip install -r requirements.txt      # restore from requirements
pip freeze > requirements.txt        # save current state
pytest                               # run all tests
pytest -v tests/test_core.py         # run specific file, verbose
```

### Blender Extension (Cursor command palette — `Ctrl+Shift+P`)

```
Blender: Start                       # launch Blender from Cursor
Blender: Reload Addons               # force manual reload
Blender: New Addon                   # scaffold a new project
Blender: Run Script                  # run current file as a script
```

### Settings to confirm are enabled

| Setting | Value |
|---|---|
| `blender.addon.reloadOnSave` | enabled |
| `python.defaultInterpreterPath` | `./.venv/bin/python` |

---

*Questions? Check the Blender Development extension README or the bpy PyPI page for version compatibility notes.*
