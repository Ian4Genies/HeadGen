import {
  MANIFEST_LIST_KEYS,
  RULE_TYPES,
  isBonePropertiesKey,
  isChannelsKey,
  isIndependentShapesKey,
  isIntMapKey,
  isObjectArrayKey,
  isOverrideMapKey,
  isRegistryTargetsKey,
  labelFor,
} from "./meta.js";
import { mountManifestList, mountRegistryPicker } from "./manifest-list.js";
import { mountGroupedManifestList, mountShapePicker } from "./grouped-list.js";
import { mountClampEditor, mountJointOverrideEditor } from "./joint-override-editor.js";
import { mountChaosJointsEditor } from "./chaos-joints-editor.js";
import { mountDriversEditor } from "./drivers-editor.js?v=3";
import { mountRelationalRulesEditor } from "./relational-rules-editor.js";
import { mountInlineParamInput, mountInlineParamList } from "./inline-param-input.js";
import {
  emptyRule,
  migrateRuleType,
  migrationDataLoss,
  normalizeRule,
  ruleTypeDescription,
  ruleTypeHelp,
  schemaFields,
  validateRule,
} from "./rule-schemas.js";
import { FILE_LAYOUTS } from "./file-layouts.js";
import { scrollToConfigTarget } from "./config-focus.js";
import { createUiStore, restoreScroll } from "./view-state.js";

function deepClone(v) {
  return JSON.parse(JSON.stringify(v));
}

function isRangeObj(v) {
  return v && typeof v === "object" && "min" in v && "max" in v && !Array.isArray(v);
}

function isIndependentEntry(v) {
  return v && typeof v === "object" && "min" in v && "max" in v && "mirror_sides" in v;
}

export class ConfigForm {
  #root;
  #data;
  #saved;
  #onChange;
  #profile;
  #fileId;
  #focus;
  #uiStore;
  #scrollRestore;
  #rulesCollapsed = new Set();
  #rulesCollapsedInit = false;
  #rulesFilter = "";
  #rulesMuteFilter = "all";
  #paramSuggestions = [];
  #staleKeys = new Set();
  #registryLoaded = false;

  constructor(root, data, onChange, options = {}) {
    this.#root = root;
    this.#data = deepClone(data);
    this.#saved = JSON.stringify(data);
    this.#onChange = onChange;
    this.#profile = options.profile ?? "";
    this.#fileId = options.fileId ?? "";
    this.#focus = options.focus ?? null;
    this.#uiStore = createUiStore(options.savedState?.ui ?? {});
    this.#scrollRestore = this.#focus ? null : (options.savedState?.scrollTop ?? null);
    if (this.#focus?.joint) this.#uiStore.set({ selectedJoint: this.#focus.joint });
    if (this.#focus?.paramKey) {
      this.#uiStore.set({
        selectedParam: this.#focus.paramKey,
        selectedShape: this.#focus.paramKey,
      });
    }
    if (this.#focus?.targetEntry) this.#uiStore.set({ registryFilter: this.#focus.targetEntry });
    this.render();
  }

  exportViewState() {
    this.#syncRulesUiState();
    return {
      scrollTop: this.#root.scrollTop,
      ui: { ...this.#uiStore.state },
    };
  }

  #syncRulesUiState() {
    this.#uiStore.set({
      rulesFilter: this.#rulesFilter,
      rulesMuteFilter: this.#rulesMuteFilter,
      rulesCollapsed: [...this.#rulesCollapsed],
    });
  }

  #finishRender(scrollTop = 0) {
    const focus = this.#focus;
    this.#scrollRestore = null;
    requestAnimationFrame(() => {
      if (focus?.section) {
        const sec =
          this.#root.querySelector(`[data-config-section~="${focus.section}"]`) ??
          this.#root.querySelector(`[data-config-section="${focus.section}"]`);
        scrollToConfigTarget(sec);
        this.#focus = null;
      } else if (scrollTop > 0) {
        restoreScroll(this.#root, scrollTop);
      }
    });
  }

  getData() {
    const data = deepClone(this.#data);
    if (this.#fileId === "constraints" && Array.isArray(data.relational_rules)) {
      data.relational_rules = data.relational_rules.map(normalizeRule);
    }
    return data;
  }

  isDirty() {
    return JSON.stringify(this.#data) !== this.#saved;
  }

  markSaved() {
    this.#saved = JSON.stringify(this.#data);
  }

  #touch() {
    this.#onChange?.(this.isDirty());
  }

  #set(path, value) {
    let obj = this.#data;
    for (let i = 0; i < path.length - 1; i++) obj = obj[path[i]];
    obj[path[path.length - 1]] = value;
    this.#touch();
  }

  #getAt(path) {
    let obj = this.#data;
    for (const p of path) obj = obj[p];
    return obj;
  }

  render() {
    const scrollTop = this.#scrollRestore ?? this.#root.scrollTop ?? 0;
    this.#root.innerHTML = "";
    this.#root.className = "form-scroll";
    if (this.#fileId === "chaos_joints") {
      this.#root.appendChild(
        mountChaosJointsEditor({
          data: this.#data,
          focus: this.#focus,
          uiStore: this.#uiStore,
          onChange: (next) => {
            this.#data = deepClone(next);
            this.#touch();
          },
        }),
      );
      this.#finishRender(scrollTop);
      return;
    }
    if (this.#fileId === "drivers") {
      this.#root.appendChild(
        mountDriversEditor({
          data: this.#data,
          uiStore: this.#uiStore,
          onChange: (next) => {
            this.#data = deepClone(next);
            this.#touch();
          },
        }),
      );
      this.#finishRender(scrollTop);
      return;
    }
    const layout = FILE_LAYOUTS[this.#fileId];
    if (layout) {
      this.#root.appendChild(this.#renderLayout(layout));
    } else {
      this.#root.appendChild(this.#node(this.#data, [], null));
    }
    this.#finishRender(scrollTop);
  }

  #renderLayout(layout) {
    const wrap = el("div", "file-layout");
    for (const sec of layout.sections) {
      const section = el("section", "section section-full");
      section.dataset.configSection = sec.keys.join(" ");
      if (sec.title) section.appendChild(el("h3", "section-title", sec.title));
      if (sec.hint) section.appendChild(el("p", "chip-hint", sec.hint));
      const body = el("div", sec.full ? "section-body" : `field-grid cols-${sec.cols ?? 2}`);
      for (const k of sec.keys) {
        if (!(k in this.#data)) continue;
        const node = this.#node(this.#data[k], [k], k);
        if (sec.full) {
          body.appendChild(node);
        } else {
          body.appendChild(this.#fieldWrap(k, node));
        }
      }
      section.appendChild(body);
      wrap.appendChild(section);
    }
    return wrap;
  }

  #node(value, path, key) {
    if (key === "seed" || (path[path.length - 1] === "seed" && value === null)) {
      return this.#seedField(path, value);
    }
    if (key === "frame_range" && Array.isArray(value) && value.length === 2) {
      return this.#frameRangeField(path, value);
    }
    if (key && MANIFEST_LIST_KEYS[key] && Array.isArray(value)) {
      return this.#manifestListField(path, key);
    }
    if (isRegistryTargetsKey(key, this.#fileId) && Array.isArray(value)) {
      return this.#registryTargetsField(path);
    }
    if (isBonePropertiesKey(key) && value && typeof value === "object") {
      return this.#bonePropertiesEditor(path);
    }
    if (isIndependentShapesKey(key) && value && typeof value === "object") {
      return this.#independentShapesEditor(path);
    }
    if (key && isOverrideMapKey(key)) {
      if (key === "overrides" && this.#fileId === "chaos_joints") {
        return this.#jointOverridesField(path);
      }
      if (key === "hard_clamps") {
        return this.#hardClampsField(path);
      }
      if (key === "variation_overrides") {
        return this.#shapeOverridesField(path, this.#data.variation_shapes ?? [], "Variation shape caps");
      }
      if (key === "expression_overrides") {
        return this.#shapeOverridesField(path, this.#data.expression_shapes ?? [], "Expression shape caps");
      }
      if (key === "distance_weights") {
        return this.#weightOverridesField(path);
      }
      return this.#overrideMap(path, value, key === "hard_clamps");
    }
    if (key && isIntMapKey(key)) {
      return this.#intMap(path, value);
    }
    if (key === "relational_rules" && Array.isArray(value)) {
      return this.#relationalRulesField(path, value);
    }
    if (key && isObjectArrayKey(key)) {
      return this.#objectArray(path, value, key);
    }
    if (key && isChannelsKey(key)) {
      return this.#channels(path);
    }
    if (key === "hair_color_defaults" && Array.isArray(value)) {
      return this.#colorList(path);
    }
    if (Array.isArray(value)) {
      if (value.every((x) => typeof x === "string")) return this.#stringList(path);
      if (value.every((x) => typeof x === "number")) return this.#numberList(path);
      return this.#genericArray(path, value);
    }
    if (value && typeof value === "object") {
      return this.#section(path, key, value);
    }
    return this.#scalar(path, key, value);
  }

  #section(path, key, obj) {
    const sec = el("section", "section");
    if (key) {
      sec.appendChild(el("h3", "section-title", labelFor(key)));
    }
    const grid = el("div", key === "paths" ? "field-grid paths-grid" : "field-grid");
    for (const [k, v] of Object.entries(obj)) {
      grid.appendChild(this.#fieldWrap(k, this.#node(v, [...path, k], k)));
    }
    sec.appendChild(grid);
    return sec;
  }

  #fieldWrap(key, node, customLabel = null) {
    const wrap = el("div", "field");
    wrap.appendChild(el("label", "field-label", customLabel ?? labelFor(key)));
    wrap.appendChild(node);
    return wrap;
  }

  async #loadParamRegistry() {
    if (this.#registryLoaded) return;
    try {
      const reg = await fetch(
        `/api/profiles/${encodeURIComponent(this.#profile)}/registry`,
      ).then((r) => r.json());
      this.#paramSuggestions = reg.rerandomize_suggestions ?? [];
    } catch {
      this.#paramSuggestions = Object.keys(this.#data.hard_clamps ?? {});
    }
    this.#registryLoaded = true;
  }

  async #refreshConstraintLint(host) {
    try {
      const result = await fetch(
        `/api/profiles/${encodeURIComponent(this.#profile)}/constraints/validate`,
      ).then((r) => r.json());
      this.#staleKeys = new Set(result.stale_keys ?? []);
      host.replaceChildren(this.#buildConstraintLintPanel(result, host));
    } catch (err) {
      host.replaceChildren(el("p", "muted small", `Lint unavailable: ${err.message}`));
    }
  }

  #buildConstraintLintPanel(result, lintHost) {
    const panel = el("div", "constraint-lint");
    const stale = result.stale_keys ?? [];
    const issues = result.rules_with_issues ?? [];
    if (!stale.length && !issues.length) {
      panel.appendChild(el("p", "chip-hint ok-hint", "All constraint references look valid."));
      return panel;
    }
    if (stale.length) {
      const sec = el("div", "lint-block");
      sec.appendChild(el("strong", "", "Stale parameter keys"));
      sec.appendChild(el("p", "muted small", stale.join(", ")));
      panel.appendChild(sec);
    }
    if (issues.length) {
      const sec = el("div", "lint-block");
      sec.appendChild(el("strong", "", "Incomplete rules"));
      for (const issue of issues) {
        sec.appendChild(
          el(
            "p",
            "muted small",
            `#${issue.index + 1} ${issue.title || issue.type}: ${issue.missing.join(", ")}`,
          ),
        );
      }
      panel.appendChild(sec);
    }
    const refresh = el("button", "btn ghost tiny", "Refresh lint");
    refresh.type = "button";
    refresh.onclick = () => void this.#refreshConstraintLint(lintHost);
    panel.appendChild(refresh);
    return panel;
  }

  #scalar(path, key, value) {
    if (typeof value === "boolean") return this.#toggle(path, value);
    if (typeof value === "number") return this.#numberInput(path, value);
    const input = el("input", "input full");
    input.type = "text";
    input.value = value ?? "";
    input.oninput = () => this.#set(path, input.value);
    return input;
  }

  #toggle(path, value) {
    const row = el("label", "switch-row");
    const input = el("input");
    input.type = "checkbox";
    input.checked = value;
    input.onchange = () => this.#set(path, input.checked);
    row.appendChild(input);
    row.appendChild(el("span", "switch-ui"));
    return row;
  }

  #numberInput(path, value, step = "any") {
    const input = el("input", "input full");
    input.type = "number";
    input.step = step;
    input.value = value;
    input.oninput = () => {
      const n = parseFloat(input.value);
      this.#set(path, Number.isFinite(n) ? n : 0);
    };
    return input;
  }

  #seedField(path, value) {
    const wrap = el("div", "seed-field");
    const random = el("label", "switch-row");
    const chk = el("input");
    chk.type = "checkbox";
    chk.checked = value === null;
    chk.onchange = () => {
      this.#set(path, chk.checked ? null : 0);
      this.render();
    };
    random.appendChild(chk);
    random.appendChild(el("span", "switch-ui"));
    random.appendChild(el("span", "switch-label", "Random each run"));
    wrap.appendChild(random);
    if (value !== null) {
      wrap.appendChild(this.#numberInput(path, value, "1"));
    }
    return wrap;
  }

  #frameRangeField(path, value) {
    const row = el("div", "range-pair");
    const start = el("input", "input small");
    start.type = "number";
    start.step = "1";
    start.value = value[0];
    const end = el("input", "input small");
    end.type = "number";
    end.step = "1";
    end.value = value[1];
    const sync = () => {
      this.#set(path, [parseInt(start.value, 10) || 0, parseInt(end.value, 10) || 0]);
    };
    start.oninput = end.oninput = sync;
    row.appendChild(el("span", "range-label", "Start"));
    row.appendChild(start);
    row.appendChild(el("span", "range-label", "End"));
    row.appendChild(end);
    return row;
  }

  #manifestListField(path, key) {
    const host = el("div", "manifest-host");
    host.appendChild(el("span", "muted small", "Loading…"));
    const meta = MANIFEST_LIST_KEYS[key];
    const groupMode = key === "joint_names" ? "joints" : "shape";
    mountGroupedManifestList({
      manifestId: meta.manifestId,
      activeItems: this.#getAt(path),
      itemLabel: meta.itemLabel,
      groupMode,
      onChange: (items) => this.#set(path, items),
    })
      .then((node) => host.replaceChildren(node))
      .catch((err) => {
        host.textContent = err.message;
      });
    return host;
  }

  #jointOverridesField(path) {
    const host = el("div", "manifest-host");
    host.dataset.configSection = "overrides";
    const joint =
      this.#focus?.joint ?? this.#uiStore.get("selectedJoint") ?? null;
    host.appendChild(
      mountJointOverrideEditor({
        overrides: this.#getAt(path),
        jointNames: this.#data.joint_names ?? [],
        globals: {
          transform_max: this.#data.transform_max,
          rotate_max: this.#data.rotate_max,
          scale_max: this.#data.scale_max,
        },
        initialJoint: joint,
        uiStore: this.#uiStore,
        onChange: (map) => this.#set(path, map),
      }),
    );
    return host;
  }

  #hardClampsField(path) {
    const host = el("div", "manifest-host");
    host.dataset.configSection = "hard_clamps";
    host.appendChild(el("span", "muted small", "Loading parameters…"));
    const focusParam =
      this.#focus?.paramKey ?? this.#uiStore.get("selectedParam") ?? null;
    fetch(`/api/profiles/${encodeURIComponent(this.#profile)}/registry`)
      .then((r) => r.json())
      .then((reg) => {
        host.replaceChildren(
          mountClampEditor({
            clamps: this.#getAt(path),
            paramSuggestions: reg.rerandomize_suggestions ?? [],
            onChange: (map) => this.#set(path, map),
            title: "Pick parameter → set min/max clamp",
            initialParam: focusParam,
            uiStore: this.#uiStore,
          }),
        );
      })
      .catch(() => {
        host.replaceChildren(
          mountClampEditor({
            clamps: this.#getAt(path),
            paramSuggestions: Object.keys(this.#getAt(path)),
            onChange: (map) => this.#set(path, map),
            initialParam: focusParam,
            uiStore: this.#uiStore,
          }),
        );
      });
    return host;
  }

  #shapeOverridesField(path, shapes, title) {
    const host = el("div", "manifest-host");
    const sectionKey = path[path.length - 1];
    host.dataset.configSection = sectionKey;
    host.appendChild(el("span", "muted small", "Loading…"));
    const initialShape =
      this.#focus?.paramKey ?? this.#uiStore.get("selectedShape") ?? null;
    mountShapePicker({
      shapes,
      activeMap: this.#getAt(path),
      title,
      initialShape,
      uiStore: this.#uiStore,
      onChange: (map) => this.#set(path, map),
    })
      .then((node) => host.replaceChildren(node))
      .catch((err) => {
        host.textContent = err.message;
      });
    return host;
  }

  #weightOverridesField(path) {
    const host = el("div", "manifest-host");
    host.dataset.configSection = "distance_weights";
    host.appendChild(el("span", "muted small", "Loading…"));
    const initialShape =
      this.#focus?.paramKey ?? this.#uiStore.get("selectedShape") ?? null;
    fetch(`/api/profiles/${encodeURIComponent(this.#profile)}/registry`)
      .then((r) => r.json())
      .then((reg) =>
        mountShapePicker({
          shapes: reg.rerandomize_suggestions ?? Object.keys(this.#getAt(path)),
          activeMap: this.#getAt(path),
          title: "Pick parameter → set distance weight",
          initialShape,
          onChange: (map) => this.#set(path, map),
        }),
      )
      .then((node) => host.replaceChildren(node))
      .catch((err) => {
        host.textContent = err.message;
      });
    return host;
  }

  #registryTargetsField(path) {
    const host = el("div", "manifest-host");
    host.dataset.configSection = "targets";
    const label =
      this.#fileId === "attractor" ? "Loading param registry…" : "Loading rerandomize registry…";
    host.appendChild(el("span", "muted small", label));
    mountRegistryPicker({
      profile: this.#profile,
      activeItems: this.#getAt(path),
      initialTarget:
        this.#focus?.targetEntry ??
        this.#focus?.paramKey ??
        this.#uiStore.get("registryFilter") ??
        null,
      uiStore: this.#uiStore,
      onChange: (items) => this.#set(path, items),
    })
      .then((node) => host.replaceChildren(node))
      .catch((err) => {
        host.textContent = err.message;
      });
    return host;
  }

  async #fetchManifestDefaults(manifestId) {
    const res = await fetch(`/api/manifests/${encodeURIComponent(manifestId)}`);
    if (!res.ok) return {};
    const data = await res.json();
    return data.defaults ?? {};
  }

  #bonePropertiesEditor(path) {
    const box = el("div", "bone-props-editor");
    box.dataset.configSection = "bone_properties";
    const focusProp = this.#focus?.paramKey ?? null;
    const render = async () => {
      const props = this.#getAt(path);
      const defaults = await this.#fetchManifestDefaults("bone_properties");
      box.innerHTML = "";
      box.appendChild(el("p", "chip-hint", "HD eye iris/pupil props and other bone custom properties"));
      const table = el("div", "bone-table");
      for (const [name, spec] of Object.entries(props)) {
        const row = this.#bonePropRow(path, props, name, spec);
        row.dataset.boneProp = name;
        table.appendChild(row);
      }
      box.appendChild(table);
      if (focusProp && props[focusProp]) {
        requestAnimationFrame(() => scrollToConfigTarget(box.querySelector(`[data-bone-prop="${focusProp}"]`)));
      }

      const addRow = el("div", "add-row");
      const sel = el("select", "input");
      sel.appendChild(el("option", "", "Add from catalog…"));
      const catalog = await fetch("/api/manifests/bone_properties").then((r) => r.json());
      for (const item of catalog.items) {
        if (item.id in props) continue;
        const opt = el("option", "", item.id);
        opt.value = item.id;
        sel.appendChild(opt);
      }
      const custom = el("input", "input mono");
      custom.placeholder = "Or type new property name";
      const addBtn = el("button", "btn ghost", "Add property");
      addBtn.type = "button";
      addBtn.onclick = async () => {
        const name = custom.value.trim() || sel.value;
        if (!name || name in props) return;
        const template = defaults[name] ?? { min: 0, max: 1, target_bone: "LeftEyeSocketBind" };
        props[name] = { ...template };
        await fetch("/api/manifests/bone_properties/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids: [name] }),
        });
        this.#set(path, { ...props });
        render();
      };
      addRow.append(sel, custom, addBtn);
      box.appendChild(addRow);
    };
    render();
    return box;
  }

  #bonePropRow(path, props, name, spec) {
    const row = el("div", "bone-row");
    row.appendChild(el("span", "kv-key mono", name));
    const min = el("input", "input small");
    min.type = "number";
    min.step = "any";
    min.value = spec.min ?? 0;
    const max = el("input", "input small");
    max.type = "number";
    max.step = "any";
    max.value = spec.max ?? 1;
    const bone = el("input", "input");
    bone.value = spec.target_bone ?? "";
    bone.placeholder = "target_bone";
    const obj = el("input", "input");
    obj.value = spec.target_object ?? "";
    obj.placeholder = "target_object (optional)";
    const sync = () => {
      props[name] = {
        min: parseFloat(min.value) || 0,
        max: parseFloat(max.value) || 0,
        ...(bone.value.trim() ? { target_bone: bone.value.trim() } : {}),
        ...(obj.value.trim() ? { target_object: obj.value.trim() } : {}),
      };
      if (!bone.value.trim() && !obj.value.trim()) {
        props[name].target_bone = "LeftEyeSocketBind";
      }
      this.#set(path, { ...props });
    };
    min.oninput = max.oninput = bone.oninput = obj.oninput = sync;
    const del = el("button", "btn icon danger", "×");
    del.type = "button";
    del.onclick = () => {
      delete props[name];
      this.#set(path, { ...props });
      this.render();
    };
    row.append(min, el("span", "range-sep", "→"), max, bone, obj, del);
    return row;
  }

  #independentShapesEditor(path) {
    const box = el("div", "indep-editor");
    box.dataset.configSection = "independent_shapes";
    const focusShape = this.#focus?.paramKey ?? null;
    const render = async () => {
      const shapes = this.#getAt(path);
      const defaults = await this.#fetchManifestDefaults("independent_shapes");
      box.innerHTML = "";
      box.appendChild(el("p", "chip-hint", "Always-on shapes outside the variation lottery"));
      const table = el("div", "indep-table");
      for (const [name, cfg] of Object.entries(shapes)) {
        const row = el("div", "indep-row");
        row.dataset.indepShape = name;
        row.appendChild(el("span", "kv-key mono", name));
        const min = el("input", "input small");
        min.type = "number";
        min.step = "any";
        min.value = cfg.min;
        const max = el("input", "input small");
        max.type = "number";
        max.step = "any";
        max.value = cfg.max;
        const sync = () => {
          shapes[name] = {
            min: parseFloat(min.value) || 0,
            max: parseFloat(max.value) || 0,
            mirror_sides: shapes[name].mirror_sides ?? false,
          };
          this.#set(path, { ...shapes });
        };
        min.oninput = max.oninput = sync;
        const mirror = el("label", "switch-row compact");
        const chk = el("input");
        chk.type = "checkbox";
        chk.checked = cfg.mirror_sides ?? false;
        chk.onchange = () => {
          shapes[name].mirror_sides = chk.checked;
          this.#set(path, { ...shapes });
        };
        mirror.append(chk, el("span", "switch-ui"), el("span", "switch-label", "Mirror"));
        const del = el("button", "btn icon danger", "×");
        del.type = "button";
        del.onclick = () => {
          delete shapes[name];
          this.#set(path, { ...shapes });
          render();
        };
        row.append(min, el("span", "range-sep", "→"), max, mirror, del);
        table.appendChild(row);
      }
      box.appendChild(table);

      if (focusShape && shapes[focusShape]) {
        requestAnimationFrame(() => scrollToConfigTarget(box.querySelector(`[data-indep-shape="${focusShape}"]`)));
      }

      const addRow = el("div", "add-row");
      const sel = el("select", "input");
      sel.appendChild(el("option", "", "Add from catalog…"));
      const catalog = await fetch("/api/manifests/independent_shapes").then((r) => r.json());
      for (const item of catalog.items) {
        if (item.id in shapes) continue;
        const opt = el("option", "", item.id);
        opt.value = item.id;
        sel.appendChild(opt);
      }
      const custom = el("input", "input mono");
      custom.placeholder = "Or register new shape";
      const addBtn = el("button", "btn ghost", "Add shape");
      addBtn.type = "button";
      addBtn.onclick = async () => {
        const name = custom.value.trim() || sel.value;
        if (!name || name in shapes) return;
        shapes[name] = { ...(defaults[name] ?? { min: 0, max: 0.3, mirror_sides: false }) };
        await fetch("/api/manifests/independent_shapes/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids: [name] }),
        });
        this.#set(path, { ...shapes });
        render();
      };
      addRow.append(sel, custom, addBtn);
      box.appendChild(addRow);
    };
    render();
    return box;
  }

  #stringList(path) {
    const box = el("div", "list-editor");
    const render = () => {
      const items = this.#getAt(path);
      box.innerHTML = "";
      items.forEach((item, i) => {
        const row = el("div", "list-row");
        const input = el("input", "input");
        input.value = item;
        input.oninput = () => {
          const list = this.#getAt(path);
          list[i] = input.value;
          this.#set(path, [...list]);
        };
        const del = el("button", "btn icon danger", "×");
        del.type = "button";
        del.onclick = () => {
          const list = this.#getAt(path);
          list.splice(i, 1);
          this.#set(path, [...list]);
          render();
        };
        row.append(input, del);
        box.appendChild(row);
      });
      const add = el("button", "btn ghost add-btn", "+ Add item");
      add.type = "button";
      add.onclick = () => {
        const list = this.#getAt(path);
        list.push("");
        this.#set(path, [...list]);
        render();
      };
      box.appendChild(add);
    };
    render();
    return box;
  }

  #numberList(path) {
    const box = el("div", "list-editor");
    const render = () => {
      const items = this.#getAt(path);
      box.innerHTML = "";
      items.forEach((item, i) => {
        const row = el("div", "list-row");
        row.appendChild(this.#numberInput([...path, i], item, "any"));
        const del = el("button", "btn icon danger", "×");
        del.type = "button";
        del.onclick = () => {
          const list = this.#getAt(path);
          list.splice(i, 1);
          this.#set(path, [...list]);
          render();
        };
        row.appendChild(del);
        box.appendChild(row);
      });
      const add = el("button", "btn ghost add-btn", "+ Add");
      add.type = "button";
      add.onclick = () => {
        const list = this.#getAt(path);
        list.push(0);
        this.#set(path, [...list]);
        render();
      };
      box.appendChild(add);
    };
    render();
    return box;
  }

  #colorList(path) {
    const box = el("div", "color-list");
    const render = () => {
      const colors = this.#getAt(path);
      box.innerHTML = "";
      colors.forEach((c, i) => {
        const row = el("div", "color-row");
        const swatch = el("input", "color-swatch");
        swatch.type = "color";
        swatch.value = c.startsWith("#") ? c : "#000000";
        const text = el("input", "input mono");
        text.value = c;
        swatch.oninput = () => {
          text.value = swatch.value;
          const list = this.#getAt(path);
          list[i] = swatch.value;
          this.#set(path, [...list]);
        };
        text.oninput = () => {
          const list = this.#getAt(path);
          list[i] = text.value;
          this.#set(path, [...list]);
        };
        const del = el("button", "btn icon danger", "×");
        del.type = "button";
        del.onclick = () => {
          const list = this.#getAt(path);
          list.splice(i, 1);
          this.#set(path, [...list]);
          render();
        };
        row.append(swatch, text, del);
        box.appendChild(row);
      });
      const add = el("button", "btn ghost add-btn", "+ Add color");
      add.type = "button";
      add.onclick = () => {
        const list = this.#getAt(path);
        list.push("#ffffff");
        this.#set(path, [...list]);
        render();
      };
      box.appendChild(add);
    };
    render();
    return box;
  }

  #overrideMap(path, map, forceRange = false) {
    const box = el("div", "map-editor");
    const search = el("input", "input search");
    search.placeholder = "Filter keys…";
    box.appendChild(search);
    const table = el("div", "kv-table");
    box.appendChild(table);

    const render = (filter = "") => {
      const data = this.#getAt(path);
      table.innerHTML = "";
      const keys = Object.keys(data).filter((k) =>
        k.toLowerCase().includes(filter.toLowerCase()),
      );
      for (const k of keys) {
        table.appendChild(this.#overrideRow(path, k, forceRange));
      }
    };

    search.oninput = () => render(search.value.trim());
    render();

    const addRow = el("div", "add-row");
    const keyIn = el("input", "input");
    keyIn.placeholder = "JointName.channel";
    const addBtn = el("button", "btn ghost", "Add override");
    addBtn.type = "button";
    addBtn.onclick = () => {
      const data = this.#getAt(path);
      const k = keyIn.value.trim();
      if (!k || k in data) return;
      data[k] = forceRange ? { min: -1, max: 1 } : 0.1;
      this.#set(path, { ...data });
      keyIn.value = "";
      render(search.value.trim());
    };
    addRow.append(keyIn, addBtn);
    box.appendChild(addRow);
    return box;
  }

  #overrideRow(path, key, forceRange) {
    const map = this.#getAt(path);
    const val = map[key];
    const row = el("div", "kv-row");
    row.appendChild(el("span", "kv-key mono", key));
    const controls = el("div", "kv-controls");

    if (forceRange || isRangeObj(val)) {
      const min = el("input", "input small");
      min.type = "number";
      min.step = "any";
      min.value = isRangeObj(val) ? val.min : val;
      min.placeholder = "min";
      const max = el("input", "input small");
      max.type = "number";
      max.step = "any";
      max.value = isRangeObj(val) ? val.max : val;
      max.placeholder = "max";
      const sync = () => {
        const data = this.#getAt(path);
        data[key] = {
          min: parseFloat(min.value) || 0,
          max: parseFloat(max.value) || 0,
        };
        this.#set(path, { ...data });
      };
      min.oninput = max.oninput = sync;
      controls.append(min, el("span", "range-sep", "→"), max);
      if (!forceRange) {
        const sym = el("button", "btn ghost tiny", "±");
        sym.type = "button";
        sym.title = "Switch to symmetric";
        sym.onclick = () => {
          const data = this.#getAt(path);
          data[key] = Math.max(Math.abs(data[key].min), Math.abs(data[key].max));
          this.#set(path, { ...data });
          this.render();
        };
        controls.appendChild(sym);
      }
    } else {
      const num = el("input", "input small");
      num.type = "number";
      num.step = "any";
      num.value = val;
      num.oninput = () => {
        const data = this.#getAt(path);
        data[key] = parseFloat(num.value) || 0;
        this.#set(path, { ...data });
      };
      const asym = el("button", "btn ghost tiny", "{min,max}");
      asym.type = "button";
      asym.title = "Switch to asymmetric range";
      asym.onclick = () => {
        const data = this.#getAt(path);
        data[key] = { min: -Math.abs(data[key]), max: Math.abs(data[key]) };
        this.#set(path, { ...data });
        this.render();
      };
      controls.append(num, asym);
    }

    const del = el("button", "btn icon danger", "×");
    del.type = "button";
    del.onclick = () => {
      const data = this.#getAt(path);
      delete data[key];
      this.#set(path, { ...data });
      this.render();
    };
    row.append(controls, del);
    return row;
  }

  #intMap(path, map) {
    const box = el("div", "map-editor");
    const table = el("div", "kv-table compact");
    for (const [k, v] of Object.entries(map)) {
      const row = el("div", "kv-row");
      row.appendChild(el("span", "kv-key mono", k));
      const val = el("input", "input small");
      val.type = "number";
      val.step = "1";
      val.value = v;
      val.oninput = () => {
        map[k] = parseInt(val.value, 10) || 0;
        this.#set(path, { ...map });
      };
      const del = el("button", "btn icon danger", "×");
      del.type = "button";
      del.onclick = () => {
        delete map[k];
        this.#set(path, { ...map });
        this.render();
      };
      row.append(val, del);
      table.appendChild(row);
    }
    box.appendChild(table);
    return box;
  }

  #independentShapes(path, obj) {
    return this.#independentShapesEditor(path);
  }

  #relationalRulesField(path, items) {
    if (!this.#rulesCollapsedInit) {
      if (this.#focus?.ruleIndex != null) {
        this.#rulesFilter = "";
        items.forEach((_, i) => {
          if (i !== this.#focus.ruleIndex) this.#rulesCollapsed.add(i);
        });
      } else if (this.#uiStore.get("rulesCollapsed")?.length) {
        for (const i of this.#uiStore.get("rulesCollapsed")) this.#rulesCollapsed.add(i);
        this.#rulesFilter = this.#uiStore.get("rulesFilter") ?? "";
        this.#rulesMuteFilter = this.#uiStore.get("rulesMuteFilter") ?? "all";
      } else if (items.length > 0) {
        items.forEach((_, i) => this.#rulesCollapsed.add(i));
      }
      this.#rulesCollapsedInit = true;
    }
    const host = el("div", "rules-editor-host");
    host.dataset.configSection = "relational_rules";
    const lintHost = el("div", "constraint-lint-host");
    const rulesHost = el("div", "rules-mount");
    host.append(lintHost, rulesHost);
    void this.#loadParamRegistry().then(() => this.#refreshConstraintLint(lintHost));
    rulesHost.appendChild(this.#mountRelationalRules(path, items, rulesHost));
    return host;
  }

  #mountRelationalRules(path, items, rulesHost) {
    return mountRelationalRulesEditor({
      items,
      collapsed: this.#rulesCollapsed,
      filterText: this.#rulesFilter,
      muteFilter: this.#rulesMuteFilter,
      focusRuleIndex: this.#focus?.ruleIndex ?? null,
      validateRule,
      onCollapsedChange: (indices) => {
        this.#rulesCollapsed.clear();
        for (const i of indices) this.#rulesCollapsed.add(i);
        this.#syncRulesUiState();
      },
      onItemsChange: (next, opts = {}) => {
        this.#set(path, next);
        if (opts.expandIndex != null) this.#rulesCollapsed.delete(opts.expandIndex);
        this.render();
      },
      onFilterChange: (text) => {
        this.#rulesFilter = text;
        this.#syncRulesUiState();
        rulesHost.replaceChildren(this.#mountRelationalRules(path, this.#getAt(path), rulesHost));
      },
      onMuteFilterChange: (mode) => {
        this.#rulesMuteFilter = mode;
        this.#syncRulesUiState();
        rulesHost.replaceChildren(this.#mountRelationalRules(path, this.#getAt(path), rulesHost));
      },
      emptyRule,
      renderRuleBody: (index, item, touch) => this.#renderRuleFields(path, items, index, item, touch),
    });
  }

  #renderRuleFields(path, items, index, item, touch) {
    const wrap = el("div", "rule-fields");
    const titleIn = el("input", "input");
    titleIn.value = item.title ?? "";
    titleIn.placeholder = "Rule title";
    titleIn.oninput = () => {
      item.title = titleIn.value;
      touch();
    };
    wrap.appendChild(this.#fieldWrap("title", titleIn));

    const typeSel = el("select", "input");
    for (const t of RULE_TYPES) {
      const opt = el("option", "", t);
      opt.value = t;
      if (item.type === t) opt.selected = true;
      typeSel.appendChild(opt);
    }

    const body = el("div", "field-grid rule-typed-body");
    const renderBody = () => {
      this.#renderTypedRuleBody(item, [...path, index], touch, body);
    };

    typeSel.onchange = () => {
      const newType = typeSel.value;
      if (newType === item.type) return;
      const lost = migrationDataLoss(item, newType);
      if (lost.length && !window.confirm(`Changing type removes: ${lost.join(", ")}. Continue?`)) {
        typeSel.value = item.type;
        return;
      }
      const migrated = migrateRuleType(item, newType);
      for (const k of Object.keys(item)) delete item[k];
      Object.assign(item, migrated);
      help.textContent = ruleTypeDescription(item.type);
      helpHint.textContent = ruleTypeHelp(item.type);
      helpHint.classList.toggle("hidden", !ruleTypeHelp(item.type));
      renderBody();
      touch();
    };
    wrap.appendChild(this.#fieldWrap("type", typeSel));

    const help = el("p", "rule-type-help muted small", ruleTypeDescription(item.type));
    wrap.appendChild(help);
    const helpHint = el("p", "rule-type-hint chip-hint" + (ruleTypeHelp(item.type) ? "" : " hidden"), ruleTypeHelp(item.type));
    wrap.appendChild(helpHint);

    renderBody();
    wrap.appendChild(body);

    const validation = validateRule(item);
    if (validation.warnings.length) {
      for (const w of validation.warnings) {
        wrap.appendChild(el("p", "chip-hint", w));
      }
    }
    return wrap;
  }

  #renderTypedRuleBody(item, basePath, touch, bodyEl) {
    bodyEl.innerHTML = "";
    const fields = schemaFields(item.type);
    for (const field of fields) {
      const fieldPath = [...basePath, field.key];
      let control;
      const sync = (val) => {
        if (val === undefined) delete item[field.key];
        else item[field.key] = val;
        this.#set(basePath.slice(0, -1), this.#getAt(basePath.slice(0, -1)));
        touch();
      };

      switch (field.widget) {
        case "param":
          control = mountInlineParamInput({
            value: item[field.key] ?? "",
            suggestions: this.#paramSuggestions,
            staleKeys: this.#staleKeys,
            onChange: (v) => {
              item[field.key] = v;
              touch();
            },
          });
          break;
        case "param_list":
          if (!Array.isArray(item[field.key])) item[field.key] = [...field.default];
          control = mountInlineParamList({
            values: item[field.key],
            suggestions: this.#paramSuggestions,
            staleKeys: this.#staleKeys,
            minItems: field.minItems ?? 1,
            onChange: (next) => {
              item[field.key] = next;
              touch();
            },
          });
          break;
        case "number":
          control = this.#numberInput(fieldPath, item[field.key] ?? field.default ?? 0);
          break;
        case "number_optional": {
          const row = el("div", "optional-num-row");
          const num = el("input", "input");
          num.type = "number";
          num.step = "any";
          num.placeholder = "optional";
          num.value = item[field.key] ?? "";
          num.oninput = () => {
            if (num.value === "") {
              delete item[field.key];
            } else {
              item[field.key] = parseFloat(num.value);
            }
            touch();
          };
          row.appendChild(num);
          control = row;
          break;
        }
        case "enum": {
          const sel = el("select", "input");
          for (const opt of field.options) {
            const o = el("option", "", opt.label);
            o.value = String(opt.value);
            if (item[field.key] === opt.value || String(item[field.key]) === String(opt.value)) {
              o.selected = true;
            }
            sel.appendChild(o);
          }
          sel.onchange = () => {
            const raw = sel.value;
            item[field.key] = raw === "-1" || raw === "1" ? parseInt(raw, 10) : raw;
            touch();
          };
          control = sel;
          break;
        }
        case "condition":
          if (!item[field.key] || typeof item[field.key] !== "object") {
            item[field.key] = field.default ? JSON.parse(JSON.stringify(field.default)) : { param: "" };
          }
          control = this.#conditionEditor(fieldPath, item[field.key], true);
          break;
        case "clamp_spec":
          if (!item[field.key] || typeof item[field.key] !== "object") {
            item[field.key] = field.default ? JSON.parse(JSON.stringify(field.default)) : { param: "" };
          }
          control = this.#clampSpecEditor(fieldPath, item[field.key], true);
          break;
        case "bias_drivers":
          if (!Array.isArray(item[field.key])) item[field.key] = [];
          control = this.#biasDriversEditor(fieldPath, item[field.key], true);
          break;
        default:
          control = this.#inlineValue(fieldPath, item[field.key], field.key, item.type);
      }
      bodyEl.appendChild(this.#fieldWrap(field.key, control, field.label));
    }
  }

  #objectArray(path, items, kind) {
    const box = el("div", "card-list");
    const render = () => {
      box.innerHTML = "";
      items.forEach((item, i) => {
        box.appendChild(this.#objectCard(path, items, i, item, kind));
      });
      const add = el("button", "btn ghost add-btn", kind === "drivers" ? "+ Add driver" : "+ Add rule");
      add.type = "button";
      add.onclick = () => {
        items.push(kind === "drivers" ? emptyDriver() : emptyRule());
        this.#set(path, [...items]);
        render();
      };
      box.appendChild(add);
    };
    render();
    return box;
  }

  #objectCard(path, items, index, item, kind) {
    const card = el("div", "rule-card" + (item.muted ? " is-muted" : ""));
    const head = el("div", "card-head");
    const title =
      kind === "drivers"
        ? `${item.target?.object}.${item.target?.property} ← ${item.source?.object}`
        : item.title || `Rule ${index + 1}`;
    head.appendChild(el("strong", "", title));
    if (item.type) head.appendChild(el("span", "type-badge", item.type));
    if (item.muted) head.appendChild(el("span", "mute-badge", "MUTED"));
    if (kind !== "drivers") {
      const muteLabel = el("label", "switch-row compact mute-toggle");
      const muteChk = el("input");
      muteChk.type = "checkbox";
      muteChk.checked = !!item.muted;
      muteChk.onchange = () => {
        item.muted = muteChk.checked;
        card.classList.toggle("is-muted", item.muted);
        this.#set(path, [...items]);
        this.render();
      };
      muteLabel.append(muteChk, el("span", "switch-ui"), el("span", "switch-label", "Muted"));
      head.appendChild(muteLabel);
    }
    const del = el("button", "btn icon danger", "×");
    del.type = "button";
    del.onclick = () => {
      items.splice(index, 1);
      this.#set(path, [...items]);
      this.render();
    };
    head.appendChild(del);
    card.appendChild(head);

    if (kind === "drivers") {
      card.appendChild(this.#driverEndpoint("Target", item.target, (v) => {
        item.target = v;
        this.#set(path, [...items]);
      }));
      card.appendChild(this.#driverEndpoint("Source", item.source, (v) => {
        item.source = v;
        this.#set(path, [...items]);
      }));
      if ("expression" in item) {
        const expr = el("input", "input");
        expr.value = item.expression ?? "var";
        expr.placeholder = "expression";
        expr.oninput = () => {
          item.expression = expr.value;
          this.#set(path, [...items]);
        };
        card.appendChild(this.#fieldWrap("expression", expr));
      }
    } else {
      const titleIn = el("input", "input");
      titleIn.value = item.title ?? "";
      titleIn.placeholder = "Rule title";
      titleIn.oninput = () => {
        item.title = titleIn.value;
        this.#set(path, [...items]);
      };
      card.appendChild(this.#fieldWrap("title", titleIn));

      const typeSel = el("select", "input");
      for (const t of RULE_TYPES) {
        const opt = el("option", "", t);
        opt.value = t;
        if (item.type === t) opt.selected = true;
        typeSel.appendChild(opt);
      }
      typeSel.onchange = () => {
        item.type = typeSel.value;
        this.#set(path, [...items]);
      };
      card.appendChild(this.#fieldWrap("type", typeSel));

      const body = el("div", "field-grid");
      for (const [k, v] of Object.entries(item)) {
        if (k === "title" || k === "type" || k === "muted") continue;
        body.appendChild(this.#fieldWrap(k, this.#inlineValue([...path, index, k], v, k, item.type)));
      }
      card.appendChild(body);
    }
    return card;
  }

  #driverEndpoint(label, ep, setEp) {
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

  #inlineValue(path, value, key, ruleType = "") {
    if (key === "condition" && value && typeof value === "object") {
      return this.#conditionEditor(path, value);
    }
    if ((key === "if" || key === "and" || key === "then_clamp") && value && typeof value === "object") {
      return this.#clampSpecEditor(path, value);
    }
    if (key === "drivers" && Array.isArray(value)) {
      return this.#biasDriversEditor(path, value);
    }
    if (typeof value === "boolean") return this.#toggle(path, value);
    if (typeof value === "number") return this.#numberInput(path, value);
    if (Array.isArray(value)) {
      if (value.length === 2 && value.every((x) => typeof x === "number")) {
        return this.#inlineRangePair(path, value);
      }
      if (value.every((x) => typeof x === "string")) return this.#stringList(path);
      if (value.every((x) => typeof x === "number")) return this.#numberList(path);
      if (value.every((x) => x && typeof x === "object" && "param" in x)) {
        return this.#biasDriversEditor(path, value);
      }
      return el("pre", "json-fallback", JSON.stringify(value, null, 2));
    }
    if (value && typeof value === "object") {
      if (isRangeObj(value)) {
        return this.#inlineRangePair(path, [value.min, value.max], true);
      }
      if ("param" in value && ("above" in value || "below" in value)) {
        return this.#conditionEditor(path, value);
      }
      if ("param" in value && ("min" in value || "max" in value)) {
        return this.#clampSpecEditor(path, value);
      }
      const grid = el("div", "field-grid tight");
      for (const [k, v] of Object.entries(value)) {
        grid.appendChild(this.#fieldWrap(k, this.#inlineValue([...path, k], v, k, ruleType)));
      }
      return grid;
    }
    const input = el("input", "input");
    input.value = value ?? "";
    input.oninput = () => this.#set(path, input.value);
    return input;
  }

  #inlineRangePair(path, pair, asRangeObj = false) {
    const row = el("div", "range-pair");
    const a = el("input", "input small");
    a.type = "number";
    a.step = "any";
    a.value = pair[0];
    const b = el("input", "input small");
    b.type = "number";
    b.step = "any";
    b.value = pair[1];
    const sync = () => {
      const lo = parseFloat(a.value) || 0;
      const hi = parseFloat(b.value) || 0;
      this.#set(path, asRangeObj ? { min: lo, max: hi } : [lo, hi]);
    };
    a.oninput = b.oninput = sync;
    row.append(a, el("span", "range-sep", "→"), b);
    return row;
  }

  #conditionEditor(path, cond, usePicker = false) {
    const box = el("div", "mini-grid");
    const setCond = () => this.#set(path, { ...cond });
    let param;
    if (usePicker) {
      param = mountInlineParamInput({
        value: cond.param ?? "",
        suggestions: this.#paramSuggestions,
        staleKeys: this.#staleKeys,
        placeholder: "param",
        onChange: (v) => {
          cond.param = v;
          setCond();
        },
      });
    } else {
      param = el("input", "input");
      param.value = cond.param ?? "";
      param.placeholder = "param";
      param.oninput = () => {
        cond.param = param.value;
        setCond();
      };
    }
    const above = el("input", "input small");
    above.type = "number";
    above.step = "any";
    above.value = cond.above ?? "";
    above.placeholder = "above";
    above.oninput = () => {
      if (above.value === "") delete cond.above;
      else cond.above = parseFloat(above.value);
      setCond();
    };
    const below = el("input", "input small");
    below.type = "number";
    below.step = "any";
    below.value = cond.below ?? "";
    below.placeholder = "below";
    below.oninput = () => {
      if (below.value === "") delete cond.below;
      else cond.below = parseFloat(below.value);
      setCond();
    };
    box.append(param, above, below);
    return box;
  }

  #clampSpecEditor(path, spec, usePicker = false) {
    const box = el("div", "mini-grid");
    const setSpec = () => this.#set(path, { ...spec });
    let param;
    if (usePicker) {
      param = mountInlineParamInput({
        value: spec.param ?? "",
        suggestions: this.#paramSuggestions,
        staleKeys: this.#staleKeys,
        onChange: (v) => {
          spec.param = v;
          setSpec();
        },
      });
    } else {
      param = el("input", "input");
      param.value = spec.param ?? "";
      param.oninput = () => {
        spec.param = param.value;
        setSpec();
      };
    }
    const min = el("input", "input small");
    min.type = "number";
    min.step = "any";
    min.value = spec.min ?? "";
    min.placeholder = "min";
    min.oninput = () => {
      if (min.value === "") delete spec.min;
      else spec.min = parseFloat(min.value);
      setSpec();
    };
    const max = el("input", "input small");
    max.type = "number";
    max.step = "any";
    max.value = spec.max ?? "";
    max.placeholder = "max";
    max.oninput = () => {
      if (max.value === "") delete spec.max;
      else spec.max = parseFloat(max.value);
      setSpec();
    };
    box.append(param, min, max);
    return box;
  }

  #biasDriversEditor(path, drivers, labeled = false) {
    const box = el("div", "driver-bias-list");
    const render = () => {
      box.innerHTML = "";
      if (labeled) {
        const head = el("div", "bias-driver-head muted small");
        head.append("Param", el("span", "", "Input range"), el("span", "", "Output map"), el("span", "", ""));
        box.appendChild(head);
      }
      drivers.forEach((d, i) => {
        const row = el("div", "bias-driver-row");
        const param = mountInlineParamInput({
          value: d.param ?? "",
          suggestions: this.#paramSuggestions,
          staleKeys: this.#staleKeys,
          onChange: (v) => {
            drivers[i].param = v;
            this.#set(path, [...drivers]);
          },
        });
        const range = el("div", "range-pair");
        const r0 = el("input", "input small");
        r0.type = "number";
        r0.step = "any";
        r0.value = d.range?.[0] ?? 0;
        const r1 = el("input", "input small");
        r1.type = "number";
        r1.step = "any";
        r1.value = d.range?.[1] ?? 0;
        const m0 = el("input", "input small");
        m0.type = "number";
        m0.step = "any";
        m0.value = d.map?.[0] ?? 0;
        const m1 = el("input", "input small");
        m1.type = "number";
        m1.step = "any";
        m1.value = d.map?.[1] ?? 0;
        const sync = () => {
          drivers[i].range = [parseFloat(r0.value) || 0, parseFloat(r1.value) || 0];
          drivers[i].map = [parseFloat(m0.value) || 0, parseFloat(m1.value) || 0];
          this.#set(path, [...drivers]);
        };
        r0.oninput = r1.oninput = m0.oninput = m1.oninput = sync;
        range.append(r0, el("span", "range-sep", "→"), r1);
        const map = el("div", "range-pair");
        map.append(m0, el("span", "range-sep", "→"), m1);
        const del = el("button", "btn icon danger", "×");
        del.type = "button";
        del.onclick = () => {
          drivers.splice(i, 1);
          this.#set(path, [...drivers]);
          render();
        };
        if (labeled) {
          row.append(param, range, map, del);
        } else {
          row.append(param, el("span", "muted small", "range"), range, el("span", "muted small", "map"), map, del);
        }
        box.appendChild(row);
      });
      const add = el("button", "btn ghost add-btn", "+ Add driver");
      add.type = "button";
      add.onclick = () => {
        drivers.push({ param: "", range: [0, 1], map: [0, 1] });
        this.#set(path, [...drivers]);
        render();
      };
      box.appendChild(add);
    };
    render();
    return box;
  }

  #channels(path) {
    const box = el("div", "card-list");
    const render = async () => {
      const channels = this.#getAt(path);
      box.innerHTML = "";
      for (const [name, cfg] of Object.entries(channels)) {
        const card = el("div", "rule-card channel-card");
        const head = el("div", "card-head");
        head.appendChild(el("strong", "", name));
        head.appendChild(el("span", "type-badge", cfg.enabled ? "on" : "off"));
        const del = el("button", "btn icon danger", "×");
        del.type = "button";
        del.onclick = () => {
          delete channels[name];
          this.#set(path, { ...channels });
          render();
        };
        head.appendChild(del);
        card.appendChild(head);
        const grid = el("div", "field-grid");
        for (const [k, v] of Object.entries(cfg)) {
          grid.appendChild(this.#fieldWrap(k, this.#inlineValue([...path, name, k], v, k)));
        }
        card.appendChild(grid);
        box.appendChild(card);
      }

      const addRow = el("div", "add-row");
      const sel = el("select", "input");
      sel.appendChild(el("option", "", "Add channel…"));
      const catalog = await fetch("/api/manifests/texture_channels").then((r) => r.json());
      for (const item of catalog.items) {
        if (item.id in channels) continue;
        const opt = el("option", "", item.id);
        opt.value = item.id;
        sel.appendChild(opt);
      }
      const custom = el("input", "input");
      custom.placeholder = "New channel key";
      const addBtn = el("button", "btn ghost", "Add channel");
      addBtn.type = "button";
      addBtn.onclick = async () => {
        const name = custom.value.trim() || sel.value;
        if (!name || name in channels) return;
        channels[name] = {
          pool_path: `input-pipeline/texture/${name}`,
          sequence_path: `output-pipeline/${name}_sequence`,
          node_name: `${name}-sequence`,
          percentage: 1.0,
          enabled: true,
        };
        await fetch("/api/manifests/texture_channels/register", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ ids: [name] }),
        });
        this.#set(path, { ...channels });
        render();
      };
      addRow.append(sel, custom, addBtn);
      box.appendChild(addRow);
    };
    render();
    return box;
  }

  #genericArray(path, items) {
    const pre = el("textarea", "input json-area");
    pre.value = JSON.stringify(items, null, 2);
    pre.onchange = () => {
      try {
        this.#set(path, JSON.parse(pre.value));
        this.render();
      } catch {
        /* keep editing */
      }
    };
    return pre;
  }
}

function el(tag, cls = "", text = "") {
  const node = document.createElement(tag);
  if (cls) node.className = cls;
  if (text) node.textContent = text;
  return node;
}

export { emptyRule } from "./rule-schemas.js";

function emptyDriver() {
  return {
    target: { object: "", bone: null, property: "", shape_key: false },
    source: { object: "", bone: null, property: "", shape_key: false },
  };
}

export function mountForm(container, data, onChange, options = {}) {
  return new ConfigForm(container, data, onChange, options);
}
