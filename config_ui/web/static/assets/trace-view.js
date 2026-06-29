/** Value Trace main panel — stages, simulate, inline edits. */

import { mountRangeField } from "./joint-override-editor.js";
import { mountRuleCardReadOnly } from "./relational-rules-editor.js";
import { mountTraceRibbon } from "./trace-ribbon.js";
import { buildRuleFocus, buildStageFocus } from "./config-focus.js";
import { restoreScroll } from "./view-state.js";

const STAGE_CONSTRAINTS = "constraints";

function el(tag, cls = "", text = "") {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text) n.textContent = text;
  return n;
}

function fmt(v) {
  const n = Number(v);
  if (Number.isNaN(n)) return "—";
  return n.toFixed(4).replace(/\.?0+$/, "");
}

function isRange(v) {
  return v && typeof v === "object" && "min" in v && "max" in v;
}

/** Map config override → flat scene value range (scale adds 1.0). */
function overrideToFlatRange(paramKey, merged) {
  const parts = paramKey.split(".");
  const isScale = parts.length === 3 && parts[1] === "scale";
  let lo;
  let hi;
  if (isRange(merged)) {
    lo = Number(merged.min);
    hi = Number(merged.max);
  } else if (typeof merged === "number") {
    const abs = Math.abs(merged);
    lo = -abs;
    hi = abs;
  } else {
    return null;
  }
  if (isScale) {
    lo += 1;
    hi += 1;
  }
  return { min: lo, max: hi };
}

function isScaleParam(key) {
  const p = key.split(".");
  return p.length === 3 && p[1] === "scale";
}

function stepForStage(steps, stageId) {
  return steps?.find((s) => s.stage_id === stageId) ?? null;
}

function deepOverlay(base, patch) {
  const out = structuredClone(base);
  for (const [k, v] of Object.entries(patch)) {
    if (v && typeof v === "object" && !Array.isArray(v) && out[k] && typeof out[k] === "object") {
      out[k] = deepOverlay(out[k], v);
    } else {
      out[k] = v;
    }
  }
  return out;
}

export function mountTraceView(host, { profile, onDirty, onOpenConfigFile }) {
  let paramKey = "";
  let stageData = null;
  let simResult = null;
  let mode = "randomize_face";
  let inputMode = "random";
  let compact = true;
  let collapsed = new Set();
  const staging = {};
  const fileCache = {};

  const ribbonHost = el("div", "trace-ribbon-host");
  const simBar = el("div", "trace-sim-bar");
  const headerHost = el("div", "trace-header");
  const cardsHost = el("div", "trace-cards");
  const emptyHost = el("div", "trace-empty");
  emptyHost.appendChild(el("p", "trace-empty-title", "Pick a parameter"));
  emptyHost.appendChild(el("p", "muted", "Use the sidebar to search joints, shapes, or bone properties."));

  host.innerHTML = "";
  host.append(ribbonHost, simBar, headerHost, cardsHost, emptyHost);

  let ribbon = mountTraceRibbon(ribbonHost, {});

  const btnSim = el("button", "btn primary", "Simulate");
  btnSim.type = "button";

  const pipelineTabs = el("div", "trace-mode-tabs");
  const inputModeTabs = el("div", "trace-input-mode-tabs");
  const valuePicker = el("div", "trace-value-picker hidden");
  const valueSlider = el("input", "trace-value-slider");
  valueSlider.type = "range";
  const valueInput = el("input", "input small trace-value-num");
  valueInput.type = "number";
  valueInput.step = "any";
  const valueRangeLabel = el("span", "trace-value-range mono small");
  valuePicker.append(valueRangeLabel, valueSlider, valueInput);

  const seedWrap = el("div", "trace-seed-wrap hidden");
  const seedInput = el("input", "input small trace-seed");
  seedInput.type = "number";
  seedInput.placeholder = "Seed";
  seedWrap.append(el("label", "trace-seed-label", "Seed"), seedInput);

  valueSlider.oninput = () => {
    valueInput.value = valueSlider.value;
  };
  valueInput.oninput = () => {
    valueSlider.value = valueInput.value;
  };

  const densityBtn = el("button", "btn ghost tiny", "Show all fields");
  densityBtn.type = "button";

  function getEffectiveGenerationRange() {
    const fallback = stageData?.metadata?.value_range;
    const gen = stageData?.stages?.find((s) => s.stage_id === "generation");
    if (!gen) return fallback;

    const slice = gen.slice || {};
    const fid = gen.config_file;
    const staged = staging[fid] || {};

    if (slice.overrides) {
      for (const [k, v] of Object.entries(slice.overrides)) {
        const merged = staged.overrides?.[k] ?? v;
        if (staged.overrides?.[k] === undefined && fallback) return fallback;
        const flat = overrideToFlatRange(paramKey, merged);
        if (flat) return flat;
      }
    }

    if (slice.bone_properties) {
      for (const [k, spec] of Object.entries(slice.bone_properties)) {
        const merged = deepOverlay(spec, staged.bone_properties?.[k] || {});
        if (merged.min != null && merged.max != null) {
          return { min: merged.min, max: merged.max };
        }
      }
    }

    if (slice.independent_shapes) {
      for (const [k, spec] of Object.entries(slice.independent_shapes)) {
        const merged = deepOverlay(spec, staged.independent_shapes?.[k] || {});
        if (merged.min != null && merged.max != null) {
          return { min: merged.min, max: merged.max };
        }
      }
    }

    const bsStaged = staging.blendshapes || {};
    if (slice.variation_overrides && paramKey in slice.variation_overrides) {
      const cap = bsStaged.variation_overrides?.[paramKey] ?? slice.variation_overrides[paramKey];
      if (cap != null) return { min: 0, max: Number(cap) };
    }
    if (slice.max_variation !== undefined) {
      const cap = bsStaged.max_variation ?? slice.max_variation;
      return { min: 0, max: Number(cap) };
    }

    return fallback;
  }

  function syncValuePickerFromMeta() {
    const vr = simResult?.value_range || getEffectiveGenerationRange();
    if (!vr) return;
    const lo = Number(vr.min);
    const hi = Number(vr.max);
    const prev = parseFloat(valueInput.value);
    valueSlider.min = String(lo);
    valueSlider.max = String(hi);
    valueSlider.step = String(Math.max((hi - lo) / 200, 0.0001));
    const val = Number.isFinite(prev) ? Math.max(lo, Math.min(hi, prev)) : (lo + hi) / 2;
    valueSlider.value = String(val);
    valueInput.value = String(val);
    valueRangeLabel.textContent = `${fmt(lo)} … ${fmt(hi)}`;
  }

  function renderSimBar() {
    pipelineTabs.innerHTML = "";
    for (const [id, label] of [
      ["randomize_face", "Randomize Face"],
      ["rerandomize", "Rerandomize Selected"],
    ]) {
      const b = el("button", "trace-mode-tab" + (mode === id ? " active" : ""), label);
      b.type = "button";
      b.onclick = () => {
        mode = id;
        renderSimBar();
      };
      pipelineTabs.appendChild(b);
    }

    inputModeTabs.innerHTML = "";
    for (const [id, label] of [
      ["random", "Random"],
      ["value", "Pick value"],
      ["seed", "Fixed seed"],
    ]) {
      const b = el("button", "trace-input-tab" + (inputMode === id ? " active" : ""), label);
      b.type = "button";
      b.onclick = () => {
        inputMode = id;
        renderSimBar();
      };
      inputModeTabs.appendChild(b);
    }

    simBar.innerHTML = "";
    densityBtn.textContent = compact ? "Show all fields" : "Compact";

    const row1 = el("div", "trace-sim-row");
    row1.append(pipelineTabs, inputModeTabs, btnSim, densityBtn);
    simBar.appendChild(row1);

    valuePicker.classList.toggle("hidden", inputMode !== "value");
    seedWrap.classList.toggle("hidden", inputMode !== "seed");
    if (inputMode === "value") {
      syncValuePickerFromMeta();
      simBar.appendChild(valuePicker);
    }
    if (inputMode === "seed") simBar.appendChild(seedWrap);

    if (simResult?.full_pipeline && simResult.param_count) {
      const parts = [`Full pipeline · ${simResult.param_count} params`];
      if (simResult.seed != null) parts.push(`seed ${simResult.seed}`);
      if (simResult.starting_value != null) parts.push(`start ${fmt(simResult.starting_value)}`);
      simBar.appendChild(el("span", "trace-pipeline-badge muted small", parts.join(" · ")));
    }
  }

  densityBtn.onclick = () => {
    compact = !compact;
    renderSimBar();
    renderCards();
  };

  renderSimBar();

  const markStaging = (fileId, patch, { refreshRange = false } = {}) => {
    staging[fileId] = deepOverlay(staging[fileId] || fileCache[fileId] || {}, patch);
    onDirty(true, staging);
    if (refreshRange) syncValuePickerFromMeta();
  };

  async function ensureFile(fileId) {
    if (fileCache[fileId]) return fileCache[fileId];
    const res = await fetch(
      `/api/profiles/${encodeURIComponent(profile)}/config/${encodeURIComponent(fileId)}`,
    );
    if (!res.ok) throw new Error(await res.text());
    fileCache[fileId] = await res.json();
    return fileCache[fileId];
  }

  async function runSimulate() {
    if (!paramKey) return;
    ribbon = mountTraceRibbon(ribbonHost, { loading: true });
    try {
      const body = {
        param_key: paramKey,
        mode,
        config_overrides: Object.keys(staging).length ? staging : undefined,
      };
      if (inputMode === "seed") {
        const s = parseInt(seedInput.value, 10);
        if (!Number.isNaN(s)) body.seed = s;
      }
      if (inputMode === "value") {
        syncValuePickerFromMeta();
        const lo = parseFloat(valueSlider.min);
        const hi = parseFloat(valueSlider.max);
        let v = parseFloat(valueInput.value);
        if (!Number.isFinite(v)) v = (lo + hi) / 2;
        body.starting_value = Math.max(lo, Math.min(hi, v));
      }
      const res = await fetch(`/api/profiles/${encodeURIComponent(profile)}/trace/simulate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(await res.text());
      simResult = await res.json();
      ribbon = mountTraceRibbon(ribbonHost, {
        steps: simResult.steps,
        finalValue: simResult.final,
      });
      renderSimBar();
      renderCards();
    } catch (err) {
      ribbon = mountTraceRibbon(ribbonHost, {});
      const errEl = el("p", "trace-sim-error", err.message);
      ribbonHost.appendChild(errEl);
    }
  }

  btnSim.onclick = () => void runSimulate();

  async function loadParam(key, { skipSimulate = false } = {}) {
    paramKey = key;
    simResult = null;
    ribbon = mountTraceRibbon(ribbonHost, {});
    const res = await fetch(
      `/api/profiles/${encodeURIComponent(profile)}/trace/${encodeURIComponent(key)}`,
    );
    if (!res.ok) throw new Error(await res.text());
    stageData = await res.json();
    collapsed = new Set(stageData.stages.map((_, i) => i));
    syncValuePickerFromMeta();
    renderHeader();
    renderCards();
    emptyHost.classList.add("hidden");
    cardsHost.classList.remove("hidden");
    headerHost.classList.remove("hidden");
    simBar.classList.remove("hidden");
    if (!skipSimulate) await runSimulate();
  }

  async function restoreState(state) {
    if (!state?.paramKey) return;
    paramKey = state.paramKey;
    mode = state.mode ?? mode;
    inputMode = state.inputMode ?? inputMode;
    compact = state.compact ?? compact;
    collapsed = new Set(state.collapsed ?? []);
    for (const k of Object.keys(staging)) delete staging[k];
    Object.assign(staging, state.staging ?? {});
    stageData = state.stageData ?? null;
    simResult = state.simResult ?? null;

    if (!stageData) {
      await loadParam(paramKey);
      return;
    }

    syncValuePickerFromMeta();
    renderHeader();
    renderSimBar();
    renderCards();
    ribbon = mountTraceRibbon(ribbonHost, {
      steps: simResult?.steps,
      finalValue: simResult?.final,
    });
    emptyHost.classList.add("hidden");
    cardsHost.classList.remove("hidden");
    headerHost.classList.remove("hidden");
    simBar.classList.remove("hidden");
    if (state.valueInput != null) valueInput.value = state.valueInput;
    if (state.seedInput != null) seedInput.value = state.seedInput;
    restoreScroll(cardsHost, state.cardsScrollTop ?? 0);
    onDirty(Object.keys(staging).length > 0, staging);
  }

  function exportViewState() {
    return {
      paramKey,
      stageData,
      simResult,
      mode,
      inputMode,
      compact,
      collapsed: [...collapsed],
      staging: { ...staging },
      valueInput: valueInput.value,
      seedInput: seedInput.value,
      cardsScrollTop: cardsHost.scrollTop,
    };
  }

  function renderHeader() {
    headerHost.innerHTML = "";
    if (!stageData) return;
    const m = stageData.metadata;
    const h = el("div", "trace-header-inner");
    h.appendChild(el("h2", "trace-param-title mono", m.key));
    h.appendChild(el("span", "badge", m.kind));
    if (m.feature_group) h.appendChild(el("span", "badge muted", m.feature_group));
    if (m.symmetry_partner) {
      const link = el("button", "btn ghost tiny", `↔ ${m.symmetry_partner}`);
      link.type = "button";
      link.onclick = () => void loadParam(m.symmetry_partner);
      h.appendChild(link);
    }
    headerHost.appendChild(h);
  }

  function valueBadge(stageId) {
    const step = stepForStage(simResult?.steps, stageId);
    if (!step) return null;
    const b = el("span", "trace-value-badge mono" + (step.skipped ? " skipped" : ""));
    b.textContent = step.skipped ? "skipped" : fmt(step.value);
    if (step.delta != null && Math.abs(step.delta) > 1e-9) {
      b.appendChild(
        el(
          "span",
          "trace-delta-chip mono " + (step.delta > 0 ? "trace-delta-up" : "trace-delta-down"),
          `Δ ${step.delta > 0 ? "+" : ""}${fmt(step.delta)}`,
        ),
      );
    }
    return b;
  }

  function compactRow(stage, index) {
    const row = el("div", "trace-stage-compact");
    row.appendChild(el("span", "trace-stage-num", String(index + 1)));
    row.appendChild(el("span", "trace-stage-label", stage.label));
    row.appendChild(el("span", "file-badge", stage.config_file));
    row.appendChild(el("span", "muted small", "no config for this param"));
    const badge = valueBadge(stage.stage_id);
    if (badge) row.appendChild(badge);
    return row;
  }

  function stageCard(stage, index) {
    const isCollapsed = collapsed.has(index);
    const card = el("div", "trace-stage-card" + (isCollapsed ? " collapsed" : " expanded"));

    const head = el("div", "trace-stage-head");
    head.appendChild(el("span", "trace-stage-chevron", isCollapsed ? "▸" : "▾"));
    head.appendChild(el("span", "trace-stage-num", String(index + 1)));
    head.appendChild(el("strong", "", stage.label));
    head.appendChild(el("span", "file-badge", stage.config_file));
    const badge = valueBadge(stage.stage_id);
    if (badge) head.appendChild(badge);

    const openBtn = el("button", "btn ghost tiny", "Open in Config →");
    openBtn.type = "button";
    openBtn.onclick = (e) => {
      e.stopPropagation();
      if (stageData?.metadata) {
        onOpenConfigFile(buildStageFocus(stage, stageData.metadata));
      } else {
        onOpenConfigFile({ fileId: stage.config_file });
      }
    };
    head.appendChild(openBtn);

    head.onclick = (e) => {
      if (e.target.closest("button")) return;
      if (collapsed.has(index)) collapsed.delete(index);
      else collapsed.add(index);
      renderCards();
    };

    card.appendChild(head);

    const body = el("div", "trace-stage-body");
    for (const note of stage.notes || []) {
      body.appendChild(el("p", "trace-note muted small", note));
    }
    renderStageFields(body, stage);
    card.appendChild(body);

    return card;
  }

  function renderCards() {
    cardsHost.innerHTML = "";
    if (!stageData) return;

    for (let i = 0; i < stageData.stages.length; i++) {
      const stage = stageData.stages[i];
      if (!stage.has_config && compact && stage.stage_id !== STAGE_CONSTRAINTS) {
        cardsHost.appendChild(compactRow(stage, i));
        continue;
      }
      cardsHost.appendChild(stageCard(stage, i));
    }

    if (simResult?.final != null) {
      const hero = el("div", "trace-final-hero");
      hero.appendChild(el("span", "trace-final-label", "Final value"));
      hero.appendChild(el("span", "trace-final-value mono", fmt(simResult.final)));
      const genStep = stepForStage(simResult.steps, "generation");
      const genVal = genStep?.value;
      if (genVal != null && Math.abs(genVal - simResult.final) > 1e-9) {
        hero.appendChild(
          el(
            "span",
            "trace-final-gen muted small",
            `(after generate: ${fmt(genVal)} — attract/constrain may move outside generation range)`,
          ),
        );
      }
      cardsHost.appendChild(hero);
    }
  }

  function numField(parent, label, value, onChange) {
    const row = el("label", "field-row");
    row.appendChild(el("span", "field-label", label));
    const inp = el("input", "input small");
    inp.type = "number";
    inp.step = "any";
    inp.value = value ?? "";
    inp.oninput = () => onChange(parseFloat(inp.value));
    row.appendChild(inp);
    parent.appendChild(row);
  }

  function renderStageFields(body, stage) {
    const slice = stage.slice || {};
    const fid = stage.config_file;

    if (stage.stage_id === "generation") {
      body.appendChild(
        el("p", "trace-note muted small", "Edits stage locally until you click Simulate."),
      );
      if (isScaleParam(paramKey)) {
        body.appendChild(
          el(
            "p",
            "trace-note muted small",
            "Scale overrides are offsets from 1.0 (config −0.1 → scene 0.9). Pick value uses scene values.",
          ),
        );
      }
      if (slice.overrides) {
        for (const [k, v] of Object.entries(slice.overrides)) {
          const row = el("div", "trace-field-row");
          row.appendChild(el("span", "mono small", k));
          mountRangeField(row, v, async (next) => {
            await ensureFile(fid);
            const overrides = { ...(staging[fid]?.overrides || fileCache[fid].overrides || {}) };
            overrides[k] = next;
            markStaging(fid, { overrides }, { refreshRange: true });
          });
          body.appendChild(row);
        }
      }
      if (slice.bone_properties) {
        for (const [k, spec] of Object.entries(slice.bone_properties)) {
          numField(body, `${k} min`, spec.min, async (v) => {
            await ensureFile("chaos_joints");
            markStaging(
              "chaos_joints",
              { bone_properties: { [k]: { ...spec, min: v } } },
              { refreshRange: true },
            );
          });
          numField(body, `${k} max`, spec.max, async (v) => {
            await ensureFile("chaos_joints");
            markStaging(
              "chaos_joints",
              { bone_properties: { [k]: { ...spec, max: v } } },
              { refreshRange: true },
            );
          });
        }
      }
      if (slice.max_variation !== undefined && !compact) {
        numField(body, "max_variation", slice.max_variation, async (v) => {
          await ensureFile("blendshapes");
          markStaging("blendshapes", { max_variation: v }, { refreshRange: true });
        });
      }
      if (slice.independent_shapes) {
        for (const [k, spec] of Object.entries(slice.independent_shapes)) {
          numField(body, `${k} min`, spec.min, async (v) => {
            markStaging(
              "blendshapes",
              { independent_shapes: { [k]: { ...spec, min: v } } },
              { refreshRange: true },
            );
          });
          numField(body, `${k} max`, spec.max, async (v) => {
            markStaging(
              "blendshapes",
              { independent_shapes: { [k]: { ...spec, max: v } } },
              { refreshRange: true },
            );
          });
        }
      }
    }

    if (stage.stage_id === "attractor") {
      if (slice.enabled !== undefined) {
        const row = el("label", "switch-row compact");
        const chk = el("input");
        chk.type = "checkbox";
        chk.checked = !!slice.enabled;
        chk.onchange = async () => {
          await ensureFile(fid);
          markStaging(fid, { enabled: chk.checked });
        };
        row.append(chk, el("span", "switch-ui"), el("span", "", "Enabled"));
        body.appendChild(row);
      }
      if (slice.max_influence != null) {
        numField(body, "max_influence", slice.max_influence, async (v) => {
          await ensureFile(fid);
          markStaging(fid, { max_influence: v });
        });
      }
      if (slice.distance_weight != null) {
        numField(body, "distance_weight", slice.distance_weight, async (v) => {
          await ensureFile(fid);
          markStaging(fid, { distance_weights: { [paramKey]: v } });
        });
      }
    }

    if (stage.stage_id === "constraints") {
      body.appendChild(
        el(
          "p",
          "trace-note muted small",
          "Simulation runs the full pipeline (all params generated) — constraints resolve against live peer values.",
        ),
      );
      const constrainStep = stepForStage(simResult?.steps, "constraints");
      if (constrainStep?.substeps?.length) {
        const sub = el("div", "trace-subsection trace-rule-substeps");
        sub.appendChild(el("h4", "", "Rule-by-rule (this param)"));
        for (const ss of constrainStep.substeps) {
          const row = el("div", "trace-substep-row");
          const delta =
            ss.delta != null && Math.abs(ss.delta) > 1e-9
              ? ` Δ ${ss.delta > 0 ? "+" : ""}${fmt(ss.delta)}`
              : " · no change";
          row.appendChild(el("span", "trace-substep-title", ss.title));
          row.appendChild(el("span", "trace-substep-value mono", `${fmt(ss.value)}${delta}`));
          const peerKeys = Object.keys(ss.peers || {});
          if (peerKeys.length) {
            row.appendChild(
              el(
                "span",
                "trace-substep-peers mono small",
                peerKeys.map((k) => `${k}=${fmt(ss.peers[k])}`).join("  "),
              ),
            );
          }
          sub.appendChild(row);
        }
        body.appendChild(sub);
      } else if (constrainStep && !constrainStep.skipped) {
        body.appendChild(
          el("p", "muted small", "No constraint rules changed this param for this seed (already satisfied)."),
        );
      }
      if (simResult?.peer_context && Object.keys(simResult.peer_context).length) {
        const peers = el("div", "trace-subsection");
        peers.appendChild(el("h4", "", "Peer values at constrain"));
        peers.appendChild(
          el(
            "p",
            "mono small",
            Object.entries(simResult.peer_context)
              .map(([k, v]) => `${k} = ${fmt(v)}`)
              .join("  ·  "),
          ),
        );
        body.appendChild(peers);
      }
      if (slice.hard_clamp) {
        const hc = el("div", "trace-subsection");
        hc.appendChild(el("h4", "", "Hard clamp"));
        const spec = slice.hard_clamp;
        numField(hc, "min", spec.min, async (v) => {
          await ensureFile(fid);
          markStaging(fid, { hard_clamps: { [paramKey]: { ...spec, min: v } } });
        });
        numField(hc, "max", spec.max, async (v) => {
          await ensureFile(fid);
          markStaging(fid, { hard_clamps: { [paramKey]: { ...spec, max: v } } });
        });
        body.appendChild(hc);
      }
      if (slice.write_rules?.length) {
        const sec = el("div", "trace-subsection");
        sec.appendChild(el("h4", "", `Writes (${slice.write_rules.length})`));
        for (const entry of slice.write_rules) {
          sec.appendChild(
            mountRuleCardReadOnly(entry, {
              index: entry.index,
              writes: true,
              onOpenInConfig: (e) => onOpenConfigFile(buildRuleFocus(e)),
            }),
          );
        }
        body.appendChild(sec);
      }
      if (slice.read_rules?.length) {
        const sec = el("div", "trace-subsection");
        sec.appendChild(el("h4", "", `Referenced by (${slice.read_rules.length})`));
        for (const entry of slice.read_rules) {
          sec.appendChild(
            mountRuleCardReadOnly(entry, {
              index: entry.index,
              writes: false,
              onOpenInConfig: (e) => onOpenConfigFile(buildRuleFocus(e)),
            }),
          );
        }
        body.appendChild(sec);
      }
    }

    if (stage.stage_id === "rerandomize") {
      body.appendChild(
        el(
          "p",
          "muted small",
          slice.is_target ? "This param is a rerandomize target" : "Not in rerandomize targets",
        ),
      );
      if (slice.sampling_range) {
        body.appendChild(
          el(
            "p",
            "mono small",
            `Sample range: ${slice.sampling_range.min} … ${slice.sampling_range.max}`,
          ),
        );
      }
    }
  }

  cardsHost.classList.add("hidden");
  headerHost.classList.add("hidden");
  simBar.classList.add("hidden");

  return {
    loadParam,
    restoreState,
    exportViewState,
    getStaging() {
      return { ...staging };
    },
    clearStaging() {
      for (const k of Object.keys(staging)) delete staging[k];
      for (const k of Object.keys(fileCache)) delete fileCache[k];
    },
    hasStaging() {
      return Object.keys(staging).length > 0;
    },
  };
}
