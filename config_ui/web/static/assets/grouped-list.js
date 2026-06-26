/** Grouped checklist for joints / shapes — full-width, searchable. */

function el(tag, cls = "", text = "") {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text) n.textContent = text;
  return n;
}

function groupId(name, mode) {
  if (mode === "joints") return name.replace(/Bind$/, "") || "Other";
  const seg = name.split("_")[0];
  return seg.charAt(0).toUpperCase() + seg.slice(1);
}

async function fetchManifest(id) {
  const res = await fetch(`/api/manifests/${encodeURIComponent(id)}`);
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

async function registerManifest(id, ids) {
  await fetch(`/api/manifests/${encodeURIComponent(id)}/register`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ids }),
  });
}

export async function mountGroupedManifestList({
  manifestId,
  activeItems,
  onChange,
  itemLabel = "item",
  groupMode = "shape",
}) {
  const root = el("div", "grouped-list");
  let manifest = await fetchManifest(manifestId);
  let active = new Set(activeItems);

  const sync = () => onChange([...active]);

  const render = () => {
    root.innerHTML = "";
    const blocked = new Set(manifest.blocked ?? []);
    const allIds = manifest.items.map((i) => i.id);
    const catalog = allIds.filter((id) => !blocked.has(id))
      .filter((id) => (groupMode === "joints" ? !id.startsWith("Right") : true));

    const toolbar = el("div", "list-toolbar");
    const search = el("input", "input search");
    search.placeholder = `Search ${itemLabel}s…`;
    const count = el("span", "list-count", `${active.size} active · ${catalog.length} in catalog`);
    toolbar.append(search, count);
    root.appendChild(toolbar);

    const groups = el("div", "group-grid");
    const grouped = {};
    for (const id of catalog) {
      const g = groupId(id, groupMode);
      (grouped[g] ??= []).push(id);
    }

    const draw = (q = "") => {
      groups.innerHTML = "";
      const ql = q.toLowerCase();
      for (const [g, ids] of Object.entries(grouped).sort(([a], [b]) => a.localeCompare(b))) {
        const filtered = ids.filter((id) => id.toLowerCase().includes(ql));
        if (!filtered.length) continue;
        const card = el("div", "group-card");
        const head = el("div", "group-head");
        const activeInGroup = filtered.filter((id) => active.has(id)).length;
        head.appendChild(el("span", "group-name", g));
        head.appendChild(el("span", "group-meta", `${activeInGroup}/${filtered.length}`));
        const allBtn = el("button", "btn ghost tiny", "All");
        allBtn.type = "button";
        allBtn.onclick = () => {
          filtered.forEach((id) => active.add(id));
          sync();
          render();
        };
        const noneBtn = el("button", "btn ghost tiny", "None");
        noneBtn.type = "button";
        noneBtn.onclick = () => {
          filtered.forEach((id) => active.delete(id));
          sync();
          render();
        };
        head.append(allBtn, noneBtn);
        card.appendChild(head);

        const list = el("div", "check-list");
        for (const id of filtered) {
          const row = el("label", "check-row");
          const chk = el("input");
          chk.type = "checkbox";
          chk.checked = active.has(id);
          chk.onchange = () => {
            if (chk.checked) active.add(id);
            else active.delete(id);
            sync();
            count.textContent = `${active.size} active · ${catalog.length} in catalog`;
          };
          row.append(chk, el("span", "mono check-label", id));
          list.appendChild(row);
        }
        card.appendChild(list);
        groups.appendChild(card);
      }
    };
    search.oninput = () => draw(search.value.trim());
    draw();
    root.appendChild(groups);

    if (blocked.size) {
      root.appendChild(el("p", "manifest-subtitle blocked-title", "Blocked"));
      const box = el("div", "chips");
      for (const id of [...blocked].sort()) {
        box.appendChild(el("span", "chip blocked-chip mono", id));
      }
      root.appendChild(box);
    }

    const addRow = el("div", "add-row");
    const inp = el("input", "input mono");
    inp.placeholder = `Register new ${itemLabel}…`;
    const btn = el("button", "btn ghost", "Register & activate");
    btn.type = "button";
    btn.onclick = async () => {
      const id = inp.value.trim();
      if (!id || blocked.has(id)) return;
      await registerManifest(manifestId, [id]);
      manifest = await fetchManifest(manifestId);
      active.add(id);
      sync();
      inp.value = "";
      render();
    };
    addRow.append(inp, btn);
    root.appendChild(addRow);
  };

  render();
  return root;
}

export async function mountShapePicker({
  shapes,
  activeMap,
  onChange,
  title = "Pick shape",
  initialShape,
  uiStore,
}) {
  const root = el("div", "shape-picker");
  let selected =
    (initialShape && shapes.includes(initialShape) ? initialShape : null) ??
    (uiStore?.get("selectedShape") && shapes.includes(uiStore.get("selectedShape"))
      ? uiStore.get("selectedShape")
      : null) ??
    "";

  const persistShape = (name) => {
    selected = name;
    uiStore?.set({ selectedShape: name });
  };
  const map = { ...activeMap };

  const renderDetail = () => {
    const panel = root.querySelector(".picker-detail");
    if (!panel) return;
    panel.innerHTML = "";
    if (!selected) {
      panel.appendChild(el("p", "muted small", "Select a shape to set its cap"));
      return;
    }
    panel.appendChild(el("h4", "picker-shape-name mono", selected));
    const val = map[selected];
    const isRange = val && typeof val === "object" && "min" in val;
    const row = el("div", "cap-row");
    if (isRange) {
      const min = el("input", "input small");
      min.type = "number";
      min.step = "any";
      min.value = val.min;
      const max = el("input", "input small");
      max.type = "number";
      max.step = "any";
      max.value = val.max;
      const sync = () => {
        map[selected] = { min: parseFloat(min.value) || 0, max: parseFloat(max.value) || 0 };
        onChange({ ...map });
      };
      min.oninput = max.oninput = sync;
      row.append(min, el("span", "range-sep", "→"), max);
    } else {
      const num = el("input", "input");
      num.type = "number";
      num.step = "any";
      num.value = val ?? 0;
      num.oninput = () => {
        map[selected] = parseFloat(num.value) || 0;
        onChange({ ...map });
      };
      row.appendChild(num);
    }
    const del = el("button", "btn ghost tiny", "Remove cap");
    del.type = "button";
    del.onclick = () => {
      delete map[selected];
      onChange({ ...map });
      renderDetail();
    };
    row.appendChild(del);
    panel.appendChild(row);
  };

  const render = () => {
    root.innerHTML = "";
    root.appendChild(el("p", "muted small", title));
    const body = el("div", "picker-split");
    const list = el("div", "picker-list");
    const search = el("input", "input search");
    search.placeholder = "Filter shapes…";
    search.value = uiStore?.get("pickerSearch") ?? "";
    list.appendChild(search);
    const items = el("div", "picker-items");
    list.appendChild(items);
    const draw = (q = "") => {
      items.innerHTML = "";
      for (const name of shapes.filter((s) => s.toLowerCase().includes(q.toLowerCase()))) {
        const btn = el("button", "picker-item mono" + (name === selected ? " active" : ""), name);
        btn.type = "button";
        if (name in map) btn.classList.add("has-cap");
        btn.onclick = () => {
          persistShape(name);
          if (!(name in map)) {
            map[name] = 0.5;
            onChange({ ...map });
          }
          renderDetail();
          draw(search.value.trim());
        };
        items.appendChild(btn);
      }
    };
    search.oninput = () => {
      uiStore?.set({ pickerSearch: search.value });
      draw(search.value.trim());
    };
    draw(search.value.trim());
    body.appendChild(list);
    body.appendChild(el("div", "picker-detail"));
    root.appendChild(body);
    renderDetail();
  };

  render();
  return root;
}
