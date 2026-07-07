# Synth Head Config UI

Web editor for pipeline JSON configs with named profile switching.

## Quick start

```powershell
# From repo root
pip install -r config_ui/requirements.txt
python -m config_ui.server
```

Or use the helper script (creates venv if needed):

```powershell
.\config_ui\start.ps1
```

Open **http://127.0.0.1:8420**

No Node/npm required — the UI is static HTML + Monaco (CDN).

## Manifests (master catalogs)

Stored in `data/manifests/`. Every joint, shape, bone property, and texture channel
ever used is registered here so you can remove it from an active profile list and
add it back later from the catalog.

| Manifest | Used by |
|----------|---------|
| `joints.json` | `chaos_joints.json` → `joint_names` |
| `variation_shapes.json` | `blendshapes.json` → `variation_shapes` |
| `expression_shapes.json` | `blendshapes.json` → `expression_shapes` |
| `independent_shapes.json` | `blendshapes.json` → `independent_shapes` |
| `bone_properties.json` | `chaos_joints.json` → `bone_properties` |
| `texture_channels.json` | `texture_swap.json` → `channels` |
| `hide_collection.json` | `runner.json` → `hideCollection` |

`NeckBind` is blocked from joint activation (quality rule). Saving any config auto-registers new items into the relevant manifest.


| Path | Role |
|------|------|
| `data/profiles/<name>/` | Stored profile (full JSON set) |
| `data/profiles/active.json` | Which profile is active |
| `data/config/` | Live config Blender reads (synced from active profile) |

- **Switch profile** → copies profile JSON into `data/config/`; Blender picks up changes on the next operator run (no addon reload).
- **Save** on the active profile → writes to both the profile folder and `data/config/`.
- On first launch, `data/config/` becomes profile `default`; `data/config-auth-head/` becomes `auth-head` if present.

## Optional React build

A Vite/React version lives in `config_ui/web/` if you prefer that workflow (`npm install && npm run build` → serves from `web/dist` when present).
