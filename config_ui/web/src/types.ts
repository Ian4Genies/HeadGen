export type ConfigFileMeta = {
  id: string;
  label: string;
  description: string;
};

export type ProfileInfo = {
  name: string;
  active: boolean;
  file_count: number;
  modified_at: string;
};

export type ValidationResult = {
  valid: boolean;
  message: string;
  frame_count?: number;
  joint_count?: number;
  driver_count?: number;
};
