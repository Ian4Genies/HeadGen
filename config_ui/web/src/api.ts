import type { ConfigFileMeta, ProfileInfo, ValidationResult } from "./types";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
    ...init,
  });
  if (!res.ok) {
    const detail = await res.text();
    throw new Error(detail || res.statusText);
  }
  return res.json() as Promise<T>;
}

export async function fetchSchema(): Promise<{ files: ConfigFileMeta[] }> {
  return request("/api/schema");
}

export async function fetchProfiles(): Promise<{
  active: string;
  profiles: ProfileInfo[];
}> {
  return request("/api/profiles");
}

export async function createProfile(name: string, source?: string): Promise<void> {
  await request("/api/profiles", {
    method: "POST",
    body: JSON.stringify({ name, source }),
  });
}

export async function activateProfile(name: string): Promise<void> {
  await request(`/api/profiles/${encodeURIComponent(name)}/activate`, {
    method: "POST",
  });
}

export async function deleteProfile(name: string): Promise<void> {
  await request(`/api/profiles/${encodeURIComponent(name)}`, { method: "DELETE" });
}

export async function renameProfile(name: string, newName: string): Promise<void> {
  await request(`/api/profiles/${encodeURIComponent(name)}/rename`, {
    method: "POST",
    body: JSON.stringify({ new_name: newName }),
  });
}

export async function fetchConfig(
  profile: string,
  fileId: string,
): Promise<Record<string, unknown>> {
  return request(
    `/api/profiles/${encodeURIComponent(profile)}/config/${encodeURIComponent(fileId)}`,
  );
}

export async function saveConfig(
  profile: string,
  fileId: string,
  data: Record<string, unknown>,
): Promise<void> {
  await request(
    `/api/profiles/${encodeURIComponent(profile)}/config/${encodeURIComponent(fileId)}`,
    { method: "PUT", body: JSON.stringify({ data }) },
  );
}

export async function validateProfile(name: string): Promise<ValidationResult> {
  return request(`/api/profiles/${encodeURIComponent(name)}/validate`);
}
