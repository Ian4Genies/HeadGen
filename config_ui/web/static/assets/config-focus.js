/** Scroll + highlight helpers for Value Trace → Config Files navigation. */

export function scrollToConfigTarget(el, { block = "center" } = {}) {
  if (!el) return;
  el.scrollIntoView({ behavior: "smooth", block, inline: "nearest" });
  el.classList.add("config-focus-highlight");
  setTimeout(() => el.classList.remove("config-focus-highlight"), 2200);
}

export function rerandomizeTargetEntry(metadata) {
  if (metadata.kind === "bone_property") return `property:${metadata.key}`;
  if (metadata.kind === "blendshape") return `shape:${metadata.key}`;
  return metadata.canonical_key ?? metadata.key;
}

export function buildStageFocus(stage, metadata) {
  const fileId = stage.config_file;
  const focus = { fileId, paramKey: metadata.key };

  if (stage.stage_id === "generation") {
    if (metadata.kind === "joint") {
      focus.section = "overrides";
      focus.joint = (metadata.canonical_key ?? metadata.key).split(".")[0];
      focus.fileId = "chaos_joints";
      return focus;
    }
    if (metadata.kind === "bone_property") {
      focus.section = "bone_properties";
      focus.fileId = "chaos_joints";
      return focus;
    }
    if (metadata.blendshape_subtype === "independent") {
      focus.section = "independent_shapes";
      return focus;
    }
    if (metadata.blendshape_subtype === "variation") {
      focus.section = "variation_overrides";
      return focus;
    }
    if (metadata.blendshape_subtype === "expression") {
      focus.section = "expression_overrides";
      return focus;
    }
    return focus;
  }

  if (stage.stage_id === "attractor") {
    focus.section =
      stage.slice?.distance_weight != null
        ? "distance_weights"
        : stage.slice?.excluded
          ? "exclude_params"
          : "enabled";
    return focus;
  }

  if (stage.stage_id === "constraints") {
    focus.section = stage.slice?.hard_clamp ? "hard_clamps" : "relational_rules";
    return focus;
  }

  if (stage.stage_id === "rerandomize") {
    focus.section = "targets";
    focus.targetEntry = rerandomizeTargetEntry(metadata);
    return focus;
  }

  return focus;
}

export function buildRuleFocus(entry) {
  return {
    fileId: "constraints",
    section: "relational_rules",
    ruleIndex: entry.index,
  };
}
