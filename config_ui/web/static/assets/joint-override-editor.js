/** Joint override editor — pick joint → channel/axis toggles + values. */

const CHANNELS = [
  { id: "location", label: "Location", axes: ["x", "y", "z"], globalKey: "transform_max" },
  { id: "rotation", label: "Rotation", axes: ["x", "y", "z"], globalKey: "rotate_max" },
  { id: "scale", label: "Scale", axes: ["x", "y", "z"], globalKey: "scale_max" },
];

function el(tag, cls = "", text = "") {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text) n.textContent = text;
  return n;
}

function isRange(v) {
  return v && typeof v === "object" && "min" in v && "max" in v;
}

function parseOverrides(map) {
  const joints = {};
  for (const [key, val] of Object.entries(map)) {
    const p = key.split(".");
    const joint = p[0];
    if (!joints[joint]) joints[joint] = {};
    if (p.length === 2) joints[joint][p[1]] = { channel: val, axes: {} };
    if (p.length === 3) {
      if (!joints[joint][p[1]]) joints[joint][p[1]] = { axes: {} };
      joints[joint][p[1]].axes[p[2]] = val;
    }
  }
  return joints;
}

function flattenOverrides(parsed) {
  const out = {};
  for (const [joint, channels] of Object.entries(parsed)) {
    for (const [chId, data] of Object.entries(channels)) {
      if (data.channel !== undefined) out[`${joint}.${chId}`] = data.channel;
      for (const [ax, val] of Object.entries(data.axes ?? {})) {
        out[`${joint}.${chId}.${ax}`] = val;
      }
    }
  }
  return out;
}

export function mountJointOverrideEditor({ overrides, jointNames, globals, onChange }) {
  const root = el("div", "joint-editor");
  let map = { ...overrides };
  let parsed = parseOverrides(map);
  let selected = jointNames[0] ?? "";

  const sync = () => {
    map = flattenOverrides(parsed);
    onChange(map);
  };

  const defaultFor = (globalKey) => globals[globalKey] ?? 0.1;

  const renderMatrix = () => {
    const panel = root.querySelector(".joint-matrix");
    if (!panel) return;
    panel.innerHTML = "";
    if (!selected) {
      panel.appendChild(el("p", "muted small", "Add joints above first"));
      return;
    }
    panel.appendChild(el("h4", "joint-selected mono", selected));
    if (!parsed[selected]) parsed[selected] = {};

    for (const ch of CHANNELS) {
      const sec = el("div", "channel-block");
      sec.appendChild(el("span", "channel-label", ch.label));
      const chData = parsed[selected][ch.id] ?? { axes: {} };
      parsed[selected][ch.id] = chData;

      const chRow = el("div", "axis-row");
      const chOn = el("label", "switch-row compact");
      const chChk = el("input");
      chChk.type = "checkbox";
      chChk.checked = chData.channel !== undefined;
      chChk.onchange = () => {
        if (chChk.checked) chData.channel = defaultFor(ch.globalKey);
        else delete chData.channel;
        sync();
        renderMatrix();
      };
      chOn.append(chChk, el("span", "switch-ui"), el("span", "switch-label", "All axes"));
      chRow.appendChild(chOn);
      if (chData.channel !== undefined) {
        chRow.appendChild(makeAxisValue(chData.channel, (v) => {
          chData.channel = v;
          sync();
        }, defaultFor(ch.globalKey)));
      }
      sec.appendChild(chRow);

      const axes = el("div", "axis-grid");
      for (const ax of ch.axes) {
        const row = el("div", "axis-row");
        row.appendChild(el("span", "axis-tag mono", ax));
        const on = el("label", "switch-row compact");
        const chk = el("input");
        chk.type = "checkbox";
        chk.checked = chData.axes[ax] !== undefined;
        chk.onchange = () => {
          if (chk.checked) chData.axes[ax] = defaultFor(ch.globalKey);
          else delete chData.axes[ax];
          sync();
          renderMatrix();
        };
        on.append(chk, el("span", "switch-ui"));
        row.appendChild(on);
        if (chData.axes[ax] !== undefined) {
          row.appendChild(makeAxisValue(chData.axes[ax], (v) => {
            chData.axes[ax] = v;
            sync();
          }, defaultFor(ch.globalKey)));
        }
        axes.appendChild(row);
      }
      sec.appendChild(axes);
      panel.appendChild(sec);
    }
  };

  const render = () => {
    root.innerHTML = "";
    const picker = el("div", "joint-picker-row");
    const sel = el("select", "input joint-select");
    for (const j of jointNames) {
      const opt = el("option", "", j);
      opt.value = j;
      if (j === selected) opt.selected = true;
      sel.appendChild(opt);
    }
    sel.onchange = () => {
      selected = sel.value;
      renderMatrix();
    };
    const search = el("input", "input");
    search.placeholder = "Jump to joint…";
    search.oninput = () => {
      const q = search.value.trim().toLowerCase();
      const hit = jointNames.find((j) => j.toLowerCase().includes(q));
      if (hit) {
        selected = hit;
        sel.value = hit;
        renderMatrix();
      }
    };
    picker.append(sel, search);
    root.appendChild(picker);
    root.appendChild(el("div", "joint-matrix"));
    renderMatrix();
  };

  render();
  return root;
}

function makeAxisValue(val, setVal, fallback) {
  const wrap = el("div", "axis-value");
  if (isRange(val)) {
    const min = el("input", "input small");
    min.type = "number";
    min.step = "any";
    min.value = val.min;
    const max = el("input", "input small");
    max.type = "number";
    max.step = "any";
    max.value = val.max;
    const sync = () => setVal({ min: parseFloat(min.value) || 0, max: parseFloat(max.value) || 0 });
    min.oninput = max.oninput = sync;
    wrap.append(min, el("span", "range-sep", "→"), max);
    const sym = el("button", "btn ghost tiny", "±");
    sym.type = "button";
    sym.onclick = () => setVal(Math.max(Math.abs(val.min), Math.abs(val.max)));
    wrap.appendChild(sym);
  } else {
    const num = el("input", "input small");
    num.type = "number";
    num.step = "any";
    num.value = val;
    num.oninput = () => setVal(parseFloat(num.value) || 0);
    wrap.appendChild(num);
    const asym = el("button", "btn ghost tiny", "{min,max}");
    asym.type = "button";
    asym.onclick = () => setVal({ min: -Math.abs(val || fallback), max: Math.abs(val || fallback) });
    wrap.appendChild(asym);
  }
  return wrap;
}

export function mountClampEditor({ clamps, paramSuggestions, onChange, title = "Clamps" }) {
  const root = el("div", "joint-editor");
  let map = { ...clamps };
  let selected = Object.keys(map)[0] ?? paramSuggestions[0] ?? "";

  const renderDetail = () => {
    const panel = root.querySelector(".joint-matrix");
    if (!panel) return;
    panel.innerHTML = "";
    if (!selected) {
      panel.appendChild(el("p", "muted small", "Pick a parameter"));
      return;
    }
    if (!map[selected]) map[selected] = { min: -1, max: 1 };
    panel.appendChild(el("h4", "joint-selected mono", selected));
    const row = el("div", "range-pair");
    const min = el("input", "input");
    min.type = "number";
    min.step = "any";
    min.value = map[selected].min;
    const max = el("input", "input");
    max.type = "number";
    max.step = "any";
    max.value = map[selected].max;
    const sync = () => {
      map[selected] = { min: parseFloat(min.value) || 0, max: parseFloat(max.value) || 0 };
      onChange({ ...map });
    };
    min.oninput = max.oninput = sync;
    row.append(min, el("span", "range-sep", "→"), max);
    const del = el("button", "btn ghost tiny", "Remove");
    del.type = "button";
    del.onclick = () => {
      delete map[selected];
      onChange({ ...map });
      render();
    };
    row.appendChild(del);
    panel.appendChild(row);
  };

  const render = () => {
    root.innerHTML = "";
    root.appendChild(el("p", "muted small", title));
    const picker = el("div", "picker-split");
    const list = el("div", "picker-list");
    const search = el("input", "input search");
    search.placeholder = "Filter parameters…";
    list.appendChild(search);
    const items = el("div", "picker-items");
    const all = [...new Set([...Object.keys(map), ...paramSuggestions])].sort();
    const draw = (q = "") => {
      items.innerHTML = "";
      for (const name of all.filter((n) => n.toLowerCase().includes(q.toLowerCase()))) {
        const btn = el("button", "picker-item mono" + (name === selected ? " active" : ""), name);
        btn.type = "button";
        if (name in map) btn.classList.add("has-cap");
        btn.onclick = () => {
          selected = name;
          if (!(name in map)) {
            map[name] = { min: -1, max: 1 };
            onChange({ ...map });
          }
          renderDetail();
          draw(search.value.trim());
        };
        items.appendChild(btn);
      }
    };
    search.oninput = () => draw(search.value.trim());
    draw();
    picker.appendChild(list);
    picker.appendChild(el("div", "joint-matrix"));
    root.appendChild(picker);
    renderDetail();
  };

  render();
  return root;
}
