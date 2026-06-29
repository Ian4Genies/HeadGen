/** Searchable grouped parameter picker for Value Trace. */

import { restoreScroll } from "./view-state.js";

const RECENT_KEY = "sh_trace_recent";
const GROUP_LABELS = {
  joint: "Joint axes",
  variation_shapes: "Variation shapes",
  expression_shapes: "Expression shapes",
  independent_shapes: "Independent shapes",
  bone_properties: "Bone properties",
};

function el(tag, cls = "", text = "") {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text) n.textContent = text;
  return n;
}

function loadRecent() {
  try {
    return JSON.parse(localStorage.getItem(RECENT_KEY) || "[]");
  } catch {
    return [];
  }
}

function pushRecent(key) {
  const list = loadRecent().filter((k) => k !== key);
  list.unshift(key);
  localStorage.setItem(RECENT_KEY, JSON.stringify(list.slice(0, 5)));
}

export function mountParamPicker(container, { profile, selectedKey = "", onSelect }) {
  let catalog = null;
  let filter = "";
  let focusIndex = 0;
  let flatItems = [];
  const collapsedGroups = new Set();

  const isSearching = () => filter.trim().length > 0;

  const toggleGroup = (groupId) => {
    if (collapsedGroups.has(groupId)) collapsedGroups.delete(groupId);
    else collapsedGroups.add(groupId);
    render();
  };

  const groupHead = (groupId, label, count) => {
    const collapsed = !isSearching() && collapsedGroups.has(groupId);
    const head = el("button", "trace-group-head" + (collapsed ? " collapsed" : ""));
    head.type = "button";
    head.append(
      el("span", "trace-group-chevron", collapsed ? "▸" : "▾"),
      el("span", "trace-group-label", label),
      el("span", "trace-group-count", String(count)),
    );
    head.onclick = () => toggleGroup(groupId);
    return head;
  };

  const search = el("input", "input trace-search");
  search.placeholder = "Search parameters…";
  search.autocomplete = "off";

  const listHost = el("div", "trace-param-list");

  const buildFlat = () => {
    if (!catalog) return [];
    const out = [];
    for (const [groupId, items] of Object.entries(catalog.groups)) {
      for (const item of items) {
        out.push({ ...item, groupId, groupLabel: GROUP_LABELS[groupId] || groupId });
      }
    }
    return out;
  };

  const filtered = () => {
    const q = filter.trim().toLowerCase();
    if (!q) return flatItems;
    return flatItems.filter(
      (it) =>
        it.key.toLowerCase().includes(q) ||
        it.kind?.includes(q) ||
        it.feature_group?.includes(q) ||
        it.groupLabel?.toLowerCase().includes(q),
    );
  };

  const row = (it, idx) => {
    const btn = el(
      "button",
      "trace-param-row" +
        (it.key === selectedKey ? " active" : "") +
        (idx === focusIndex ? " focused" : ""),
    );
    btn.type = "button";
    btn.dataset.key = it.key;
    btn.append(
      el("span", "trace-param-key mono", it.key),
      el("span", "trace-param-sub", it.feature_group || it.kind),
    );
    btn.onclick = () => pick(it.key);
    return btn;
  };

  const pick = (key) => {
    pushRecent(key);
    selectedKey = key;
    onSelect(key);
    render();
  };

  const buildVisible = (items) => {
    const visible = [];
    const recent = loadRecent().filter((k) => flatItems.some((it) => it.key === k));
    if (!isSearching() && recent.length && !collapsedGroups.has("__recent__")) {
      for (const key of recent) {
        const it = flatItems.find((x) => x.key === key);
        if (it) visible.push(it);
      }
    }
    const groupOrder = catalog
      ? Object.keys(catalog.groups)
      : [...new Set(items.map((it) => it.groupId))];
    for (const groupId of groupOrder) {
      if (!isSearching() && collapsedGroups.has(groupId)) continue;
      for (const it of items.filter((x) => x.groupId === groupId)) visible.push(it);
    }
    return visible;
  };

  const render = () => {
    listHost.innerHTML = "";
    const items = filtered();
    if (!items.length) {
      listHost.appendChild(el("p", "muted small", "No parameters match"));
      return;
    }

    let idx = 0;
    const recent = loadRecent().filter((k) => flatItems.some((it) => it.key === k));
    if (!isSearching() && recent.length) {
      const recentItems = recent
        .map((key) => flatItems.find((x) => x.key === key))
        .filter(Boolean);
      listHost.appendChild(groupHead("__recent__", "Recent", recentItems.length));
      if (!collapsedGroups.has("__recent__")) {
        for (const it of recentItems) listHost.appendChild(row(it, idx++));
      }
    }

    const groupOrder = catalog
      ? Object.keys(catalog.groups)
      : [...new Set(items.map((it) => it.groupId))];

    for (const groupId of groupOrder) {
      const groupItems = items.filter((it) => it.groupId === groupId);
      if (!groupItems.length) continue;
      listHost.appendChild(groupHead(groupId, GROUP_LABELS[groupId] || groupId, groupItems.length));
      if (isSearching() || !collapsedGroups.has(groupId)) {
        for (const it of groupItems) listHost.appendChild(row(it, idx++));
      }
    }

    const visible = buildVisible(items);
    if (focusIndex >= visible.length) focusIndex = Math.max(0, visible.length - 1);
  };

  search.oninput = () => {
    filter = search.value;
    focusIndex = 0;
    render();
  };

  search.onkeydown = (e) => {
    const visible = buildVisible(filtered());
    if (e.key === "ArrowDown") {
      e.preventDefault();
      focusIndex = Math.min(focusIndex + 1, visible.length - 1);
      render();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      focusIndex = Math.max(focusIndex - 1, 0);
      render();
    } else if (e.key === "Enter" && visible[focusIndex]) {
      e.preventDefault();
      pick(visible[focusIndex].key);
    }
  };

  container.innerHTML = "";
  container.append(search, listHost);

  return {
    async load() {
      const res = await fetch(`/api/profiles/${encodeURIComponent(profile)}/trace/catalog`);
      if (!res.ok) throw new Error(await res.text());
      catalog = await res.json();
      flatItems = buildFlat();
      render();
    },
    setSelected(key) {
      selectedKey = key;
      render();
    },
    focusSearch() {
      search.focus();
    },
    exportViewState() {
      return {
        selectedKey,
        filter,
        focusIndex,
        listScrollTop: listHost.scrollTop,
        collapsedGroups: [...collapsedGroups],
      };
    },
    restoreState(state) {
      if (!state) return;
      selectedKey = state.selectedKey ?? selectedKey;
      filter = state.filter ?? "";
      focusIndex = state.focusIndex ?? 0;
      collapsedGroups.clear();
      for (const g of state.collapsedGroups ?? []) collapsedGroups.add(g);
      search.value = filter;
      render();
      restoreScroll(listHost, state.listScrollTop ?? 0);
    },
  };
}
