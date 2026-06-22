/** Per-file section layout — full-width for lists & complex editors. */

export const FILE_LAYOUTS = {
  featureFlags: {
    sections: [
      {
        keys: ["wedgeProjection"],
        cols: 1,
        title: "Eye pipeline",
        hint: "Off = HD eyes only (no wedges, projectors, or eye bake). Written to the scene when Variation Pipeline runs — downstream operators read the scene, not this file.",
      },
    ],
  },
  runner: {
    sections: [
      { keys: ["frame_count", "seed"], cols: 2 },
      { keys: ["paths"], full: true, title: "Paths" },
    ],
  },
  chaos_joints: {
    sections: [
      { keys: ["joint_names"], full: true, title: "Active joints" },
      {
        keys: ["transform_max", "rotate_max", "scale_max", "enable_scale"],
        cols: 4,
        title: "Global fallbacks",
      },
      { keys: ["overrides"], full: true, title: "Per-joint overrides" },
      { keys: ["bone_properties"], full: true, title: "Bone custom properties" },
    ],
  },
  blendshapes: {
    sections: [
      { keys: ["variation_shapes"], full: true, title: "Variation shapes" },
      { keys: ["max_var_shapes", "max_variation"], cols: 2, title: "Variation budget" },
      { keys: ["variation_overrides"], full: true, title: "Variation caps" },
      { keys: ["expression_shapes"], full: true, title: "Expression shapes" },
      { keys: ["expression_max"], cols: 1 },
      { keys: ["expression_overrides"], full: true, title: "Expression caps" },
      { keys: ["independent_shapes"], full: true, title: "Independent shapes" },
    ],
  },
  constraints: {
    sections: [
      { keys: ["hard_clamps"], full: true, title: "Hard clamps" },
      { keys: ["relational_rules"], full: true, title: "Relational rules" },
    ],
  },
  modifiers: {
    sections: [{ keys: ["smooth_corrective"], full: true }],
  },
  attractor: {
    sections: [
      { keys: ["enabled", "debug"], cols: 2 },
      { keys: ["attractive_heads_dir"], full: true },
      { keys: ["min_attractors", "max_attractors", "max_influence"], cols: 3 },
      { keys: ["distance_weights"], full: true, title: "Distance weights" },
      { keys: ["exclude_params"], full: true, title: "Excluded parameters" },
    ],
  },
  materials: {
    sections: [
      { keys: ["paths"], full: true },
      { keys: ["skin_material_name", "eye_material_name", "final_color_randomness"], cols: 3 },
      {
        keys: ["hair-color-node", "hair_color_randomness", "hair_color_defaults"],
        full: true,
        title: "Hair",
      },
      {
        keys: ["lip-color-node", "lip_color_randomness", "lip_color_override"],
        cols: 3,
        title: "Lips",
      },
    ],
  },
  cleanup: {
    sections: [
      { keys: ["paths"], full: true },
      { keys: ["eye_wedge_R_name", "eye_wedge_L_name", "mouth_bag_group"], cols: 3 },
      { keys: ["mouth_sew_indices"], full: true },
    ],
  },
  drivers: {
    sections: [{ keys: ["drivers"], full: true }],
  },
  projection: {
    sections: [
      { keys: ["paths"], full: true },
      {
        keys: [
          "eye_wedge_R_bake_name",
          "eye_wedge_L_bake_name",
          "hd_eye_R_name",
          "hd_eye_L_name",
          "R_projector_name",
          "L_projector_name",
        ],
        cols: 2,
      },
      {
        keys: [
          "eye-baked-sequence-name",
          "eye-bake-diffuse-name",
          "eye-bake-switch-name",
          "eye-color-name",
        ],
        cols: 2,
      },
      { keys: ["eye-bake-settings"], full: true, title: "Bake settings" },
    ],
  },
  export: {
    sections: [
      {
        keys: ["head_bake_resolution", "eye_wedge_bake_resolution", "bake_samples", "bake_margin"],
        cols: 4,
      },
      { keys: ["glb_format", "frame_range"], cols: 2 },
      {
        keys: ["head_bake_material_name", "eye_wedge_R_material_name", "eye_wedge_L_material_name"],
        cols: 3,
      },
      {
        keys: ["include_eyes", "include_brows", "include_lashes"],
        cols: 3,
        title: "Include parts",
      },
      {
        keys: [
          "bake_wedge_texture_direct",
          "copy_eye_projection",
          "bake_brow_texture_direct",
          "bake_lash_texture_direct",
        ],
        cols: 2,
        title: "Bake options",
      },
    ],
  },
  texture_swap: {
    sections: [{ keys: ["channels"], full: true, title: "Overlay channels" }],
  },
  rerandomize: {
    sections: [
      { keys: ["enabled", "seed", "reapply_constraints"], cols: 3 },
      { keys: ["targets"], full: true, title: "Targets" },
    ],
  },
};
