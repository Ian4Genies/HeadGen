/** Catalog-backed list editor — active items + manifest pool. */

async function fetchManifest(id) {
  const res = await fetch(`/api/manifests/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function registerManifest(id, ids, note = "") {
  await fetch(`/api/manifests/${encodeURIComponent(id)}/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids, note }),
  });
}

function el(tag, cls = "", text = "") {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text) n.textContent = text;
  return n;
}

export async function mountManifestList({
  manifestId,
  activeItems,
  onChange,
  allowCustom = true,
  itemLabel = "item",
}) {
  const root = el("div", "manifest-list");
  let manifest = await fetchManifest(manifestId);
  let active = [...activeItems];

  const sync = (next) => {
    active = next;
    onChange([...active]);
    render();
  };

  const render = () => {
    root.innerHTML = "";
    const blocked = new Set(manifest.blocked ?? []);
    const catalogIds = manifest.items.map((i) => i.id);
    const inactive = catalogIds.filter((id) => !active.includes(id) && !blocked.has(id));

    root.appendChild(el("p", "manifest-subtitle", `Active ${itemLabel}s (${active.length})`));
    const activeBox = el("div", "chips active-chips");
    if (!active.length) {
      activeBox.appendChild(el("span", "muted small", "None selected"));
    }
    for (const id of active) {
      const chip = el("span", "chip active-chip mono", id);
      const rm = el("button", "chip-x", "×");
      rm.type = "button";
      rm.title = "Remove from active list (stays in catalog)";
      rm.onclick = () => sync(active.filter((x) => x !== id));
      chip.appendChild(rm);
      activeBox.appendChild(chip);
    }
    root.appendChild(activeBox);

    root.appendChild(el("p", "manifest-subtitle", "Catalog — click to activate"));
    const search = el("input", "input search");
    search.placeholder = `Search catalog… (${inactive.length} available)`;
    root.appendChild(search);

    const pool = el("div", "chips catalog-chips");
    const drawPool = (q = "") => {
      pool.innerHTML = "";
      const filtered = inactive.filter((id) => id.toLowerCase().includes(q.toLowerCase()));
      if (!filtered.length) {
        pool.appendChild(el("span", "muted small", "No matches"));
        return;
      }
      for (const id of filtered) {
        const btn = el("button", "chip catalog-chip mono", `+ ${id}`);
        btn.type = "button";
        btn.onclick = () => sync([...active, id]);
        pool.appendChild(btn);
      }
    };
    search.oninput = () => drawPool(search.value.trim());
    drawPool();
    root.appendChild(pool);

    if (blocked.size) {
      root.appendChild(el("p", "manifest-subtitle blocked-title", "Blocked from activation"));
      const blockedBox = el("div", "chips");
      for (const id of [...blocked].sort()) {
        blockedBox.appendChild(el("span", "chip blocked-chip mono", id));
      }
      root.appendChild(blockedBox);
    }

    if (allowCustom) {
      const addRow = el("div", "add-row");
      const inp = el("input", "input");
      inp.placeholder = `Register new ${itemLabel}…`;
      const btn = el("button", "btn ghost", "Register & add");
      btn.type = "button";
      btn.onclick = async () => {
        const id = inp.value.trim();
        if (!id || blocked.has(id)) return;
        await registerManifest(manifestId, [id]);
        manifest = await fetchManifest(manifestId);
        if (!active.includes(id)) sync([...active, id]);
        else render();
        inp.value = "";
      };
      addRow.append(inp, btn);
      root.appendChild(addRow);
    }
  };

  render();
  return root;
}

function mirrorJointParam(key) {
  const parts = key.split(".");
  if (parts.length < 2) return null;
  const joint = parts[0];
  if (joint.startsWith("Left")) return ["Right" + joint.slice(4), ...parts.slice(1)].join(".");
  return null;
}

function isRedundantMirrorTarget(key, active) {
  const parts = key.split(".");
  if (parts.length < 2 || !parts[0].startsWith("Right")) return false;
  const left = ["Left" + parts[0].slice(5), ...parts.slice(1)].join(".");
  return active.includes(left);
}

export async function mountRegistryPicker({ profile, activeItems, onChange }) {
  const root = el("div", "manifest-list");
  let active = [...activeItems];
  let filterText = "";
  let registry = { rerandomize_suggestions: [] };
  try {
    const res = await fetch(`/api/profiles/${encodeURIComponent(profile)}/registry`);
    if (res.ok) registry = await res.json();
  } catch {
    /* fallback to string list */
  }

  const suggestions = registry.rerandomize_suggestions ?? [];

  root.appendChild(
    el(
      "p",
      "chip-hint",
      "Left* joint flat keys mirror to Right* automatically (scale identical; location X and rotation Y/Z negated).",
    ),
  );
  const subtitle = el("p", "manifest-subtitle", "");
  root.appendChild(subtitle);
  const activeBox = el("div", "chips active-chips");
  root.appendChild(activeBox);

  const search = el("input", "input search");
  search.placeholder = "Search params, shapes, properties…";
  root.appendChild(search);

  const pool = el("div", "chips catalog-chips");
  root.appendChild(pool);

  const addRow = el("div", "add-row");
  const customInp = el("input", "input mono");
  customInp.placeholder = "Custom target (supports wildcards)";
  const addBtn = el("button", "btn ghost", "Add");
  addBtn.type = "button";
  addRow.append(customInp, addBtn);
  root.appendChild(addRow);

  const drawPool = () => {
    pool.innerHTML = "";
    const q = filterText.trim().toLowerCase();
    const inactive = suggestions.filter((s) => !active.includes(s));
    const filtered = inactive.filter((s) => s.toLowerCase().includes(q));
    if (!filtered.length) {
      pool.appendChild(el("span", "muted small", q ? "No matches" : "All suggestions active"));
      return;
    }
    for (const s of filtered.slice(0, 120)) {
      const btn = el("button", "chip catalog-chip mono", `+ ${s}`);
      btn.type = "button";
      btn.onclick = () => {
        const mirror = mirrorJointParam(s);
        let next = [...active, s];
        if (mirror) next = next.filter((x) => x !== mirror);
        sync(next);
      };
      pool.appendChild(btn);
    }
  };

  const renderActive = () => {
    subtitle.textContent = `Active targets (${active.length})`;
    activeBox.innerHTML = "";
    for (const id of active) {
      const chip = el("span", "chip active-chip mono" + (isRedundantMirrorTarget(id, active) ? " redundant-mirror" : ""), id);
      const mirror = mirrorJointParam(id);
      if (mirror) {
        chip.appendChild(el("span", "mirror-badge", ` → ${mirror}`));
      } else if (isRedundantMirrorTarget(id, active)) {
        chip.appendChild(el("span", "mirror-badge redundant", " redundant with Left*"));
      }
      const rm = el("button", "chip-x", "×");
      rm.type = "button";
      rm.onclick = () => sync(active.filter((x) => x !== id));
      chip.appendChild(rm);
      activeBox.appendChild(chip);
    }
  };

  const sync = (next) => {
    active = next;
    onChange([...active]);
    renderActive();
    drawPool();
  };

  search.oninput = () => {
    filterText = search.value;
    drawPool();
  };

  addBtn.onclick = () => {
    const v = customInp.value.trim();
    if (!v || active.includes(v)) return;
    sync([...active, v]);
    customInp.value = "";
  };

  renderActive();
  drawPool();
  return root;
}
