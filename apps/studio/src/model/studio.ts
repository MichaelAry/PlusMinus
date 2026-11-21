import { create } from "zustand";
import type { Document, RunMode, RunResponse, TreeEntry } from "../api/contracts";

export interface OpenDocument extends Document {
  id: string;
  dirty: boolean;
}

interface StudioStore {
  workspace: string | null;
  entries: TreeEntry[];
  documents: OpenDocument[];
  activeId: string;
  mode: RunMode;
  runningJob: string | null;
  response: RunResponse | null;
  transportError: string | null;
  setWorkspace: (workspace: string, entries: TreeEntry[]) => void;
  setEntries: (entries: TreeEntry[]) => void;
  open: (doc: Document) => void;
  close: (id: string) => void;
  edit: (id: string, source: string) => void;
  saved: (id: string, doc: Document) => void;
  select: (id: string) => void;
  setMode: (mode: RunMode) => void;
  started: (job: string) => void;
  finished: (job: string, response: RunResponse | null, error: string | null) => void;
}
const example = "// PlusMinus / quick experiment\nx = 10;\ny = x * 2;\nprint(y);\n";
const initial: OpenDocument = { id: "untitled", path: "", source: example, digest: "", dirty: false };

export const useStudio = create<StudioStore>((set) => ({
  workspace: null,
  entries: [],
  documents: [initial],
  activeId: "untitled",
  mode: "run",
  runningJob: null,
  response: null,
  transportError: null,
  setWorkspace: (workspace, entries) => set({ workspace, entries, documents: [initial], activeId: "untitled", response: null }),
  setEntries: (entries) => set({ entries }),
  open: (doc) => set((s) => ({
    documents: s.documents.some((d) => d.id === doc.path) ? s.documents : [...s.documents, { ...doc, id: doc.path, dirty: false }],
    activeId: doc.path,
  })),
  close: (id) => set((s) => {
    const rest = s.documents.filter((d) => d.id !== id);
    if (rest.length === 0) rest.push(initial);
    return { documents: rest, activeId: s.activeId === id ? rest[rest.length - 1].id : s.activeId };
  }),
  edit: (id, source) => set((s) => ({
    documents: s.documents.map((d) => d.id === id ? { ...d, source, dirty: true } : d),
  })),
  saved: (id, doc) => set((s) => ({
    documents: s.documents.map((d) => d.id === id ? { ...d, id: doc.path, digest: doc.digest, path: doc.path, dirty: false } : d),
    activeId: s.activeId === id ? doc.path : s.activeId,
  })),
  select: (activeId) => set({ activeId }),
  setMode: (mode) => set({ mode }),
  started: (runningJob) => set({ runningJob, response: null, transportError: null }),
  finished: (job, response, error) => set((s) =>
    s.runningJob === job ? { runningJob: null, response, transportError: error } : s),
}));
