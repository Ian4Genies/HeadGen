/** Searchable grouped parameter picker for Value Trace. */

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

  const render = () => {
    listHost.innerHTML = "";
    const items = filtered();
    if (focusIndex >= items.length) focusIndex = Math.max(0, items.length - 1);

    const recent = loadRecent().filter((k) => flatItems.some((it) => it.key === k));
    if (!filter && recent.length) {
      listHost.appendChild(el("p", "trace-group-title", "Recent"));
      for (const key of recent) {
        const it = flatItems.find((x) => x.key === key);
        if (it) listHost.appendChild(row(it, items.indexOf(it)));
      }
    }

    let lastGroup = null;
    for (let i = 0; i < items.length; i++) {
      const it = items[i];
      if (it.groupId !== lastGroup) {
        listHost.appendChild(el("p", "trace-group-title", it.groupLabel));
        lastGroup = it.groupId;
      }
      listHost.appendChild(row(it, i));
    }

    if (!items.length) listHost.appendChild(el("p", "muted small", "No parameters match"));
  };

  search.oninput = () => {
    filter = search.value;
    focusIndex = 0;
    render();
  };

  search.onkeydown = (e) => {
    const items = filtered();
    if (e.key === "ArrowDown") {
      e.preventDefault();
      focusIndex = Math.min(focusIndex + 1, items.length - 1);
      render();
    } else if (e.key === "ArrowUp") {
      e.preventDefault();
      focusIndex = Math.max(focusIndex - 1, 0);
      render();
    } else if (e.key === "Enter" && items[focusIndex]) {
      e.preventDefault();
      pick(items[focusIndex].key);
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
  };
}
