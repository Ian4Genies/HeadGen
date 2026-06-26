/** Collapsible relational-rules list for constraints.json. */

import { RULE_TYPES } from "./meta.js";

function el(tag, cls = "", text = "") {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text) n.textContent = text;
  return n;
}

export function ruleSummary(item) {
  const bits = [];
  const push = (v) => {
    if (v !== undefined && v !== null && v !== "") bits.push(String(v));
  };
  push(item.target);
  push(item.source);
  if (item.floor && item.ceiling) bits.push(`${item.floor} ↔ ${item.ceiling}`);
  else {
    push(item.floor);
    push(item.ceiling);
  }
  if (item.params?.length) bits.push(item.params.join(", "));
  if (item.numerator && item.denominator) bits.push(`${item.numerator} / ${item.denominator}`);
  if (item.param_a && item.param_b) bits.push(`${item.param_a} × ${item.param_b}`);
  if (item.condition?.param) bits.push(`if ${item.condition.param}`);
  if (item.direction) bits.push(item.direction);
  return bits.slice(0, 4).join(" · ");
}

export function ruleSearchText(item) {
  return [
    item.title,
    item.type,
    item.target,
    item.source,
    item.floor,
    item.ceiling,
    item.numerator,
    item.denominator,
    item.param_a,
    item.param_b,
    ...(item.params ?? []),
    item.condition?.param,
  ]
    .filter(Boolean)
    .join(" ")
    .toLowerCase();
}

export function reindexCollapsedSet(set, removedIndex) {
  const next = new Set();
  for (const i of set) {
    if (i < removedIndex) next.add(i);
    else if (i > removedIndex) next.add(i - 1);
  }
  set.clear();
  for (const i of next) set.add(i);
}

import { scrollToConfigTarget } from "./config-focus.js";

export function mountRelationalRulesEditor({
  items,
  collapsed,
  filterText,
  muteFilter,
  onItemsChange,
  onFilterChange,
  onMuteFilterChange,
  onCollapsedChange,
  renderRuleBody,
  emptyRule,
  focusRuleIndex,
}) {
  const root = el("div", "rules-editor");

  const syncItems = (next) => onItemsChange(next);

  const visibleIndices = () => {
    const q = filterText.trim().toLowerCase();
    return items
      .map((item, i) => {
        if (focusRuleIndex != null && i === focusRuleIndex) return i;
        if (muteFilter === "active" && item.muted) return -1;
        if (muteFilter === "muted" && !item.muted) return -1;
        if (q && !ruleSearchText(item).includes(q)) return -1;
        return i;
      })
      .filter((i) => i >= 0);
  };

  const syncCollapsed = () => onCollapsedChange?.([...collapsed]);

  const renderToolbar = () => {
    const bar = el("div", "rules-toolbar");
    const search = el("input", "input search");
    search.placeholder = "Filter rules (title, type, target, params)…";
    search.value = filterText;
    search.oninput = () => onFilterChange(search.value);

    const expandAll = el("button", "btn ghost tiny", "Expand all");
    expandAll.type = "button";
    expandAll.onclick = () => {
      collapsed.clear();
      syncCollapsed();
      render();
    };

    const collapseAll = el("button", "btn ghost tiny", "Collapse all");
    collapseAll.type = "button";
    collapseAll.onclick = () => {
      collapsed.clear();
      items.forEach((_, i) => collapsed.add(i));
      syncCollapsed();
      render();
    };

    const muteSel = el("select", "input tiny mute-filter");
    for (const [val, label] of [
      ["all", "All rules"],
      ["active", "Active only"],
      ["muted", "Muted only"],
    ]) {
      const opt = el("option", "", label);
      opt.value = val;
      if (muteFilter === val) opt.selected = true;
      muteSel.appendChild(opt);
    }
    muteSel.onchange = () => onMuteFilterChange(muteSel.value);

    const active = items.filter((r) => !r.muted).length;
    const muted = items.length - active;
    const stats = el(
      "span",
      "rules-stats",
      `${items.length} rules · ${active} active · ${muted} muted`,
    );

    bar.append(search, expandAll, collapseAll, muteSel, stats);
    return bar;
  };

  const toggleCollapsed = (index) => {
    if (collapsed.has(index)) collapsed.delete(index);
    else collapsed.add(index);
    syncCollapsed();
  };

  const renderCard = (index, item) => {
    const isCollapsed = collapsed.has(index);
    const card = el(
      "div",
      `rule-card ${isCollapsed ? "collapsed" : "expanded"}` + (item.muted ? " is-muted" : ""),
    );
    card.dataset.ruleIndex = String(index);

    const head = el("div", "card-head rule-card-head");
    const chevron = el("span", "rule-card-toggle", isCollapsed ? "▸" : "▾");
    head.appendChild(chevron);

    const title = item.title || `Rule ${index + 1}`;
    head.appendChild(el("strong", "rule-card-title", title));
    if (item.type) head.appendChild(el("span", "type-badge", item.type));
    if (item.muted) head.appendChild(el("span", "mute-badge", "MUTED"));

    const summary = ruleSummary(item);
    if (summary) head.appendChild(el("span", "rule-card-summary mono", summary));

    const muteLabel = el("label", "switch-row compact mute-toggle");
    const muteChk = el("input");
    muteChk.type = "checkbox";
    muteChk.checked = !!item.muted;
    muteChk.onchange = (e) => {
      e.stopPropagation();
      item.muted = muteChk.checked;
      syncItems([...items]);
      render();
    };
    muteLabel.append(muteChk, el("span", "switch-ui"), el("span", "switch-label", "Muted"));
    head.appendChild(muteLabel);

    const del = el("button", "btn icon danger", "×");
    del.type = "button";
    del.onclick = (e) => {
      e.stopPropagation();
      const next = [...items];
      next.splice(index, 1);
      reindexCollapsedSet(collapsed, index);
      syncItems(next);
      render();
    };
    head.appendChild(del);

    head.onclick = (e) => {
      if (e.target.closest("button, label, input, select")) return;
      toggleCollapsed(index);
      render();
    };

    card.appendChild(head);

    const body = el("div", "rule-card-body");
    body.appendChild(renderRuleBody(index, item, () => syncItems([...items])));
    card.appendChild(body);

    return card;
  };

  const render = () => {
    root.innerHTML = "";
    root.appendChild(renderToolbar());

    const list = el("div", "card-list");
    const visible = visibleIndices();
    if (!visible.length) {
      list.appendChild(el("p", "muted small rules-empty", "No rules match the current filter."));
    } else {
      for (const i of visible) {
        list.appendChild(renderCard(i, items[i]));
      }
    }

    const add = el("button", "btn ghost add-btn", "+ Add rule");
    add.type = "button";
    add.onclick = () => {
      const next = [...items, emptyRule()];
      syncItems(next);
      render();
    };
    list.appendChild(add);
    root.appendChild(list);

    if (focusRuleIndex != null) {
      requestAnimationFrame(() => {
        scrollToConfigTarget(root.querySelector(`[data-rule-index="${focusRuleIndex}"]`));
      });
    }
  };

  render();
  return root;
}

/** Read-only rule card for Value Trace constraints stage. */
export function mountRuleCardReadOnly(entry, { index = 0, writes = true, onOpenInConfig } = {}) {
  const r = entry.rule ?? entry;
  const card = el(
    "div",
    `rule-card collapsed trace-rule-card${r.muted || entry.muted ? " is-muted" : ""}${writes ? "" : " read-only-ref"}`,
  );
  card.dataset.ruleIndex = String(entry.index ?? index);
  const head = el("div", "card-head rule-card-head");
  head.appendChild(el("strong", "rule-card-title", r.title || `Rule ${index + 1}`));
  if (r.type) head.appendChild(el("span", "type-badge", r.type));
  if (r.muted || entry.muted) head.appendChild(el("span", "mute-badge", "MUTED"));
  head.appendChild(el("span", "rule-card-summary mono", ruleSummary(r)));
  if (!writes) head.appendChild(el("span", "ref-badge", "reads only"));
  if (onOpenInConfig) {
    const openBtn = el("button", "btn ghost tiny", "Open in Config →");
    openBtn.type = "button";
    openBtn.onclick = (e) => {
      e.stopPropagation();
      onOpenInConfig(entry);
    };
    head.appendChild(openBtn);
  }
  card.appendChild(head);
  return card;
}

export { RULE_TYPES };
