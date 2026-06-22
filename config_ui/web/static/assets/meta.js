/** Field labels + widget hints for the config form UI. */

export const MANIFEST_LIST_KEYS = {
  joint_names: { manifestId: "joints", itemLabel: "joint" },
  variation_shapes: { manifestId: "variation_shapes", itemLabel: "variation shape" },
  expression_shapes: { manifestId: "expression_shapes", itemLabel: "expression shape" },
};

export const LABELS = {
  wedgeProjection: "Eye wedge projection",
  frame_count: "Frame count",
  seed: "RNG seed",
  paths: "Paths",
  fbx: "Source FBX",
  gen13_blend: "Base blend",
  save_variation_blend: "Variation output",
  save_eye_bake_blend: "Eye bake output",
  save_water_tight_blend: "Watertight output",
  save_export_blend: "Export output",
  issues_dir: "Issues directory",
  good_dir: "Good heads directory",
  attractive_dir: "Attractive heads directory",
  final_output_dir: "Final output directory",
  transform_max: "Location max (m)",
  rotate_max: "Rotation max (°)",
  scale_max: "Scale max",
  enable_scale: "Enable scale channels",
  overrides: "Per-joint overrides",
  joint_names: "Active chaos joints",
  max_var_shapes: "Max variation shapes per group",
  max_variation: "Variation weight max",
  variation_shapes: "Active variation shapes",
  variation_overrides: "Variation overrides",
  expression_shapes: "Active expression shapes",
  expression_max: "Expression weight max",
  expression_overrides: "Expression overrides",
  independent_shapes: "Independent shapes",
  bone_properties: "Bone custom properties",
  hard_clamps: "Hard clamps",
  relational_rules: "Relational rules",
  smooth_corrective: "Smooth corrective",
  factor: "Factor / scale weight",
  iterations: "Iterations",
  scale: "Scale",
  smooth_type: "Smooth type",
  use_only_smooth: "Use only smooth",
  use_pin_boundary: "Pin boundary",
  rest_source: "Rest source",
  enabled: "Enabled",
  debug: "Debug mode",
  attractive_heads_dir: "Attractive heads directory",
  min_attractors: "Min attractors",
  max_attractors: "Max attractors",
  max_influence: "Max influence",
  distance_weights: "Distance weights",
  exclude_params: "Excluded parameters",
  skin_material_blend: "Skin material blend",
  skin_material_name: "Skin material",
  eye_material_name: "Eye material",
  final_color_randomness: "Skin color randomness",
  "hair-color-node": "Hair color node",
  hair_color_randomness: "Hair color randomness",
  hair_color_defaults: "Hair color palette",
  "lip-color-node": "Lip color node",
  lip_color_randomness: "Lip color randomness",
  lip_color_override: "Lip color override",
  assets_blend_path: "Assets blend",
  eye_wedge_R_name: "Right eye wedge",
  eye_wedge_L_name: "Left eye wedge",
  mouth_bag_group: "Mouth bag group",
  remove_mouth_bag: "Remove mouth bag",
  sew_lips: "Sew lips",
  snap_lips: "Snap lips to midpoint",
  join_merge_distance: "Join merge distance",
  lip_sew_merge_distance: "Lip sew merge distance",
  seam_weld_distance: "Seam weld distance",
  mouth_sew_indices: "Mouth sew indices",
  drivers: "Driver relationships",
  "baked-sequence-R-path": "Baked sequence R",
  "baked-sequence-L-path": "Baked sequence L",
  eye_wedge_R_bake_name: "Right bake wedge",
  eye_wedge_L_bake_name: "Left bake wedge",
  hd_eye_R_name: "HD eye R",
  hd_eye_L_name: "HD eye L",
  R_projector_name: "R projector",
  L_projector_name: "L projector",
  "eye-baked-sequence-name": "Eye sequence node",
  "eye-bake-diffuse-name": "Bake diffuse node",
  "eye-bake-switch-name": "Bake switch node",
  "eye-color-name": "Eye color node",
  "eye-bake-settings": "Eye bake settings",
  render_engine: "Render engine",
  bake_type: "Bake type",
  use_pass_direct: "Pass direct",
  use_pass_indirect: "Pass indirect",
  use_pass_color: "Pass color",
  use_selected_to_active: "Selected to active",
  use_cage: "Use cage",
  cage_extrusion: "Cage extrusion",
  max_ray_distance: "Max ray distance",
  target: "Target param",
  margin_type: "Margin type",
  margin: "Margin",
  use_clear: "Clear image",
  save_mode: "Save mode",
  head_bake_resolution: "Head bake resolution",
  eye_wedge_bake_resolution: "Eye wedge resolution",
  bake_samples: "Bake samples",
  bake_margin: "Bake margin",
  glb_format: "GLB format",
  frame_range: "Frame range",
  head_bake_material_name: "Head bake material",
  eye_wedge_R_material_name: "Eye wedge R material",
  eye_wedge_L_material_name: "Eye wedge L material",
  include_eyes: "Include eyes",
  include_brows: "Include brows",
  include_lashes: "Include lashes",
  include_hd_eyes: "Include HD eyes",
  bake_wedge_texture_direct: "Bake wedge texture direct",
  copy_eye_projection: "Copy eye projection",
  bake_brow_texture_direct: "Bake brow texture direct",
  bake_lash_texture_direct: "Bake lash texture direct",
  bake_hd_eye_texture_direct: "Bake HD eye texture direct",
  clean_head_on_export: "Clean head on export",
  hd_eye_material_name: "HD eye material",
  hd_eye_bake_resolution: "HD eye bake resolution",
  channels: "Texture overlay channels",
  pool_path: "Texture pool",
  sequence_path: "Output sequence",
  node_name: "Shader node",
  percentage: "Blend percentage",
  material_name: "Material override",
  reapply_constraints: "Reapply constraints",
  targets: "Re-randomize targets",
  min: "Min",
  max: "Max",
  mirror_sides: "Mirror sides",
  title: "Title",
  type: "Rule type",
  target_bone: "Target bone",
  target_object: "Target object",
  param: "Parameter",
  above: "Above threshold",
  below: "Below threshold",
  combine: "Combine mode",
  max_bias: "Max bias",
  direction: "Direction",
  source: "Source param",
  floor: "Floor param",
  ceiling: "Ceiling param",
  tolerance: "Tolerance",
  target_sign: "Target sign",
  numerator: "Numerator",
  denominator: "Denominator",
  max_ratio: "Max ratio",
  param_a: "Param A",
  param_b: "Param B",
  max_product: "Max product",
  max_combined: "Max combined",
  params: "Params",
  map: "Output map",
  range: "Input range",
};

export const RULE_TYPES = [
  "scale_follow",
  "conditional_clamp",
  "mutual_dampen",
  "ratio_clamp",
  "product_clamp",
  "cross_proportion_clamp",
  "sandwich_clamp",
  "conditional_bias",
  "winner_take_all",
];

export function labelFor(key) {
  return LABELS[key] ?? key.replace(/_/g, " ").replace(/-/g, " ");
}

export function isOverrideMapKey(key) {
  return [
    "overrides",
    "hard_clamps",
    "variation_overrides",
    "expression_overrides",
    "distance_weights",
  ].includes(key);
}

export function isIntMapKey(key) {
  return key === "mouth_sew_indices";
}

export function isObjectArrayKey(key) {
  return ["relational_rules", "drivers"].includes(key);
}

export function isChannelsKey(key) {
  return key === "channels";
}

export function isBonePropertiesKey(key) {
  return key === "bone_properties";
}

export function isIndependentShapesKey(key) {
  return key === "independent_shapes";
}

export function isRegistryTargetsKey(key, fileId) {
  if (fileId === "rerandomize" && key === "targets") return true;
  if (fileId === "attractor" && key === "exclude_params") return true;
  return false;
}
