import { useCallback, useEffect, useMemo, useState } from "react";
import Editor from "@monaco-editor/react";
import {
  activateProfile,
  createProfile,
  deleteProfile,
  fetchConfig,
  fetchProfiles,
  fetchSchema,
  renameProfile,
  saveConfig,
  validateProfile,
} from "./api";
import type { ConfigFileMeta, ProfileInfo } from "./types";

type Toast = { kind: "ok" | "err"; text: string };

export default function App() {
  const [files, setFiles] = useState<ConfigFileMeta[]>([]);
  const [profiles, setProfiles] = useState<ProfileInfo[]>([]);
  const [activeProfile, setActiveProfile] = useState("");
  const [selectedFile, setSelectedFile] = useState("runner");
  const [editorText, setEditorText] = useState("{}");
  const [savedText, setSavedText] = useState("{}");
  const [dirty, setDirty] = useState(false);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [toast, setToast] = useState<Toast | null>(null);
  const [newProfileName, setNewProfileName] = useState("");
  const [showNewProfile, setShowNewProfile] = useState(false);

  const selectedMeta = useMemo(
    () => files.find((f) => f.id === selectedFile),
    [files, selectedFile],
  );

  const notify = useCallback((kind: Toast["kind"], text: string) => {
    setToast({ kind, text });
    window.setTimeout(() => setToast(null), 3500);
  }, []);

  const refreshProfiles = useCallback(async () => {
    const data = await fetchProfiles();
    setProfiles(data.profiles);
    setActiveProfile(data.active);
  }, []);

  const loadFile = useCallback(
    async (profile: string, fileId: string) => {
      const data = await fetchConfig(profile, fileId);
      const text = JSON.stringify(data, null, 2);
      setEditorText(text);
      setSavedText(text);
      setDirty(false);
    },
    [],
  );

  useEffect(() => {
    (async () => {
      try {
        const [schema, profs] = await Promise.all([fetchSchema(), fetchProfiles()]);
        setFiles(schema.files);
        setProfiles(profs.profiles);
        setActiveProfile(profs.active);
        await loadFile(profs.active, "runner");
      } catch (err) {
        notify("err", err instanceof Error ? err.message : "Failed to load");
      } finally {
        setLoading(false);
      }
    })();
  }, [loadFile, notify]);

  useEffect(() => {
    if (!activeProfile || loading) return;
    loadFile(activeProfile, selectedFile).catch((err) =>
      notify("err", err instanceof Error ? err.message : "Failed to load file"),
    );
  }, [activeProfile, selectedFile, loadFile, loading, notify]);

  const handleEditorChange = (value: string | undefined) => {
    const next = value ?? "";
    setEditorText(next);
    setDirty(next !== savedText);
  };

  const handleSave = useCallback(async () => {
    if (!dirty || saving) return;
    setSaving(true);
    try {
      const parsed = JSON.parse(editorText) as Record<string, unknown>;
      await saveConfig(activeProfile, selectedFile, parsed);
      setSavedText(editorText);
      setDirty(false);
      notify("ok", `${selectedFile}.json saved`);
      await refreshProfiles();
    } catch (err) {
      notify("err", err instanceof Error ? err.message : "Save failed");
    } finally {
      setSaving(false);
    }
  }, [activeProfile, dirty, editorText, notify, refreshProfiles, saving, selectedFile]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === "s") {
        e.preventDefault();
        void handleSave();
      }
    };
    window.addEventListener("keydown", onKeyDown, { capture: true });
    return () => window.removeEventListener("keydown", onKeyDown, { capture: true });
  }, [handleSave]);

  const handleValidate = async () => {
    try {
      const result = await validateProfile(activeProfile);
      if (result.valid) {
        notify(
          "ok",
          `Valid — ${result.frame_count} frames, ${result.joint_count} joints, ${result.driver_count} drivers`,
        );
      } else {
        notify("err", result.message);
      }
    } catch (err) {
      notify("err", err instanceof Error ? err.message : "Validation failed");
    }
  };

  const handleActivate = async (name: string) => {
    if (dirty && !window.confirm("Unsaved changes will remain in the editor only. Switch profile anyway?")) {
      return;
    }
    try {
      await activateProfile(name);
      setActiveProfile(name);
      await refreshProfiles();
      notify("ok", `Active profile: ${name} (synced to data/config)`);
    } catch (err) {
      notify("err", err instanceof Error ? err.message : "Activation failed");
    }
  };

  const handleCreateProfile = async () => {
    const name = newProfileName.trim();
    if (!name) return;
    try {
      await createProfile(name, activeProfile);
      setNewProfileName("");
      setShowNewProfile(false);
      await refreshProfiles();
      notify("ok", `Active profile: ${name} (synced to data/config)`);
    } catch (err) {
      notify("err", err instanceof Error ? err.message : "Create failed");
    }
  };

  const handleDeleteProfile = async (name: string) => {
    if (!window.confirm(`Delete profile "${name}"? This cannot be undone.`)) return;
    try {
      await deleteProfile(name);
      await refreshProfiles();
      notify("ok", `Deleted "${name}"`);
    } catch (err) {
      notify("err", err instanceof Error ? err.message : "Delete failed");
    }
  };

  const handleRenameProfile = async (name: string) => {
    const newName = window.prompt("New profile name:", name);
    if (!newName || newName.trim() === name) return;
    try {
      await renameProfile(name, newName.trim());
      if (activeProfile === name) setActiveProfile(newName.trim());
      await refreshProfiles();
      notify("ok", `Renamed to "${newName.trim()}"`);
    } catch (err) {
      notify("err", err instanceof Error ? err.message : "Rename failed");
    }
  };

  if (loading) {
    return (
      <div className="flex h-full items-center justify-center text-slate-400">
        Loading config editor…
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <header className="glass flex shrink-0 items-center justify-between gap-4 border-b border-white/5 px-5 py-3">
        <div className="flex items-center gap-3">
          <div className="flex h-9 w-9 items-center justify-center rounded-xl bg-gradient-to-br from-violet-500 to-fuchsia-600 text-sm font-bold shadow-lg shadow-violet-900/40">
            SH
          </div>
          <div>
            <h1 className="text-base font-semibold tracking-tight">Synth Head Config</h1>
            <p className="text-xs text-slate-400">Pipeline profiles · live sync to Blender</p>
          </div>
        </div>

        <div className="flex flex-wrap items-center gap-2">
          <label className="text-xs uppercase tracking-wider text-slate-500">Profile</label>
          <select
            className="input min-w-[160px]"
            value={activeProfile}
            onChange={(e) => handleActivate(e.target.value)}
          >
            {profiles.map((p) => (
              <option key={p.name} value={p.name}>
                {p.name}
                {p.active ? " · active" : ""}
              </option>
            ))}
          </select>
          <button className="btn btn-ghost" onClick={() => setShowNewProfile((v) => !v)}>
            + New
          </button>
          <button className="btn btn-ghost" onClick={() => handleRenameProfile(activeProfile)}>
            Rename
          </button>
          <button
            className="btn btn-danger"
            disabled={profiles.length <= 1}
            onClick={() => handleDeleteProfile(activeProfile)}
          >
            Delete
          </button>
        </div>

        <div className="flex items-center gap-2">
          <button className="btn btn-ghost" onClick={handleValidate}>
            Validate
          </button>
          <button className="btn btn-primary" disabled={!dirty || saving} onClick={handleSave}>
            {saving ? "Saving…" : dirty ? "Save changes" : "Saved"}
          </button>
        </div>
      </header>

      {showNewProfile && (
        <div className="glass flex items-center gap-2 border-b border-white/5 px-5 py-2">
          <input
            className="input flex-1 max-w-xs"
            placeholder="Profile name"
            value={newProfileName}
            onChange={(e) => setNewProfileName(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && handleCreateProfile()}
          />
          <span className="text-xs text-slate-500">duplicates current profile</span>
          <button className="btn btn-primary" onClick={handleCreateProfile}>
            Create
          </button>
        </div>
      )}

      <div className="flex min-h-0 flex-1">
        <aside className="glass w-72 shrink-0 overflow-y-auto border-r border-white/5 p-3">
          <p className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-widest text-slate-500">
            Config files
          </p>
          <nav className="space-y-1">
            {files.map((file) => (
              <button
                key={file.id}
                className={`w-full rounded-xl px-3 py-2.5 text-left transition ${
                  selectedFile === file.id
                    ? "bg-violet-500/15 text-violet-100 ring-1 ring-violet-500/30"
                    : "text-slate-300 hover:bg-white/5"
                }`}
                onClick={() => {
                  if (dirty && !window.confirm("Discard unsaved changes?")) return;
                  setSelectedFile(file.id);
                }}
              >
                <div className="mono text-sm font-medium">{file.id}.json</div>
                <div className="mt-0.5 text-xs text-slate-500">{file.description}</div>
              </button>
            ))}
          </nav>
        </aside>

        <main className="flex min-w-0 flex-1 flex-col">
          <div className="flex items-center justify-between border-b border-white/5 px-4 py-2">
            <div>
              <h2 className="mono text-sm font-medium text-violet-200">
                {selectedFile}.json
              </h2>
              <p className="text-xs text-slate-500">{selectedMeta?.description}</p>
            </div>
            <div className="flex items-center gap-3 text-xs">
              {dirty && (
                <span className="rounded-full bg-amber-500/15 px-2 py-1 text-amber-200">
                  unsaved
                </span>
              )}
              <span className="text-slate-500">profile: {activeProfile}</span>
            </div>
          </div>
          <div className="min-h-0 flex-1">
            <Editor
              height="100%"
              language="json"
              theme="vs-dark"
              value={editorText}
              onChange={handleEditorChange}
              options={{
                minimap: { enabled: false },
                fontSize: 13,
                fontFamily: "JetBrains Mono, monospace",
                lineNumbers: "on",
                scrollBeyondLastLine: false,
                wordWrap: "on",
                padding: { top: 12 },
                renderLineHighlight: "line",
              }}
            />
          </div>
        </main>
      </div>

      {toast && (
        <div
          className={`toast-enter fixed bottom-5 right-5 rounded-xl px-4 py-3 text-sm shadow-xl ${
            toast.kind === "ok"
              ? "bg-emerald-500/15 text-emerald-200 ring-1 ring-emerald-500/30"
              : "bg-rose-500/15 text-rose-200 ring-1 ring-rose-500/30"
          }`}
        >
          {toast.text}
        </div>
      )}
    </div>
  );
}
