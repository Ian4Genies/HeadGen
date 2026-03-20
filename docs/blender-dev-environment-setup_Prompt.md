# Prompt: Blender Addon Python Development Environment Setup

Use this prompt verbatim (or paste it into a new AI chat session) to scaffold a professional Blender addon development environment. The AI will check for current versions, adapt to the active Blender version, and create all necessary files.

---

## THE PROMPT

```
You are setting up a professional Blender addon Python development environment from scratch.
The project is called: [PROJECT_NAME]
The addon package name (Python identifier, snake_case): [ADDON_PACKAGE_NAME]
The addon display name: [ADDON_DISPLAY_NAME]
The maintainer / studio name: [MAINTAINER_NAME]
The project root folder already exists at: [PROJECT_ROOT_PATH]

Before doing anything, check the following and confirm your findings:

1. What is the latest stable Blender release version? (Check blender.org or the bpy PyPI page)
2. What Python version does that Blender release bundle? (This determines venv Python version)
3. What is the latest available `bpy` pip package version matching that Blender version?
4. What is the latest available `fake-bpy-module` pip package version matching that Blender version?
5. What is the latest stable `pytest` version?
6. What is the latest `actions/checkout` and `actions/setup-python` GitHub Actions version?

Use the most current versions you can verify. Do not hardcode versions from your training data
without checking — Blender releases regularly and the pip packages follow.

---

Once confirmed, scaffold the following complete project structure and files:

## 1. Addon Package

Create `[ADDON_PACKAGE_NAME]/` as a folder-based Python package containing:

### `[ADDON_PACKAGE_NAME]/__init__.py`
- Include `importlib.reload()` pattern at the top for all submodules
- Guard: `if "bpy" in locals():` before each reload call
- Import `bpy`, then `from . import core, operators`
- Include a `bl_info` dict with: name, author, version (0, 1, 0), blender version tuple,
  location, description, category
- Define `classes = operators.CLASSES`
- Define `register()` — iterate `classes`, call `bpy.utils.register_class(cls)`
- Define `unregister()` — iterate `reversed(classes)`, call `bpy.utils.unregister_class(cls)`

### `[ADDON_PACKAGE_NAME]/core.py`
- Module docstring explaining this is pure Python logic, minimal bpy, testable with plain pytest
- Add one example utility function `clamp(value, low=0.0, high=1.0) -> float` as a starter

### `[ADDON_PACKAGE_NAME]/operators.py`
- Module docstring explaining this is the thin Blender operator layer that delegates to core
- Import `bpy` and `from . import core`
- Define one smoke-test operator class `[PREFIX]_OT_hello` (use SCREAMING_SNAKE prefix derived
  from the addon package name, e.g. package `synth_head` → prefix `SYNTHHEAD`)
  - `bl_idname = "[addon_package_name].hello"`
  - `bl_label = "[Addon Display Name]: Hello"`
  - `bl_options = {"REGISTER"}`
  - `execute()` calls `self.report({"INFO"}, "addon is loaded and working.")` and returns `{"FINISHED"}`
- Define `CLASSES = [<hello operator class>]` at the bottom

### `[ADDON_PACKAGE_NAME]/blender_manifest.toml`
- `schema_version = "1.0.0"`
- `id` = addon package name
- `version = "0.1.0"`
- `name` = addon display name
- `tagline` = one-line description
- `maintainer` = maintainer name
- `type = "add-on"`
- `blender_version_min` = the current Blender version you verified (as a string "X.Y.Z")
- `license = ["SPDX:GPL-3.0-or-later"]`

### `[ADDON_PACKAGE_NAME]/tests/__init__.py`
- Empty file (makes the folder a Python package so pytest can import from it)

### `[ADDON_PACKAGE_NAME]/tests/test_core.py`
- Module docstring: "Starter tests for [addon_package_name].core — validates the dev environment works."
- Import `from [addon_package_name] import core`
- Test: `test_clamp_within_range` — asserts `core.clamp(0.5) == 0.5`
- Test: `test_clamp_below` — asserts `core.clamp(-1.0) == 0.0`
- Test: `test_clamp_above` — asserts `core.clamp(2.0) == 1.0`
- Test: `test_bpy_importable` — imports `bpy`, asserts `hasattr(bpy, "context")`

---

## 1b. Scaled Architecture: core/ and scene/ Sub-Packages (Optional Expansion)

Include this section in your explanation to the developer as guidance for when and how
to expand beyond the starter flat-file structure.

When the project grows, the single `core.py` file should be promoted to two sub-packages
that segregate pure Python from bpy-dependent scene code. Explain the following to the developer:

### When to make this split

The developer should make this change when either condition is met:
- `core.py` exceeds ~150–200 lines and is becoming hard to navigate, OR
- They need to write code that takes a `bpy.types.Object` or other live Blender type as an
  argument — that code belongs in `scene/`, not `core/`

### The target structure

```
[ADDON_PACKAGE_NAME]/
  __init__.py
  operators.py

  core/
    __init__.py          ← re-exports public API for backward compatibility
    math.py              ← pure Python: clamp, lerp, remap, interpolation
    shapes.py            ← pure Python: shape key weight calculations
    [domain].py          ← one file per logical domain of pure Python logic

  scene/
    __init__.py
    mesh.py              ← reads/writes mesh data via bpy
    shapekeys.py         ← drives shape key values on a real bpy Object
    [domain].py          ← one file per logical domain of bpy scene operations
```

### The dependency rule (enforce strictly)

Arrows point downward only — never upward or sideways:

```
operators.py  →  scene/  →  core/
```

- `core/` NEVER imports from `scene/`
- `scene/` NEVER imports from `operators.py`
- `operators.py` imports from `scene/` (and optionally `core/` for pure utilities)
- If a function takes only plain Python types (float, dict, list, str), it belongs in `core/`
- If a function takes a `bpy.types.*` argument, it belongs in `scene/`

### Migration steps (backward compatible)

1. Create `core/__init__.py` and re-export existing public symbols:
   ```python
   from .math import clamp
   ```
   Existing code that does `from [addon_package_name] import core; core.clamp(...)` continues
   to work unchanged.

2. Create `scene/__init__.py` (empty is fine to start).

3. Update the top of `[ADDON_PACKAGE_NAME]/__init__.py` to reload sub-modules:
   ```python
   if "bpy" in locals():
       importlib.reload(core.math)
       importlib.reload(core.shapes)
       importlib.reload(scene.shapekeys)
       importlib.reload(operators)
   ```

4. Add corresponding test files: `tests/test_math.py`, `tests/test_shapes.py`, etc.
   The test folder structure should mirror the `core/` structure.

### What gets tested where

| Code | Location | Testable with pytest? |
|---|---|---|
| Math primitives, algorithms, data transforms | `core/` | Yes — no Blender needed |
| Functions taking `bpy.types.*` arguments | `scene/` | No — needs live Blender |
| Operator `execute()` methods | `operators.py` | No — needs live Blender |

Do NOT scaffold this structure automatically on the initial setup — start flat.
Only scaffold it if the developer explicitly requests the scaled structure or if the
project brief clearly indicates significant complexity from the outset.

---

## 2. Project Configuration Files

### `requirements.txt`
List the three packages with their verified versions:
```
bpy==[verified version]
fake-bpy-module-[verified version]
pytest
```
Note: pin bpy and fake-bpy-module to the exact verified versions. Leave pytest unpinned
or pin to latest stable.

### `pyproject.toml`
```toml
[tool.pytest.ini_options]
testpaths = ["[ADDON_PACKAGE_NAME]/tests"]
pythonpath = ["."]
```

### `.gitignore`
Include:
- `.venv/`
- `__pycache__/`
- `*.pyc`
- `*.pyo`
- `*.egg-info/`
- `dist/`
- `build/`
- `blender_vscode_development/`
- `.vscode/` with exception `!.vscode/settings.json`
- `Thumbs.db`, `Desktop.ini`, `.DS_Store`

### `.vscode/settings.json`
```json
{
    "python.defaultInterpreterPath": ".venv\\Scripts\\python.exe",
    "python.analysis.extraPaths": ["${workspaceFolder}"],
    "blender.addon.reloadOnSave": true,
    "blender.environmentVariables": {
        "BLENDER_USER_RESOURCES": "${workspaceFolder}/blender_vscode_development"
    }
}
```
Note: use `.venv/bin/python` for the interpreter path on Mac/Linux. Mention both variants
in a comment above the setting so the developer can switch.

---

## 3. GitHub Actions CI Workflow

### `.github/workflows/test.yml`
```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@[latest verified version]

      - uses: actions/setup-python@[latest verified version]
        with:
          python-version: "[Python version bundled by the verified Blender release]"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run tests
        run: pytest [ADDON_PACKAGE_NAME]/tests/ -v
```

---

## 4. Cursor AI Rules

### `.cursor/rules/project-context.mdc`
```markdown
---
description: [Addon Display Name] Blender addon project structure and development conventions
alwaysApply: true
---

# [Addon Display Name] — Blender [version] Addon

## Project Layout

- `[addon_package_name]/` — the addon package Blender loads
  - `__init__.py` — entry point with register/unregister and importlib reload pattern
  - `core.py` — pure Python logic, minimal bpy usage, tested with pytest
  - `operators.py` — thin Blender operator layer, delegates to core
  - `blender_manifest.toml` — Blender [version]+ extension manifest
  - `tests/` — pytest tests that run against the bpy pip package (headless, no Blender UI)
- `requirements.txt` — venv dependencies (bpy, fake-bpy-module, pytest)
- `pyproject.toml` — pytest configuration
- `.venv/` — Python [python version] virtual environment (not committed)

## Architecture Rules

- Keep `operators.py` as thin as possible; push logic into `core.py`.
- Never add environment guards or conditional imports to switch between venv and Blender.
- `import bpy` should work identically in pytest (via pip bpy) and in live Blender.
- New operator classes go in `operators.py` and must be added to the `CLASSES` list.
- Each new module must get an `importlib.reload()` line in `__init__.py`.

## Testing

- Tests run via `pytest` from the repo root against the bpy pip package.
- GHA runs the same pytest suite on Python [python version] / ubuntu-latest.
- Visual/interactive testing uses the Blender Development extension (Blender: Start).
```

### `.cursor/rules/blender-python.mdc`
```markdown
---
description: Blender Python API conventions for addon code
globs: [addon_package_name]/**/*.py
alwaysApply: false
---

# Blender Python Conventions

- Operator class names: `[PREFIX]_OT_<name>` (Blender naming convention)
- Panel class names: `[PREFIX]_PT_<name>`
- Property group names: `[PREFIX]_PG_<name>`
- Use `bl_idname = "[addon_package_name].<snake_case>"` for operator IDs.
- Always include `bl_label` and `bl_options` on operators.
- Register/unregister via the `CLASSES` list in `operators.py`, iterated in `__init__.py`.
- Prefer `context.object` over `bpy.context.object` inside operators.
```

Where `[PREFIX]` is the SCREAMING_SNAKE version of the addon package name
(e.g. `synth_head` → `SYNTHHEAD`, `my_tool` → `MYTOOL`).

---

## 5. Post-Scaffold Instructions to Provide to the Developer

After creating all files, output the following setup instructions:

---

### One-time environment setup (run these in order)

**Step 1 — Create the virtual environment using Python [verified Python version]:**
```bash
# Windows
py -[X.Y] -m venv .venv

# Mac / Linux
python[X.Y] -m venv .venv
```

**Step 2 — Activate the venv:**
```bash
# Windows (PowerShell)
.venv\Scripts\Activate.ps1

# Mac / Linux
source .venv/bin/activate
```

**Step 3 — Install dependencies:**
```bash
pip install -r requirements.txt
```

**Step 4 — Point Cursor at the venv:**
Command palette (`Ctrl+Shift+P`) → `Python: Select Interpreter` → select `.venv`

**Step 5 — Install the Blender Development extension:**
Extensions panel (`Ctrl+Shift+X`) → search `JacquesLucke.blender-development` → Install

**Step 6 — Verify the environment works:**
```bash
pytest
```
All 4 starter tests should pass. If `test_bpy_importable` fails, `bpy` is not installed
correctly in the venv.

**Step 7 — Launch Blender from Cursor (for interactive development):**
Command palette → `Blender: Start` → locate Blender executable when prompted

---

End of setup instructions.
```

---

## USAGE NOTES

**Before using this prompt:**
- Replace all `[PLACEHOLDERS]` with your actual project values.
- The AI will verify package versions at the time of use, so the resulting `requirements.txt` will reflect current versions, not the versions current when this prompt was written.

**Variables to replace:**

| Placeholder | Example |
|---|---|
| `[PROJECT_NAME]` | `HeadGen` |
| `[ADDON_PACKAGE_NAME]` | `synth_head` |
| `[ADDON_DISPLAY_NAME]` | `Synth Head` |
| `[MAINTAINER_NAME]` | `Genies` |
| `[PROJECT_ROOT_PATH]` | `C:\Genies\01_Repo\02_Blender\HeadGen` |
| `[PREFIX]` | Auto-derived from package name by AI |

**What the AI will produce:**
- A complete folder and file structure ready to develop in
- Version-verified `requirements.txt` for the current Blender release
- A working GitHub Actions CI pipeline
- Cursor AI rules that persist project conventions across sessions
- Step-by-step setup instructions for the developer

**What you still need to do manually after running this prompt:**
1. Run the venv setup commands the AI outputs
2. Install the Blender Development extension in Cursor
3. Run `pytest` to verify the environment is working
4. Initialize a git repo (`git init`, `git add .`, `git commit`)
