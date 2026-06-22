function el(tag, cls = "", text = "") {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text) n.textContent = text;
  return n;
}

function deepClone(v) {
  return JSON.parse(JSON.stringify(v));
}

export function emptyDriver() {
  return {
    target: { object: "", bone: null, property: "", shape_key: false },
    source: { object: "", bone: null, property: "", shape_key: false },
  };
}

function driverSummary(d) {
  const t = d.target ?? {};
  const s = d.source ?? {};
  const tObj = t.object || "?";
  const tProp = t.property || "?";
  const sObj = s.object || "?";
  const sProp = s.property || "?";
  const sBone = s.bone ? `@${s.bone}` : "";
  return `${tObj}.${tProp} ← ${sObj}${sBone}.${sProp}`;
}

function driverSearchText(d) {
  const parts = [
    d.target?.object,
    d.target?.property,
    d.target?.bone,
    d.source?.object,
    d.source?.property,
    d.source?.bone,
    d.expression,
  ];
  return parts.filter(Boolean).join(" ").toLowerCase();
}

function replaceInEndpoint(ep, find, replace) {
  if (!ep || !find) return;
  for (const k of ["object", "property", "bone"]) {
    if (typeof ep[k] === "string" && ep[k].includes(find)) {
      ep[k] = ep[k].split(find).join(replace);
    }
  }
}

function renderEndpoint(label, ep, setEp) {
  const sec = el("div", "driver-end");
  sec.appendChild(el("span", "driver-label", label));
  const grid = el("div", "field-grid tight");
  for (const k of ["object", "bone", "property", "shape_key"]) {
    if (!(k in ep) && k === "bone") ep.bone = null;
    const field = el("div", "field");
    field.appendChild(el("label", "field-label", k));
    if (k === "shape_key") {
      const toggle = el("label", "switch-row compact");
      const chk = el("input");
      chk.type = "checkbox";
      chk.checked = ep[k] ?? false;
      chk.onchange = () => {
        ep[k] = chk.checked;
        setEp({ ...ep });
      };
      toggle.append(chk, el("span", "switch-ui"));
      field.appendChild(toggle);
    } else if (k === "bone") {
      const inp = el("input", "input");
      inp.value = ep.bone ?? "";
      inp.placeholder = "null";
      inp.oninput = () => {
        ep.bone = inp.value.trim() || null;
        setEp({ ...ep });
      };
      field.appendChild(inp);
    } else {
      const inp = el("input", "input");
      inp.value = ep[k] ?? "";
      inp.oninput = () => {
        ep[k] = inp.value;
        setEp({ ...ep });
      };
      field.appendChild(inp);
    }
    grid.appendChild(field);
  }
  sec.appendChild(grid);
  return sec;
}

export function mountDriversEditor({ data, onChange }) {
  const root = el("div", "drivers-editor");
  let state = deepClone(data);
  const collapsed = new Set();
  const selected = new Set();
  let lastClickIndex = -1;
  let filterText = "";

  const push = () => onChange(deepClone(state));

  const setDrivers = (drivers) => {
    state = { ...state, drivers };
    push();
  };

  const visibleIndices = () => {
    const q = filterText.trim().toLowerCase();
    const drivers = state.drivers ?? [];
    if (!q) return drivers.map((_, i) => i);
    return drivers.map((d, i) => (driverSearchText(d).includes(q) ? i : -1)).filter((i) => i >= 0);
  };

  const syncSelection = () => {
    const max = (state.drivers ?? []).length;
    for (const i of [...selected]) {
      if (i >= max) selected.delete(i);
    }
  };

  const selectRange = (from, to) => {
    const a = Math.min(from, to);
    const b = Math.max(from, to);
    for (let i = a; i <= b; i++) selected.add(i);
  };

  const duplicateAt = (indices, asBlock = false) => {
    const drivers = [...(state.drivers ?? [])];
    const sorted = [...indices].sort((a, b) => a - b);
    selected.clear();
    if (asBlock) {
      const copies = sorted.map((i) => deepClone(drivers[i]));
      const insertAt = sorted[sorted.length - 1] + 1;
      drivers.splice(insertAt, 0, ...copies);
      for (let i = 0; i < copies.length; i++) selected.add(insertAt + i);
      lastClickIndex = insertAt;
    } else {
      for (const idx of [...sorted].reverse()) {
        drivers.splice(idx + 1, 0, deepClone(drivers[idx]));
        selected.add(idx + 1);
      }
      lastClickIndex = sorted[0] + 1;
    }
    setDrivers(drivers);
    render();
  };

  const deleteAt = (indices) => {
    const drivers = [...(state.drivers ?? [])];
    for (const idx of [...indices].sort((a, b) => b - a)) drivers.splice(idx, 1);
    selected.clear();
    lastClickIndex = -1;
    setDrivers(drivers);
    render();
  };

  const applyFindReplace = (indices, find, replace, scope) => {
    if (!find) return;
    const drivers = deepClone(state.drivers ?? []);
    for (const idx of indices) {
      const d = drivers[idx];
      if (!d) continue;
      if (scope === "all" || scope === "target") replaceInEndpoint(d.target, find, replace);
      if (scope === "all" || scope === "source") replaceInEndpoint(d.source, find, replace);
      if (scope === "all" && typeof d.expression === "string" && d.expression.includes(find)) {
        d.expression = d.expression.split(find).join(replace);
      }
    }
    setDrivers(drivers);
    render();
  };

  const bumpDriver = (item, titleEl) => {
    push();
    if (titleEl) {
      const summary = driverSummary(item);
      titleEl.textContent = summary;
      titleEl.title = summary;
    }
  };

  function render() {
    root.innerHTML = "";
    syncSelection();
    const drivers = state.drivers ?? [];
    const visible = visibleIndices();

    const heading = el("section", "section section-full drivers-heading");
    heading.appendChild(el("h3", "section-title", "Driver relationships"));
    heading.appendChild(
      el(
        "p",
        "chip-hint",
        "Bulk tools enabled — look for the filter bar, row checkboxes, and Duplicate block.",
      ),
    );
    root.appendChild(heading);

    const toolbar = el("div", "drivers-toolbar");
    const search = el("input", "input drivers-search");
    search.placeholder = "Filter by object, bone, or property…";
    search.value = filterText;
    search.oninput = () => {
      filterText = search.value;
      render();
    };

    const expandAll = el("button", "btn ghost tiny", "Expand all");
    expandAll.type = "button";
    expandAll.onclick = () => {
      collapsed.clear();
      render();
    };

    const collapseAll = el("button", "btn ghost tiny", "Collapse all");
    collapseAll.type = "button";
    collapseAll.onclick = () => {
      drivers.forEach((_, i) => collapsed.add(i));
      render();
    };

    const selectVisible = el("button", "btn ghost tiny", "Select visible");
    selectVisible.type = "button";
    selectVisible.onclick = () => {
      visible.forEach((i) => selected.add(i));
      render();
    };

    const clearSel = el("button", "btn ghost tiny", "Clear selection");
    clearSel.type = "button";
    clearSel.onclick = () => {
      selected.clear();
      lastClickIndex = -1;
      render();
    };

    toolbar.append(search, expandAll, collapseAll, selectVisible, clearSel);
    root.appendChild(toolbar);

    if (selected.size > 0) {
      const bulk = el("div", "drivers-bulk-bar");
      bulk.appendChild(el("span", "bulk-count", `${selected.size} selected`));

      const dupBtn = el("button", "btn primary tiny", "Duplicate block");
      dupBtn.type = "button";
      dupBtn.title = "Append copies of all selected drivers after the last selected row";
      dupBtn.onclick = () => duplicateAt(selected, true);

      const delBtn = el("button", "btn danger tiny", "Delete");
      delBtn.type = "button";
      delBtn.onclick = () => {
        if (window.confirm(`Delete ${selected.size} driver(s)?`)) deleteAt(selected);
      };

      const expSel = el("button", "btn ghost tiny", "Expand");
      expSel.type = "button";
      expSel.onclick = () => {
        selected.forEach((i) => collapsed.delete(i));
        render();
      };

      const colSel = el("button", "btn ghost tiny", "Collapse");
      colSel.type = "button";
      colSel.onclick = () => {
        selected.forEach((i) => collapsed.add(i));
        render();
      };

      const findIn = el("input", "input tiny drivers-find");
      findIn.placeholder = "Find";
      const replIn = el("input", "input tiny drivers-find");
      replIn.placeholder = "Replace";
      const scopeSel = el("select", "input tiny");
      for (const [val, lab] of [
        ["all", "All fields"],
        ["target", "Target only"],
        ["source", "Source only"],
      ]) {
        const opt = el("option", "", lab);
        opt.value = val;
        scopeSel.appendChild(opt);
      }
      const replBtn = el("button", "btn ghost tiny", "Replace in selected");
      replBtn.type = "button";
      replBtn.onclick = () => applyFindReplace(selected, findIn.value, replIn.value, scopeSel.value);

      bulk.append(dupBtn, delBtn, expSel, colSel, findIn, replIn, scopeSel, replBtn);
      root.appendChild(bulk);
    }

    const list = el("div", "drivers-list");
    if (!visible.length) {
      list.appendChild(el("p", "muted small", filterText ? "No drivers match filter." : "No drivers yet."));
    }

    for (const idx of visible) {
      const item = drivers[idx];
      const card = el("div", "rule-card driver-card" + (selected.has(idx) ? " selected" : ""));
      if (collapsed.has(idx)) card.classList.add("collapsed");

      const head = el("div", "card-head driver-card-head");
      const chk = el("input", "driver-select");
      chk.type = "checkbox";
      chk.checked = selected.has(idx);
      chk.onclick = (e) => e.stopPropagation();
      chk.onchange = () => {
        if (chk.checked) selected.add(idx);
        else selected.delete(idx);
        lastClickIndex = idx;
        render();
      };

      const toggle = el("button", "btn icon driver-toggle", collapsed.has(idx) ? "▸" : "▾");
      toggle.type = "button";
      toggle.title = "Expand / collapse";
      toggle.onclick = (e) => {
        e.stopPropagation();
        if (collapsed.has(idx)) collapsed.delete(idx);
        else collapsed.add(idx);
        render();
      };

      const title = el("strong", "driver-title mono", driverSummary(item));
      title.title = driverSummary(item);

      head.ondblclick = (e) => {
        if (e.target.closest("button, input, label")) return;
        if (collapsed.has(idx)) collapsed.delete(idx);
        else collapsed.add(idx);
        render();
      };
      head.onclick = (e) => {
        if (e.target.closest("button, input, label")) return;
        if (e.shiftKey && lastClickIndex >= 0) {
          selectRange(lastClickIndex, idx);
        } else if (e.ctrlKey || e.metaKey) {
          if (selected.has(idx)) selected.delete(idx);
          else selected.add(idx);
        } else {
          selected.clear();
          selected.add(idx);
        }
        lastClickIndex = idx;
        render();
      };

      const dupOne = el("button", "btn icon", "⧉");
      dupOne.type = "button";
      dupOne.title = "Duplicate";
      dupOne.onclick = (e) => {
        e.stopPropagation();
        duplicateAt([idx]);
      };

      const delOne = el("button", "btn icon danger", "×");
      delOne.type = "button";
      delOne.title = "Delete";
      delOne.onclick = (e) => {
        e.stopPropagation();
        deleteAt([idx]);
      };

      head.append(chk, toggle, title, dupOne, delOne);
      card.appendChild(head);

      const body = el("div", "driver-body");
      body.appendChild(
        renderEndpoint("Target", item.target, (v) => {
          item.target = v;
          bumpDriver(item, title);
        }),
      );
      body.appendChild(
        renderEndpoint("Source", item.source, (v) => {
          item.source = v;
          bumpDriver(item, title);
        }),
      );
      if ("expression" in item) {
        const expr = el("input", "input");
        expr.value = item.expression ?? "var";
        expr.placeholder = "expression";
        expr.oninput = () => {
          item.expression = expr.value;
          push();
        };
        const wrap = el("div", "field");
        wrap.appendChild(el("label", "field-label", "expression"));
        wrap.appendChild(expr);
        body.appendChild(wrap);
      }
      card.appendChild(body);
      list.appendChild(card);
    }
    root.appendChild(list);

    const foot = el("div", "drivers-foot");
    const add = el("button", "btn ghost add-btn", "+ Add driver");
    add.type = "button";
    add.onclick = () => {
      const next = [...drivers, emptyDriver()];
      const newIdx = next.length - 1;
      collapsed.delete(newIdx);
      selected.clear();
      selected.add(newIdx);
      lastClickIndex = newIdx;
      setDrivers(next);
      render();
    };
    foot.appendChild(
      el(
        "span",
        "muted small",
        "Shift+click row for range select · Ctrl/Cmd+click to toggle · double-click header to collapse",
      ),
    );
    foot.appendChild(add);
    root.appendChild(foot);
  }

  render();
  return root;
}
