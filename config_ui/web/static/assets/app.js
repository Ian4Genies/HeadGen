import { mountForm } from "./forms.js";

const $ = (sel) => document.querySelector(sel);

let files = [];
let activeProfile = "";
let selectedFile = "runner";
let form = null;
let dirty = false;

async function api(path, init) {
  const res = await fetch(path, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    let detail = await res.text();
    try {
      detail = JSON.parse(detail).detail ?? detail;
    } catch {
      /* keep text */
    }
    throw new Error(detail || res.statusText);
  }
  return res.status === 204 ? null : res.json();
}

function toast(kind, text) {
  const el = $("#toast");
  el.className = `toast ${kind}`;
  el.textContent = text;
  el.classList.remove("hidden");
  clearTimeout(toast._t);
  toast._t = setTimeout(() => el.classList.add("hidden"), 3500);
}

function setDirty(next) {
  dirty = next;
  $("#dirty-badge").classList.toggle("hidden", !dirty);
  $("#btn-save").disabled = !dirty;
  $("#btn-save").textContent = dirty ? "Save changes" : "Saved";
}

function confirmDiscard() {
  return !dirty || window.confirm("Discard unsaved changes?");
}

function renderFileList() {
  const nav = $("#file-list");
  nav.innerHTML = "";
  for (const file of files) {
    const btn = document.createElement("button");
    btn.type = "button";
    btn.className = `file-btn${file.id === selectedFile ? " active" : ""}`;
    btn.innerHTML = `<div class="name">${file.label}</div><div class="desc">${file.description}</div>`;
    btn.onclick = async () => {
      if (!confirmDiscard()) return;
      selectedFile = file.id;
      renderFileList();
      await loadFile();
    };
    nav.appendChild(btn);
  }
  const meta = files.find((f) => f.id === selectedFile);
  $("#file-title").textContent = meta?.label ?? selectedFile;
  $("#file-desc").textContent = meta?.description ?? "";
}

async function refreshProfiles() {
  const data = await api("/api/profiles");
  activeProfile = data.active;
  const select = $("#profile-select");
  select.innerHTML = "";
  for (const p of data.profiles) {
    const opt = document.createElement("option");
    opt.value = p.name;
    opt.textContent = p.active ? `${p.name} · active` : p.name;
    select.appendChild(opt);
  }
  select.value = activeProfile;
  $("#active-label").textContent = `profile: ${activeProfile}`;
  $("#btn-delete").disabled = data.profiles.length <= 1;
}

async function loadFile() {
  const data = await api(
    `/api/profiles/${encodeURIComponent(activeProfile)}/config/${encodeURIComponent(selectedFile)}`,
  );
  const host = $("#form-root");
  form = mountForm(host, data, setDirty, { profile: activeProfile, fileId: selectedFile });
  setDirty(false);
}

async function boot() {
  const schema = await api("/api/schema");
  files = schema.files;
  await refreshProfiles();
  renderFileList();
  await loadFile();

  $("#profile-select").onchange = async (e) => {
    if (!confirmDiscard()) {
      e.target.value = activeProfile;
      return;
    }
    try {
      await api(`/api/profiles/${encodeURIComponent(e.target.value)}/activate`, {
        method: "POST",
      });
      activeProfile = e.target.value;
      await refreshProfiles();
      await loadFile();
      toast("ok", `Active profile: ${activeProfile} (synced to data/config)`);
    } catch (err) {
      toast("err", err.message);
      e.target.value = activeProfile;
    }
  };

  $("#btn-save").onclick = async () => {
    try {
      await api(
        `/api/profiles/${encodeURIComponent(activeProfile)}/config/${encodeURIComponent(selectedFile)}`,
        { method: "PUT", body: JSON.stringify({ data: form.getData() }) },
      );
      form.markSaved();
      setDirty(false);
      toast("ok", `${selectedFile}.json saved`);
      await refreshProfiles();
    } catch (err) {
      toast("err", err.message);
    }
  };

  $("#btn-validate").onclick = async () => {
    try {
      const result = await api(
        `/api/profiles/${encodeURIComponent(activeProfile)}/validate`,
      );
      if (result.valid) {
        toast(
          "ok",
          `Valid — ${result.frame_count} frames, ${result.joint_count} joints, ${result.driver_count} drivers`,
        );
      } else {
        toast("err", result.message);
      }
    } catch (err) {
      toast("err", err.message);
    }
  };

  $("#btn-new").onclick = () => {
    $("#new-profile-bar").classList.toggle("hidden");
    $("#new-profile-name").focus();
  };

  $("#btn-create").onclick = async () => {
    const name = $("#new-profile-name").value.trim();
    if (!name) return;
    try {
      await api("/api/profiles", {
        method: "POST",
        body: JSON.stringify({ name, source: activeProfile }),
      });
      $("#new-profile-name").value = "";
      $("#new-profile-bar").classList.add("hidden");
      await refreshProfiles();
      toast("ok", `Created profile "${name}"`);
    } catch (err) {
      toast("err", err.message);
    }
  };

  $("#btn-rename").onclick = async () => {
    const newName = window.prompt("New profile name:", activeProfile);
    if (!newName || newName.trim() === activeProfile) return;
    try {
      await api(`/api/profiles/${encodeURIComponent(activeProfile)}/rename`, {
        method: "POST",
        body: JSON.stringify({ new_name: newName.trim() }),
      });
      if (activeProfile === $("#profile-select").value) {
        activeProfile = newName.trim();
      }
      await refreshProfiles();
      toast("ok", `Renamed to "${newName.trim()}"`);
    } catch (err) {
      toast("err", err.message);
    }
  };

  $("#btn-delete").onclick = async () => {
    if (!window.confirm(`Delete profile "${activeProfile}"? This cannot be undone.`)) return;
    try {
      await api(`/api/profiles/${encodeURIComponent(activeProfile)}`, {
        method: "DELETE",
      });
      await refreshProfiles();
      await loadFile();
      toast("ok", "Profile deleted");
    } catch (err) {
      toast("err", err.message);
    }
  };
}

boot().catch((err) => toast("err", err.message));
