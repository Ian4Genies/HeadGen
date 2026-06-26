/** Sticky pipeline stepper — per-step values from simulate API. */

function el(tag, cls = "", text = "") {
  const n = document.createElement(tag);
  if (cls) n.className = cls;
  if (text) n.textContent = text;
  return n;
}

function fmt(v) {
  if (v === null || v === undefined) return "—";
  const n = Number(v);
  if (Number.isNaN(n)) return String(v);
  return Math.abs(n) < 0.0001 && n !== 0 ? n.toExponential(2) : n.toFixed(4).replace(/\.?0+$/, "");
}

function fmtDelta(d) {
  if (d === null || d === undefined) return "";
  const n = Number(d);
  if (Math.abs(n) < 1e-9) return "";
  const sign = n > 0 ? "+" : "";
  return `${sign}${fmt(n)}`;
}

export function mountTraceRibbon(container, { steps = null, loading = false, finalValue = null } = {}) {
  container.innerHTML = "";
  container.className = "trace-ribbon-wrap";

  const ribbon = el("div", `trace-ribbon${loading ? " loading" : ""}`);

  if (loading) {
    for (let i = 0; i < 4; i++) {
      const node = el("div", "trace-ribbon-node shimmer");
      node.appendChild(el("span", "trace-step-label", "…"));
      node.appendChild(el("span", "trace-step-value mono", "—"));
      ribbon.appendChild(node);
      if (i < 3) ribbon.appendChild(el("span", "trace-ribbon-arrow", "→"));
    }
    container.appendChild(ribbon);
    return { update() {} };
  }

  if (!steps?.length) {
    container.appendChild(el("p", "trace-ribbon-empty muted", "Run Simulate to see values after each step"));
    return { update() {} };
  }

  const displaySteps = [...steps];
  const last = displaySteps[displaySteps.length - 1];
  const showFinal =
    finalValue !== null &&
    last &&
    last.stage_id !== "final" &&
    !displaySteps.some((s) => s.stage_id === "final");

  if (showFinal) {
    displaySteps.push({
      stage_id: "final",
      label: "Final",
      value: finalValue,
      delta: finalValue - last.value,
      skipped: false,
    });
  }

  for (let i = 0; i < displaySteps.length; i++) {
    const step = displaySteps[i];
    const node = el(
      "div",
      `trace-ribbon-node${step.skipped ? " skipped" : ""}${step.stage_id === "final" ? " hero" : ""} pulse`,
    );
    node.appendChild(el("span", "trace-step-label", step.label));
    node.appendChild(el("span", "trace-step-value mono", step.skipped ? "skip" : fmt(step.value)));
    const d = fmtDelta(step.delta);
    if (d && !step.skipped) {
      const cls = step.delta > 0 ? "trace-delta-up" : step.delta < 0 ? "trace-delta-down" : "trace-delta-neutral";
      node.appendChild(el("span", `trace-delta mono ${cls}`, `Δ ${d}`));
    }
    if (step.detail) node.appendChild(el("span", "trace-step-detail", step.detail));
    ribbon.appendChild(node);
    if (i < displaySteps.length - 1) ribbon.appendChild(el("span", "trace-ribbon-arrow", "→"));
  }

  container.appendChild(ribbon);

  return {
    update(next) {
      mountTraceRibbon(container, next);
    },
  };
}
