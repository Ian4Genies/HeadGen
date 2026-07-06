/**
 * Dedicated chaos_joints.json editor — schema-driven from VariationConfig.
 */

const CHANNELS = [
  { id: "location", label: "Location", axes: ["x", "y", "z"], global: "transform_max" },
  { id: "rotation", label: "Rotation", axes: ["x", "y", "z"], global: "rotate_max" },
  { id: "scale", label: "Scale", axes: ["x", "y", "z"], global: "scale_max" },
];

function el(tag, cls = "", text = "") {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text) n.textContent = text;
  return n;
}

function deepClone(v) {
  return JSON.parse(JSON.stringify(v));
}

function isRange(v) {
  return v && typeof v === "object" && "min" in v && "max" in v && !Array.isArray(v);
}

function parseOverrides(map) {
  const joints = {};
  for (const [key, val] of Object.entries(map)) {
    const p = key.split(".");
    const joint = p[0];
    if (!joints[joint]) joints[joint] = {};
    if (p.length === 2) {
      if (!joints[joint][p[1]]) joints[joint][p[1]] = { axes: {} };
      joints[joint][p[1]].channel = val;
    } else if (p.length === 3) {
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

function mirrorPartner(name) {
  if (name.startsWith("Right")) return "Left" + name.slice(5);
  if (name.startsWith("Left")) return "Right" + name.slice(4);
  return null;
}

function isMirrorJoint(name) {
  return name.startsWith("Right");
}

function syncMirrorJointNames(names) {
  const lefts = new Set(names.filter((n) => n.startsWith("Left")));
  const result = [];
  const emitted = new Set();
  for (const name of names) {
    if (emitted.has(name)) continue;
    if (name.startsWith("Left")) {
      result.push(name);
      emitted.add(name);
      const right = mirrorPartner(name);
      if (right && !emitted.has(right)) {
        result.push(right);
        emitted.add(right);
      }
    } else if (isMirrorJoint(name)) {
      const left = mirrorPartner(name);
      if (left && lefts.has(left) && !emitted.has(name)) {
        result.push(name);
        emitted.add(name);
      }
    } else {
      result.push(name);
      emitted.add(name);
    }
  }
  return result;
}

export function mountChaosJointsEditor({ data, onChange, focus, uiStore }) {
  const root = el("div", "chaos-editor");
  let state = deepClone(data);
  if (state.joint_names) {
    state.joint_names = syncMirrorJointNames(state.joint_names);
  }
  let schema = null;
  let selectedOverrideJoint =
    focus?.joint ??
    uiStore?.get("selectedJoint") ??
    null;

  const persistJoint = (joint) => {
    selectedOverrideJoint = joint;
    uiStore?.set({ selectedJoint: joint });
  };

  const push = () => onChange(deepClone(state));

  const setJointNames = (names) => setState({ joint_names: syncMirrorJointNames(names) });

  const setState = (patch) => {
    state = { ...state, ...patch };
    push();
  };

  fetch("/api/schema/chaos_joints")
    .then((r) => r.json())
    .then((s) => {
      schema = s;
      render();
    })
    .catch(() => render());

  function render() {
    root.innerHTML = "";
    root.appendChild(renderGlobals());
    root.appendChild(renderJointList());
    root.appendChild(renderOverrides());
    root.appendChild(renderBoneProperties());
    applyFocusScroll();
  }

  function applyFocusScroll() {
    if (!focus?.section) return;
    requestAnimationFrame(() => {
      const sec = root.querySelector(`[data-config-section="${focus.section}"]`);
      if (!sec) return;
      sec.scrollIntoView({ behavior: "smooth", block: "start" });
      if (focus.section === "bone_properties" && focus.paramKey) {
        const card = sec.querySelector(`[data-bone-prop="${focus.paramKey}"]`);
        if (card) {
          card.classList.add("config-focus-highlight");
          setTimeout(() => card.classList.remove("config-focus-highlight"), 2200);
          card.scrollIntoView({ behavior: "smooth", block: "center" });
        }
      }
    });
  }

  function renderGlobals() {
    const sec = el("section", "section section-full");
    sec.dataset.configSection = "globals";
    sec.appendChild(el("h3", "section-title", "Global fallbacks"));
    const grid = el("div", "field-grid cols-4");
    const defs = schema?.globals ?? {
      transform_max: { label: "Location max (m)" },
      rotate_max: { label: "Rotation max (°)" },
      scale_max: { label: "Scale max" },
      enable_scale: { label: "Enable scale" },
    };
    for (const [key, meta] of Object.entries(defs)) {
      const field = el("div", "field");
      field.appendChild(el("label", "field-label", meta.label ?? key));
      if (meta.type === "bool" || typeof state[key] === "boolean") {
        const row = el("label", "switch-row");
        const chk = el("input");
        chk.type = "checkbox";
        chk.checked = !!state[key];
        chk.onchange = () => setState({ [key]: chk.checked });
        row.append(chk, el("span", "switch-ui"));
        field.appendChild(row);
      } else {
        const inp = el("input", "input");
        inp.type = "number";
        inp.step = "any";
        inp.value = state[key];
        inp.oninput = () => setState({ [key]: parseFloat(inp.value) || 0 });
        field.appendChild(inp);
      }
      grid.appendChild(field);
    }
    sec.appendChild(grid);
    return sec;
  }

  function renderJointList() {
    const sec = el("section", "section section-full");
    sec.dataset.configSection = "joint_names";
    sec.appendChild(el("h3", "section-title", "Active joints"));
    sec.appendChild(
      el(
        "p",
        "chip-hint",
        "Left* joints mirror to Right* at runtime — only add Left* or center joints, never Right*.",
      ),
    );

    const names = state.joint_names ?? [];
    const center = names.filter((n) => !n.startsWith("Left") && !n.startsWith("Right"));
    const left = names.filter((n) => n.startsWith("Left"));
    const badRight = names.filter((n) => isMirrorJoint(n));

    const lists = el("div", "joint-lists");
    lists.appendChild(jointGroup("Center joints", center, null));
    lists.appendChild(jointGroup("Left joints (auto-mirror → Right*)", left, (n) => mirrorPartner(n)));
    if (badRight.length) {
      lists.appendChild(jointGroup("⚠ Remove these — use Left* instead", badRight, null));
    }
    sec.appendChild(lists);

    const addRow = el("div", "add-row");
    const inp = el("input", "input mono");
    inp.placeholder = "Joint name (e.g. FaceBind)";
    const addBtn = el("button", "btn primary", "+ Add joint");
    addBtn.type = "button";
    addBtn.onclick = async () => {
      const name = inp.value.trim();
      if (!name || names.includes(name)) return;
      if (isMirrorJoint(name)) {
        alert(`Add "${mirrorPartner(name)}" instead — Right* joints are mirrored automatically.`);
        return;
      }
      if ((schema?.joint_names?.blocked ?? []).includes(name)) {
        alert(`${name} is blocked from joint_names.`);
        return;
      }
      await fetch("/api/manifests/joints/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: [name] }),
      });
      setJointNames([...names, name]);
      inp.value = "";
      render();
    };
    addRow.append(inp, addBtn);
    sec.appendChild(addRow);

    const catalogHost = el("div", "manifest-host");
    sec.appendChild(catalogHost);
    import("./grouped-list.js").then(({ mountGroupedManifestList }) =>
      mountGroupedManifestList({
        manifestId: "joints",
        activeItems: names.filter((n) => !isMirrorJoint(n)),
        itemLabel: "joint",
        groupMode: "joints",
        onChange: (items) => {
          setJointNames(items);
          render();
        },
      }).then((node) => catalogHost.replaceChildren(node)),
    );

    return sec;
  }

  function jointGroup(title, items, mirrorFn) {
    const box = el("div", "joint-group");
    box.appendChild(el("h4", "group-name", title));
    const chips = el("div", "chips active-chips");
    if (!items.length) chips.appendChild(el("span", "muted small", "None"));
    for (const name of items) {
      const chip = el("span", "chip active-chip mono", name);
      if (mirrorFn) {
        chip.appendChild(el("span", "mirror-badge", ` → ${mirrorFn(name)}`));
      }
      const rm = el("button", "chip-x", "×");
      rm.type = "button";
      rm.title = "Remove from active joints";
      rm.onclick = () => {
        setJointNames((state.joint_names ?? []).filter((x) => x !== name));
        render();
      };
      chip.appendChild(rm);
      chips.appendChild(chip);
    }
    box.appendChild(chips);
    return box;
  }

  function renderOverrides() {
    const sec = el("section", "section section-full");
    sec.dataset.configSection = "overrides";
    sec.appendChild(el("h3", "section-title", "Per-joint overrides"));
    sec.appendChild(
      el(
        "p",
        "chip-hint",
        "Toggle channels/axes, switch ± symmetric ↔ min/max split. Value 0 locks an axis.",
      ),
    );

    const overrides = state.overrides ?? {};
    let parsed = parseOverrides(overrides);
    const overrideJoints = [
      ...new Set([
        ...(state.joint_names ?? []),
        ...Object.keys(parsed),
        ...(focus?.joint ? [focus.joint] : []),
      ]),
    ].sort();

    let selected =
      selectedOverrideJoint && overrideJoints.includes(selectedOverrideJoint)
        ? selectedOverrideJoint
        : overrideJoints[0] ?? "";
    persistJoint(selected);
    const picker = el("div", "joint-picker-row");
    const sel = el("select", "input joint-select");
    for (const j of overrideJoints) {
      const opt = el("option", "", j);
      opt.value = j;
      if (j === selected) opt.selected = true;
      sel.appendChild(opt);
    }
    sel.onchange = () => {
      selected = sel.value;
      persistJoint(selected);
      drawMatrix();
    };
    picker.appendChild(sel);

    const clearJoint = el("button", "btn ghost", "Clear all overrides for joint");
    clearJoint.type = "button";
    clearJoint.onclick = () => {
      if (!selected || !window.confirm(`Remove all overrides for ${selected}?`)) return;
      delete parsed[selected];
      state.overrides = flattenOverrides(parsed);
      push();
      drawMatrix();
    };
    picker.appendChild(clearJoint);
    sec.appendChild(picker);

    const matrix = el("div", "joint-matrix");
    sec.appendChild(matrix);

    const globals = {
      transform_max: state.transform_max,
      rotate_max: state.rotate_max,
      scale_max: state.scale_max,
    };

    const syncOverrides = () => {
      state.overrides = flattenOverrides(parsed);
      push();
    };

    function drawMatrix() {
      matrix.innerHTML = "";
      if (!selected) {
        matrix.appendChild(el("p", "muted small", "Add a joint first"));
        return;
      }
      if (!(state.joint_names ?? []).includes(selected)) {
        matrix.appendChild(
          el(
            "p",
            "chip-hint",
            "Not in joint_names — overrides saved but won't affect generation until joint is active.",
          ),
        );
      }
      matrix.appendChild(el("h4", "joint-selected mono", selected));
      if (!parsed[selected]) parsed[selected] = {};

      for (const ch of CHANNELS) {
        const block = el("div", "channel-block");
        block.appendChild(el("span", "channel-label", ch.label));
        const chData = parsed[selected][ch.id] ?? { axes: {} };
        parsed[selected][ch.id] = chData;
        const def = globals[ch.global] ?? 0.1;

        const wholeRow = el("div", "axis-row");
        wholeRow.appendChild(el("span", "axis-tag", "ALL"));
        const wholeOn = el("label", "switch-row compact");
        const wholeChk = el("input");
        wholeChk.type = "checkbox";
        wholeChk.checked = chData.channel !== undefined;
        wholeChk.onchange = () => {
          if (wholeChk.checked) chData.channel = def;
          else delete chData.channel;
          syncOverrides();
          drawMatrix();
        };
        wholeOn.append(wholeChk, el("span", "switch-ui"), el("span", "switch-label", "Whole channel"));
        wholeRow.appendChild(wholeOn);
        if (chData.channel !== undefined) {
          wholeRow.appendChild(
            rangeEditor(chData.channel, (v) => {
              chData.channel = v;
              syncOverrides();
            }, def, drawMatrix),
          );
        }
        block.appendChild(wholeRow);

        const grid = el("div", "axis-grid");
        for (const ax of ch.axes) {
          const row = el("div", "axis-row");
          row.appendChild(el("span", "axis-tag mono", ax));
          const on = el("label", "switch-row compact");
          const chk = el("input");
          chk.type = "checkbox";
          chk.checked = chData.axes[ax] !== undefined;
          chk.onchange = () => {
            if (chk.checked) chData.axes[ax] = def;
            else delete chData.axes[ax];
            syncOverrides();
            drawMatrix();
          };
          on.append(chk, el("span", "switch-ui"));
          row.appendChild(on);
          if (chData.axes[ax] !== undefined) {
            row.appendChild(
              rangeEditor(chData.axes[ax], (v) => {
                chData.axes[ax] = v;
                syncOverrides();
              }, def, drawMatrix),
            );
          }
          grid.appendChild(row);
        }
        block.appendChild(grid);
        matrix.appendChild(block);
      }
    }

    drawMatrix();
    return sec;
  }

  function renderBoneProperties() {
    const sec = el("section", "section section-full");
    sec.dataset.configSection = "bone_properties";
    sec.appendChild(el("h3", "section-title", "Bone custom properties"));
    sec.appendChild(
      el(
        "p",
        "chip-hint",
        "Samples [min,max] each frame. Target exactly one: pose bone (dropdown) or scene object (string).",
      ),
    );

    const props = state.bone_properties ?? {};
    const boneTargets = [...new Set(state.joint_names ?? [])].sort();
    const defaultEntry = schema?.bone_properties?.default_entry ?? {
      min: 0,
      max: 1,
      target_bone: "LeftEyeSocketBind",
    };

    const list = el("div", "bone-prop-list");
    for (const [name, spec] of Object.entries(props)) {
      const card = bonePropCard(name, spec, props, boneTargets, defaultEntry);
      card.dataset.boneProp = name;
      list.appendChild(card);
    }
    sec.appendChild(list);

    const addRow = el("div", "add-row");
    const nameIn = el("input", "input mono");
    nameIn.placeholder = "Property name (e.g. var_iris_shrink)";
    const addBtn = el("button", "btn primary", "+ Add property");
    addBtn.type = "button";
    addBtn.onclick = async () => {
      const name = nameIn.value.trim();
      if (!name || name in props) return;
      props[name] = deepClone(defaultEntry);
      state.bone_properties = { ...props };
      await fetch("/api/manifests/bone_properties/register", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ ids: [name] }),
      });
      push();
      nameIn.value = "";
      render();
    };
    addRow.append(nameIn, addBtn);
    sec.appendChild(addRow);
    return sec;
  }

  function bonePropCard(name, spec, props, boneTargets, defaultEntry) {
    const card = el("div", "rule-card bone-prop-card");
    const head = el("div", "card-head");
    head.appendChild(el("strong", "mono", name));
    const del = el("button", "btn icon danger", "×");
    del.type = "button";
    del.title = "Remove property";
    del.onclick = () => {
      delete props[name];
      state.bone_properties = { ...props };
      push();
      render();
    };
    head.appendChild(del);
    card.appendChild(head);

    const grid = el("div", "field-grid cols-2");
    grid.append(
      numberField("min", spec.min ?? 0, (v) => syncSpec({ min: v })),
      numberField("max", spec.max ?? 1, (v) => syncSpec({ max: v })),
    );
    card.appendChild(grid);

    let targetMode = "target_object" in spec ? "object" : "bone";

    const modeRow = el("div", "target-mode-row");
    modeRow.appendChild(el("span", "field-label", "Target type"));
    const boneBtn = el(
      "button",
      "btn ghost tiny" + (targetMode === "bone" ? " active-mode" : ""),
      "Pose bone",
    );
    const objBtn = el(
      "button",
      "btn ghost tiny" + (targetMode === "object" ? " active-mode" : ""),
      "Scene object",
    );
    boneBtn.type = "button";
    objBtn.type = "button";
    modeRow.append(boneBtn, objBtn);
    card.appendChild(modeRow);

    const targetWrap = el("div", "field");
    card.appendChild(targetWrap);

    function syncSpec(partial) {
      const out = {
        min: partial.min ?? spec.min ?? 0,
        max: partial.max ?? spec.max ?? 1,
      };
      if (targetMode === "object") {
        out.target_object = partial.target_object ?? spec.target_object ?? "";
      } else {
        out.target_bone = partial.target_bone ?? spec.target_bone ?? boneTargets[0] ?? "LeftEyeSocketBind";
      }
      Object.keys(spec).forEach((k) => delete spec[k]);
      Object.assign(spec, out);
      props[name] = { ...spec };
      state.bone_properties = { ...props };
      push();
    }

    function setMode(next) {
      targetMode = next;
      syncSpec({});
      drawTarget();
      boneBtn.classList.toggle("active-mode", next === "bone");
      objBtn.classList.toggle("active-mode", next === "object");
    }

    function drawTarget() {
      targetWrap.innerHTML = "";
      if (targetMode === "object") {
        targetWrap.appendChild(el("label", "field-label", "Object name"));
        const inp = el("input", "input mono");
        inp.value = spec.target_object ?? "";
        inp.placeholder = "e.g. headOnly_geo";
        inp.oninput = () => syncSpec({ target_object: inp.value });
        targetWrap.appendChild(inp);
      } else {
        targetWrap.appendChild(el("label", "field-label", "Pose bone"));
        const sel = el("select", "input mono");
        const cur = spec.target_bone ?? "";
        for (const b of [...new Set([...boneTargets, cur].filter(Boolean))].sort()) {
          const opt = el("option", "", b);
          opt.value = b;
          if (b === cur) opt.selected = true;
          sel.appendChild(opt);
        }
        sel.onchange = () => syncSpec({ target_bone: sel.value });
        targetWrap.appendChild(sel);
      }
    }

    boneBtn.onclick = () => setMode("bone");
    objBtn.onclick = () => setMode("object");
    drawTarget();
    return card;
  }

  function numberField(label, value, onInput) {
    const f = el("div", "field");
    f.appendChild(el("label", "field-label", label));
    const inp = el("input", "input");
    inp.type = "number";
    inp.step = "any";
    inp.value = value;
    inp.oninput = () => onInput(parseFloat(inp.value) || 0);
    f.appendChild(inp);
    return f;
  }

  function rangeEditor(val, setVal, fallback, onRestructure) {
    const wrap = el("div", "range-editor");

    const draw = () => {
      wrap.innerHTML = "";
      const split = isRange(val);
      const modes = el("div", "mode-row");
      const symBtn = el("button", "btn ghost tiny" + (!split ? " active-mode" : ""), "± symmetric");
      const splitBtn = el("button", "btn ghost tiny" + (split ? " active-mode" : ""), "min / max");
      symBtn.type = "button";
      splitBtn.type = "button";
      symBtn.onclick = () => {
        if (isRange(val)) {
          setVal(Math.max(Math.abs(val.min), Math.abs(val.max)));
          onRestructure();
        }
      };
      splitBtn.onclick = () => {
        if (!isRange(val)) {
          const v = typeof val === "number" ? val : fallback;
          setVal({ min: -Math.abs(v), max: Math.abs(v) });
          onRestructure();
        }
      };
      modes.append(symBtn, splitBtn);
      wrap.appendChild(modes);

      if (isRange(val)) {
        const row = el("div", "range-pair");
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
        row.append(min, el("span", "range-sep", "→"), max);
        wrap.appendChild(row);
      } else {
        const row = el("div", "range-pair");
        const num = el("input", "input small");
        num.type = "number";
        num.step = "any";
        num.value = val;
        num.oninput = () => setVal(parseFloat(num.value) || 0);
        row.appendChild(num);
        row.appendChild(el("span", "muted small", val === 0 ? "(locks axis)" : "→ [-v, +v]"));
        wrap.appendChild(row);
      }
    };

    draw();
    return wrap;
  }

  render();
  return root;
}
