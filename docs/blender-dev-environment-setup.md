# Blender + Cursor — Python Development Environment Setup

**Audience:** Developers with mid-level Python and Blender experience who want to understand how this project is structured, why it was built this way, and how to work within it day-to-day.

---

## Table of Contents

1. [The Problem This Solves](#1-the-problem-this-solves)
2. [The Two-Environment Strategy](#2-the-two-environment-strategy)
3. [The Architecture Rule That Makes It Work](#3-the-architecture-rule-that-makes-it-work)
4. [Scaling the Architecture: core/ and scene/ Packages](#4-scaling-the-architecture-core-and-scene-packages)
5. [Project File Structure](#5-project-file-structure)
6. [The Python Virtual Environment (venv)](#6-the-python-virtual-environment-venv)
7. [The Blender Development Extension](#7-the-blender-development-extension)
8. [The Blender Extension Manifest](#8-the-blender-extension-manifest)
9. [Cursor Rules](#9-cursor-rules)
10. [Testing Strategy](#10-testing-strategy)
11. [GitHub Actions CI Pipeline](#11-github-actions-ci-pipeline)
12. [Day-to-Day Development Workflow](#12-day-to-day-development-workflow)
13. [Keeping Both Environments Healthy](#13-keeping-both-environments-healthy)
14. [Quick Reference](#14-quick-reference)

---

## 1. The Problem This Solves

Blender bundles its own Python interpreter. It does not use your system Python. This creates three compounding problems for anyone who wants to develop Blender addons professionally:

1. **Autocomplete breaks.** Your IDE cannot see the `bpy` API because `bpy` only exists inside Blender's interpreter, not the Python your editor is using.
2. **You cannot run tests without opening Blender.** There is no way to run `pytest` against code that `import bpy` unless Blender's Python is somehow available outside of Blender.
3. **CI/CD is impractical.** Running tests in GitHub Actions would require installing a full Blender binary, which is hundreds of megabytes and was not designed to run headlessly in containers.

The traditional workaround was to add environment guards — checking if `bpy` is available and swapping to fake objects if it isn't. This is messy, error-prone, and means your test code doesn't actually test what runs in Blender.

This setup eliminates all three problems cleanly.

---

## 2. The Two-Environment Strategy

The core insight is that Blender publishes its Python API (`bpy`) as a regular pip package on PyPI. This means you can install `bpy` into a standard Python virtual environment and `import bpy` works the same way in your IDE, in pytest, and in GitHub Actions — because it's literally the same package.

This gives us two parallel environments that share the same source code:

| Aspect | venv + pytest | Blender (via extension) |
|---|---|---|
| Python source | `bpy` pip package | Blender's bundled Python |
| Autocomplete | `fake-bpy-module` type stubs | Native Blender Python |
| Test runner | `pytest` directly | Visual / operator output |
| Feedback loop | Terminal output | Live Blender viewport |
| Used for | Unit tests, logic verification, CI | Visual/interactive development |
| Requires Blender open? | No | Yes |
| Code changes needed to switch? | None | None |

These are not competing environments — you use both all the time. They serve different purposes.

The **venv** is always on. Cursor uses it for autocomplete and linting the moment you open the project. You run `pytest` in it for fast logic verification. GHA uses it for CI.

The **Blender extension** is used when you need to see something in a viewport, test a UI interaction, or exercise code paths that require real Blender rendering behavior.

---

## 3. The Architecture Rule That Makes It Work

The reason the two environments can share the same code without any environment flags is a strict layering rule:

```
core.py        ← Pure Python. Business logic. Minimal bpy usage.
operators.py   ← Thin Blender layer. Calls into core.py. No logic here.
```

`core.py` contains all the actual work — mesh calculations, shape key math, data transformations, etc. The rule is to use `bpy` in `core.py` only when there is no other way. Pure Python math, data structures, and algorithms live here and are trivially testable with pytest.

`operators.py` is just a thin adapter. Operators receive a Blender `context`, extract what they need, call into `core.py`, and report back. The operators themselves are almost impossible to test without Blender — but they contain so little logic that there is almost nothing to test. All the logic that matters is in `core.py`.

This is not a novel pattern — it is a variant of the hexagonal architecture / ports-and-adapters pattern applied to Blender development.

**If you find yourself writing complex logic inside an operator's `execute()` method, stop and move it to `core.py`.** The thicker the operator layer, the less testable your code is.

---

## 4. Scaling the Architecture: core/ and scene/ Packages

The starter scaffold uses a single `core.py` file. This works fine early on, but as the project grows two problems emerge:

1. `core.py` starts doing two distinct jobs: pure Python math/data logic, and direct Blender scene manipulation via `bpy`. These have very different testability characteristics and should not be mixed.
2. A single flat file becomes hard to navigate once it holds more than a few hundred lines.

The solution is to promote `core.py` into a sub-package and add a parallel `scene/` sub-package for anything that needs to act directly on a live Blender scene.

This architecture is encoded in the project's Cursor rule (`project-context.mdc`), so the AI will automatically route new code to the correct layer when you ask it to add features. You do not need to specify "put this in core/" or "put this in scene/" — the rule does that for you.

### The Expanded Structure

```
synth_head/
  __init__.py
  operators.py

  core/                        ← was core.py, now a package
    __init__.py                ← re-exports public API for backward compatibility
    math.py                    ← pure Python: clamp, lerp, remap, interpolation
    shapes.py                  ← pure Python: shape key weight calculations
    ethnicity.py               ← pure Python: ethnicity blend math and data

  scene/                       ← bpy-heavy: operates directly on a live Blender scene
    __init__.py
    mesh.py                    ← reads/writes mesh data via bpy
    shapekeys.py               ← drives shape key values on a real bpy Object
    materials.py               ← assigns materials, sets node properties
```

### The Dependency Rule

Arrows only point in one direction — downward:

```
operators.py
    ↓ calls
scene/shapekeys.py     (needs bpy — manipulates a real Blender object)
    ↓ calls
core/shapes.py         (pure Python — calculates the target weight values)
    ↓ calls
core/math.py           (pure Python — lerp, clamp, remap primitives)
```

`core/` never imports from `scene/`. `scene/` never imports from `operators.py`. This keeps the pure Python layer fully isolated and testable with no Blender session required.

### What Goes Where

| Code type | Goes in | Testable with pytest? |
|---|---|---|
| Math primitives (clamp, lerp, remap) | `core/math.py` | Yes |
| Shape key weight calculations | `core/shapes.py` | Yes |
| Reading/parsing data files | `core/` | Yes |
| Any pure Python algorithm | `core/` | Yes |
| Writing shape key values to a `bpy.types.Object` | `scene/shapekeys.py` | No — needs live Blender |
| Modifying mesh topology | `scene/mesh.py` | No — needs live Blender |
| Assigning materials or node values | `scene/materials.py` | No — needs live Blender |
| Operator `execute()` methods | `operators.py` | No — needs live Blender |

A practical rule: if a function takes a `bpy.types.Object`, `bpy.types.Mesh`, or any other `bpy.types.*` as an argument, it belongs in `scene/`. If it takes only plain Python types (floats, dicts, lists, strings), it belongs in `core/`.

### Concrete Example

```python
# core/shapes.py — pure Python, fully testable
def blend_shape_weights(base: dict, target: dict, t: float) -> dict:
    """Linearly interpolate between two shape key weight dicts."""
    return {k: base[k] + (target[k] - base[k]) * t for k in base}
```

```python
# core/math.py — pure Python, fully testable
def lerp(a: float, b: float, t: float) -> float:
    return a + (b - a) * t

def clamp(value: float, low: float = 0.0, high: float = 1.0) -> float:
    return max(low, min(high, value))
```

```python
# scene/shapekeys.py — bpy-dependent, tested interactively in live Blender
import bpy
from synth_head.core import shapes

def apply_shape_blend(obj: bpy.types.Object, base: dict, target: dict, t: float) -> None:
    weights = shapes.blend_shape_weights(base, target, t)
    key_blocks = obj.data.shape_keys.key_blocks
    for key_name, value in weights.items():
        key_blocks[key_name].value = value
```

```python
# operators.py — thin adapter, tested interactively in live Blender
from synth_head.scene import shapekeys

class SYNTHHEAD_OT_blend(bpy.types.Operator):
    bl_idname = "synth_head.blend"
    bl_label = "Synth Head: Blend Shapes"
    bl_options = {"REGISTER", "UNDO"}

    t: bpy.props.FloatProperty(name="Blend", min=0.0, max=1.0)

    def execute(self, context):
        shapekeys.apply_shape_blend(context.object, base, target, self.t)
        return {"FINISHED"}
```

Notice that `apply_shape_blend` in `scene/shapekeys.py` calls `shapes.blend_shape_weights` in `core/shapes.py`. The bpy-facing code delegates to the pure Python code for the actual calculation. The calculation is now fully testable without Blender.

### Converting core.py to a Package

When you are ready to make this change, the migration is backward compatible:

1. Create `core/` folder with `__init__.py`
2. Move the contents of `core.py` into the appropriate modules inside `core/`
3. Re-export from `core/__init__.py` so existing imports do not break:

```python
# core/__init__.py — re-exports for backward compatibility
from .math import clamp, lerp
from .shapes import blend_shape_weights
```

Code elsewhere that was doing `from synth_head import core; core.clamp(...)` continues to work unchanged.

4. Update `__init__.py` at the package root to add reload lines for the new submodules:

```python
if "bpy" in locals():
    importlib.reload(core.math)
    importlib.reload(core.shapes)
    importlib.reload(scene.shapekeys)
    importlib.reload(operators)
```

5. Add `tests/test_shapes.py`, `tests/test_math.py` etc. alongside the new modules — the test structure mirrors the `core/` structure.

### When to Make This Split

Do not split prematurely. The starter scaffold (`core.py`, `operators.py`) is correct for early development. Make the split when either:

- `core.py` has grown past ~150–200 lines and navigation is becoming slow, **or**
- You are about to write a function that needs to call `bpy` to access a live scene object — that is the moment to create `scene/` rather than putting it in `core.py`

The Cursor rule (`project-context.mdc`) is already written for the scaled `core/` / `scene/` structure. This means the AI will follow the three-layer pattern and use the correct placement rule from the very first time you ask it to generate code — even before you have physically created the `core/` and `scene/` folders. The rule is future-proof: it describes where things belong, and the AI will create the folders as needed when it writes code.

---

## 5. Project File Structure

```
HeadGen/
  synth_head/                      ← the Blender addon package
    __init__.py                    ← entry point Blender loads
    core.py                        ← pure Python business logic
    operators.py                   ← thin Blender operator layer
    blender_manifest.toml          ← Blender 5.0+ extension manifest
    tests/
      __init__.py                  ← makes tests/ a Python package
      test_core.py                 ← pytest tests against core.py

  data/                            ← reference data files
    headOnly_geo_data.txt
    headOnly_geo_shapekeys.txt

  docs/                            ← you are here
  plan/                            ← planning and onboarding notes

  .venv/                           ← virtual environment (NOT committed to git)
  requirements.txt                 ← package list (committed to git)
  pyproject.toml                   ← pytest configuration
  .gitignore
  .vscode/settings.json            ← editor settings (Cursor/VS Code)
  .github/workflows/test.yml       ← GitHub Actions CI workflow
  .cursor/rules/
    project-context.mdc            ← always-on project context for Cursor AI
    blender-python.mdc             ← Blender naming conventions for Cursor AI
```

### Why the addon is a folder package, not a single file

Blender supports both single-file addons (`my_addon.py`) and folder-based packages (`my_addon/__init__.py`). We use the folder package form because:

- It allows splitting logic into multiple modules (`core.py`, `operators.py`, etc.)
- It is required for the `blender_manifest.toml` extension format
- It is required for proper `importlib.reload()` support
- It is required for pytest to import the package cleanly via `pythonpath = ["."]`

---

## 6. The Python Virtual Environment (venv)

### What it is

A virtual environment is an isolated Python sandbox that lives in your project folder (`.venv/`). It has its own `python` binary and its own set of installed packages, independent of your system Python. This prevents package conflicts between projects.

### Why we need Python 3.11 specifically

The `bpy` pip package is tied to a specific Python version — Blender 5.0 bundles Python 3.11. If you try to install `bpy==5.0.x` into a Python 3.12 or 3.13 environment, the installation will fail because there are no compatible compiled wheels. You must use Python 3.11.

### The packages

```
bpy==5.0.1          ← Blender's Python API as a pip package
fake-bpy-module-5.0 ← Type stubs that give Cursor autocomplete for the bpy API
pytest              ← Test runner
```

- **`bpy`** is the real deal — it gives you working `import bpy` in pytest. It is not a mock. You can actually call bpy functions in tests.
- **`fake-bpy-module`** is separate from `bpy`. It provides `.pyi` type stub files that IDEs read for autocomplete hints. Without it, Cursor does not know the signatures of `bpy.types.Operator` and similar. With it, you get full autocomplete.
- **`pytest`** is the standard Python test runner. No Blender-specific plugins needed.

### Initial setup (one time per machine / per project)

```bash
# Create the venv using Python 3.11 specifically
python3.11 -m venv .venv        # mac / linux
py -3.11 -m venv .venv          # windows

# Activate it
source .venv/bin/activate       # mac / linux
.venv\Scripts\Activate.ps1      # windows powershell

# Install packages
pip install -r requirements.txt

# Point Cursor at it
# Command palette → Python: Select Interpreter → choose .venv
```

### `requirements.txt`

This file is the committed record of exactly which packages are installed. It is generated from the live venv state:

```bash
pip freeze > requirements.txt
```

Anyone cloning the repo can recreate the exact same environment with:

```bash
pip install -r requirements.txt
```

### `.venv/` is not committed to git

The `.venv/` folder can be hundreds of megabytes, contains compiled binaries that are OS-specific, and can be recreated from `requirements.txt` in seconds. It is excluded via `.gitignore`. Never commit it.

### `pyproject.toml`

This file configures pytest for this project:

```toml
[tool.pytest.ini_options]
testpaths = ["synth_head/tests"]
pythonpath = ["."]
```

- `testpaths` tells pytest where to look for tests so you can just run `pytest` without specifying a path.
- `pythonpath = ["."]` adds the project root to Python's import path, which is what makes `from synth_head import core` work in tests without installing the package.

---

## 7. The Blender Development Extension

The **Blender Development** extension (by Jacques Lucke, `JacquesLucke.blender-development`) is the bridge between Cursor and a live running Blender session.

### What it does

- Launches Blender from the Cursor command palette
- Creates a symlink from your project folder into Blender's addon directory, so Blender always reads your live source files directly — no copy/paste, no manual install
- Reloads your addon in the running Blender instance every time you save a file in Cursor
- Pipes Blender's terminal output (print statements, errors, tracebacks) into the Cursor terminal panel
- Connects Cursor's debugger to the running Blender Python interpreter, allowing breakpoints

### The reload-on-save loop

With `blender.addon.reloadOnSave` enabled:

1. Edit a `.py` file in Cursor
2. Hit `Ctrl+S`
3. Blender reloads your addon in under a second
4. Test visually in the Blender viewport

This is fast enough to treat as a live preview loop.

### `importlib.reload()` boilerplate

When Python loads a module, it caches it in `sys.modules`. If you reload an addon, Python sees the cached version and does not re-execute the module files. This means changes to `core.py` might not appear even after a reload.

The fix is the reload pattern in `__init__.py`:

```python
import importlib

if "bpy" in locals():
    importlib.reload(core)
    importlib.reload(operators)

import bpy
from . import core, operators
```

The `if "bpy" in locals()` guard is true only on a reload (not on initial load), so it only re-executes the module files when the addon is being reloaded by Blender. Add one `importlib.reload()` line per submodule.

### Isolating from your personal Blender profile

Without isolation, the development symlink appears inside `~/.config/blender/` (or the equivalent on your OS) alongside your personal addons. The `BLENDER_USER_RESOURCES` setting redirects Blender to use a local folder instead:

```json
"blender.environmentVariables": {
  "BLENDER_USER_RESOURCES": "${workspaceFolder}/blender_vscode_development"
}
```

The `blender_vscode_development/` folder is automatically created by the extension and is listed in `.gitignore`. It is safe to delete at any time.

### Breakpoint debugging

1. Launch Blender via **Blender: Start** (not by double-clicking Blender directly)
2. Click the gutter next to any line number in Cursor to set a breakpoint
3. Trigger the relevant operator in Blender
4. Cursor pauses at the breakpoint with full variable inspection

This only works when Blender was launched via the extension. A Blender instance opened independently has no debugger connection.

---

## 8. The Blender Extension Manifest

Blender 4.2 introduced a new extension format that replaces the old `bl_info` dict. Both exist in this project for backward compatibility.

### `blender_manifest.toml`

```toml
schema_version = "1.0.0"

id = "synth_head"
version = "0.1.0"
name = "Synth Head"
tagline = "Procedural head generation with shape key control"
maintainer = "Genies"
type = "add-on"

blender_version_min = "5.0.0"

license = ["SPDX:GPL-3.0-or-later"]
```

This file must live inside the addon package folder (alongside `__init__.py`). The `id` must match the Python package name. The `blender_version_min` gates which Blender versions can install this addon.

### `bl_info` in `__init__.py`

The `bl_info` dictionary is the older format still read by Blender 2.x–4.1 and by the Blender Development extension. Keeping both ensures compatibility with the development tooling even as the project targets Blender 5.0+.

---

## 9. Cursor Rules

Cursor rules are markdown files stored in `.cursor/rules/` that are injected into the AI context when you ask Cursor to help with code. They persist across sessions and let you establish conventions once rather than re-explaining them every time.

### `project-context.mdc` — always on

`alwaysApply: true` means this rule is included in every AI conversation in this workspace. It contains:

- The full project layout and what each file and folder is for
- The three-layer architecture: `operators.py → scene/ → core/`
- The placement rule: plain Python types → `core/`, `bpy.types.*` arguments → `scene/`
- Import rules (no environment guards, `import bpy` must work everywhere)
- Testing conventions for each layer

**This rule is the single source of truth that keeps the AI writing code in the right place.** When you ask Cursor to add a feature, it reads this rule before responding and will route new code to the correct layer automatically — without you needing to specify it each time.

If you ever find the AI putting scene-manipulation code in `core/` or putting logic in an operator, check that the rule file is intact and the `.venv` interpreter is selected. If the AI drifts despite the rule, a quick correction like "this touches a live Blender object, put it in `scene/`" is enough to redirect it, and the rule will keep it on track for the rest of the session.

### `blender-python.mdc` — file-scoped

`globs: synth_head/**/*.py` means this rule is only included when you are working on files inside the addon. It contains Blender-specific naming conventions:

- Operator class names: `SYNTHHEAD_OT_<name>`
- Panel class names: `SYNTHHEAD_PT_<name>`
- Property group names: `SYNTHHEAD_PG_<name>`
- `bl_idname` format: `"synth_head.<snake_case>"`

These naming conventions are enforced by Blender itself — using non-conforming names causes Blender to refuse to register the class.

### What the rules enforce vs. what they don't

Rules are persistent guidance injected into the AI context — they are not a compiler or a linter. They reliably keep the AI on pattern for:

- Naming conventions (enforced by `blender-python.mdc`)
- Layer routing — where new code is placed (`core/` vs `scene/` vs `operators.py`)
- `CLASSES` list maintenance
- `importlib.reload()` for new modules

They do not catch everything. If you give an ambiguous instruction the AI may still drift. The rules reduce that significantly, but a short correction in the conversation is always sufficient to get back on track.

### Updating the rules as the project grows

The rules live in `.cursor/rules/` and are plain markdown — edit them like any other file. When you add a new major subsystem, update `project-context.mdc` to document it. The AI will incorporate it from the next conversation onward.

---

## 10. Testing Strategy

### What we test

Tests live in `synth_head/tests/`. Currently they test:

- `core.py` functions directly (no Blender needed)
- That `bpy` is importable (verifies the venv is configured correctly)

### What we do not test with pytest

- Operator behavior (requires a Blender context)
- Viewport changes (requires rendering)
- UI interactions (requires the Blender UI)

These are verified manually using the Blender Development extension.

### Running tests

```bash
pytest                              # run everything in synth_head/tests/
pytest -v                           # verbose — shows each test name and result
pytest synth_head/tests/test_core.py  # run one specific file
```

Tests run against the `bpy` pip package — no Blender window, no GUI, sub-second execution. This is fast enough to run constantly during development.

### Test file structure

```python
# synth_head/tests/test_core.py
from synth_head import core

def test_clamp_within_range():
    assert core.clamp(0.5) == 0.5

def test_bpy_importable():
    import bpy
    assert hasattr(bpy, "context")
```

The `test_bpy_importable` test exists specifically to verify the venv is set up correctly — if `bpy` is not installed, this test fails and you know immediately what is wrong.

---

## 11. GitHub Actions CI Pipeline

Because tests use the `bpy` pip package, the CI pipeline requires no Blender installation — just Python 3.11 and pip.

### `.github/workflows/test.yml`

```yaml
name: Tests

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - uses: actions/setup-python@v5
        with:
          python-version: "3.11"

      - name: Install dependencies
        run: pip install -r requirements.txt

      - name: Run tests
        run: pytest synth_head/tests/ -v
```

### How it works

1. On every push and pull request, GitHub spins up an Ubuntu container
2. It checks out the repo
3. It installs Python 3.11 (matching the `bpy` package requirements)
4. It runs `pip install -r requirements.txt` — this installs `bpy`, `fake-bpy-module`, and `pytest`
5. It runs `pytest` — the same tests you run locally
6. Pass/fail result is reported on the pull request

If a test passes locally but fails in GHA, the most common cause is a dependency that is installed in your local venv but not in `requirements.txt`. Always run `pip freeze > requirements.txt` after installing new packages.

---

## 12. Day-to-Day Development Workflow

### Starting a development session

1. Open the project folder in Cursor — the venv interpreter is selected automatically
2. Run **Blender: Start** from the command palette if you need visual testing
3. Write code in `core.py` (logic) and `operators.py` (Blender wiring)

### Logic development loop

1. Write a function in `core.py`
2. Write a test in `synth_head/tests/test_core.py`
3. Run `pytest` in the terminal
4. Iterate until tests pass

### Visual development loop

1. Save any `.py` file (`Ctrl+S`)
2. Blender reloads your addon automatically
3. Test in the viewport
4. Return to Cursor

### Adding a new operator

1. Define the class in `operators.py` following the naming convention:
   ```python
   class SYNTHHEAD_OT_my_operator(bpy.types.Operator):
       bl_idname = "synth_head.my_operator"
       bl_label = "My Operator"
       bl_options = {"REGISTER", "UNDO"}

       def execute(self, context):
           result = core.do_the_work(...)
           self.report({"INFO"}, f"Done: {result}")
           return {"FINISHED"}
   ```
2. Add it to the `CLASSES` list at the bottom of `operators.py`
3. Save — Blender reloads automatically

### Adding a new module

1. Create the `.py` file in `synth_head/`
2. Add it to `__init__.py`:
   ```python
   import importlib
   if "bpy" in locals():
       importlib.reload(core)
       importlib.reload(operators)
       importlib.reload(my_new_module)   # add this line

   from . import core, operators, my_new_module   # add here too
   ```

### Adding a new dependency

```bash
pip install some-package
pip freeze > requirements.txt
# commit requirements.txt
```

---

## 13. Keeping Both Environments Healthy

| Symptom | Likely cause | Fix |
|---|---|---|
| `import bpy` fails in pytest | `bpy` not installed in venv | `pip install bpy==5.0.1` |
| No `bpy` autocomplete in Cursor | `fake-bpy-module` not installed | `pip install fake-bpy-module-5.0` |
| Cursor using wrong Python | Interpreter not set | Command palette → Python: Select Interpreter → choose `.venv` |
| Blender does not reload on save | `reloadOnSave` disabled | Cursor Settings → search `blender.addon.reloadOnSave` → enable |
| Changes to `core.py` not showing in Blender | Missing `importlib.reload()` | Add `importlib.reload(core)` to `__init__.py` |
| Test passes locally, fails in GHA | Package missing from `requirements.txt` | `pip freeze > requirements.txt` and commit |
| GHA fails on `bpy` install | Wrong Python version in workflow | Confirm `python-version: "3.11"` in workflow YAML |
| `blender_vscode_development/` cluttering your git status | Not in `.gitignore` | Add `blender_vscode_development/` to `.gitignore` |

### Updating Blender version

1. Install the new Blender version
2. Determine which Python version it bundles (check Blender release notes)
3. Create a new `.venv` using that Python version
4. Update `bpy` and `fake-bpy-module` versions in `requirements.txt`
5. Update `python-version` in `.github/workflows/test.yml`
6. Update `blender_version_min` in `blender_manifest.toml`
7. Update `"blender"` tuple in `bl_info` in `__init__.py`

---

## 14. Quick Reference

### venv commands

```bash
# First-time setup
py -3.11 -m venv .venv                   # create (windows)
python3.11 -m venv .venv                 # create (mac/linux)
.venv\Scripts\Activate.ps1              # activate (windows)
source .venv/bin/activate                # activate (mac/linux)
pip install -r requirements.txt          # install packages

# Daily use
pytest                                   # run all tests
pytest -v                                # verbose
pytest synth_head/tests/test_core.py    # specific file

# After adding a package
pip install some-package
pip freeze > requirements.txt
```

### Cursor command palette (`Ctrl+Shift+P`)

```
Blender: Start              ← launch Blender and connect debugger
Blender: Reload Addons      ← force manual reload
Blender: New Addon          ← scaffold a new project
Blender: Run Script         ← run the current file as a one-off script
Python: Select Interpreter  ← point Cursor at the .venv interpreter
```

### Settings to verify

| Setting | Value |
|---|---|
| `blender.addon.reloadOnSave` | enabled |
| `python.defaultInterpreterPath` | `.venv\Scripts\python.exe` (Windows) or `.venv/bin/python` |
| `blender.environmentVariables.BLENDER_USER_RESOURCES` | `${workspaceFolder}/blender_vscode_development` |

### Blender naming conventions

| Type | Pattern | Example |
|---|---|---|
| Operator | `SYNTHHEAD_OT_<name>` | `SYNTHHEAD_OT_generate_head` |
| Panel | `SYNTHHEAD_PT_<name>` | `SYNTHHEAD_PT_controls` |
| Property group | `SYNTHHEAD_PG_<name>` | `SYNTHHEAD_PG_settings` |
| Operator ID | `"synth_head.<snake>"` | `"synth_head.generate_head"` |
