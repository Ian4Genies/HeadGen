/** Compact searchable param combobox for constraint rule fields. */

function el(tag, cls = "", text = "") {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text) n.textContent = text;
  return n;
}

export function mountInlineParamInput({
  value = "",
  suggestions = [],
  staleKeys = null,
  placeholder = "Parameter key",
  onChange,
}) {
  const wrap = el("div", "inline-param-input");
  const input = el("input", "input");
  input.value = value ?? "";
  input.placeholder = placeholder;
  input.autocomplete = "off";

  const drop = el("div", "inline-param-drop hidden");
  let open = false;

  const isStale = (key) => staleKeys instanceof Set && key && staleKeys.has(key);

  const filtered = (q) => {
    const query = q.trim().toLowerCase();
    if (!query) return suggestions.slice(0, 40);
    return suggestions.filter((s) => s.toLowerCase().includes(query)).slice(0, 40);
  };

  const close = () => {
    open = false;
    drop.classList.add("hidden");
  };

  const renderDrop = () => {
    drop.innerHTML = "";
    const items = filtered(input.value);
    if (!items.length) {
      drop.appendChild(el("p", "muted small inline-param-empty", "No matches"));
      return;
    }
    for (const key of items) {
      const btn = el("button", "inline-param-opt mono" + (isStale(key) ? " is-stale" : ""), key);
      btn.type = "button";
      btn.onclick = () => {
        input.value = key;
        onChange(key);
        close();
      };
      drop.appendChild(btn);
    }
  };

  const openDrop = () => {
    open = true;
    drop.classList.remove("hidden");
    renderDrop();
  };

  input.oninput = () => {
    onChange(input.value);
    if (isStale(input.value)) input.classList.add("is-stale");
    else input.classList.remove("is-stale");
    if (!open) openDrop();
    else renderDrop();
  };

  input.onfocus = () => openDrop();

  input.onkeydown = (e) => {
    if (e.key === "Escape") close();
  };

  document.addEventListener("click", (e) => {
    if (!wrap.contains(e.target)) close();
  });

  if (isStale(input.value)) input.classList.add("is-stale");

  wrap.append(input, drop);
  return wrap;
}

export function mountInlineParamList({
  values = [],
  suggestions = [],
  staleKeys = null,
  minItems = 1,
  onChange,
}) {
  const box = el("div", "inline-param-list");
  const render = () => {
    box.innerHTML = "";
    values.forEach((item, i) => {
      const row = el("div", "list-row");
      row.appendChild(
        mountInlineParamInput({
          value: item,
          suggestions,
          staleKeys,
          onChange: (v) => {
            values[i] = v;
            onChange([...values]);
          },
        }),
      );
      const del = el("button", "btn icon danger", "×");
      del.type = "button";
      del.disabled = values.length <= minItems;
      del.onclick = () => {
        values.splice(i, 1);
        onChange([...values]);
        render();
      };
      row.appendChild(del);
      box.appendChild(row);
    });
    const add = el("button", "btn ghost add-btn", "+ Add param");
    add.type = "button";
    add.onclick = () => {
      values.push("");
      onChange([...values]);
      render();
    };
    box.appendChild(add);
  };
  render();
  return box;
}
