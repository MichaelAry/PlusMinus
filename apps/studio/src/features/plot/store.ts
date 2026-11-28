import { invoke } from "@tauri-apps/api/core";
import { create } from "zustand";
import { decodePlot, encodePlot, newPlot, type PlotDocument } from "./document";

interface PlotFile { path: string; source: string; digest: string }
type Choice = "save" | "discard" | "cancel";
type Rows = [string, string][];
interface PlotState {
  document: PlotDocument;
  generation: number;
  selected: string | null;
  drafts: Map<string, Rows>;
  file: Pick<PlotFile, "path" | "digest"> | null;
  dirty: boolean;
  busy: boolean;
  message: string;
  question?: { owner: Document; resolve: (choice: Choice) => void };
}

const initial = newPlot();
export const usePlot = create<PlotState>(() => ({
  generation: 0, document: initial, selected: initial.series[0].id, drafts: new Map(),
  file: null, dirty: false, busy: false, message: "",
}));

export function plotMessage(message: string) { usePlot.setState({ message }); }

export function editPlot(updater: (state: PlotState) => Partial<PlotState>) {
  usePlot.setState(state => state.busy ? state : { ...updater(state), dirty: true });
}

function adopt(document: PlotDocument, file: PlotFile | null, message = "") {
  usePlot.setState(state => ({
    generation: state.generation + 1, document, file: file && { path: file.path, digest: file.digest },
    selected: document.series[0]?.id ?? null, drafts: new Map(), dirty: false, message,
  }));
}

async function remember(path: string | null) {
  try { await invoke("remember_plot", { path }); }
  catch (error) { plotMessage("Could not update the plot session: " + String(error)); }
}

async function exclusive<T>(work: () => Promise<T>, fallback: T): Promise<T> {
  if (usePlot.getState().busy) return fallback;
  usePlot.setState({ busy: true });
  try { return await work(); }
  catch (error) {
    plotMessage(String(error));
    return fallback;
  } finally { usePlot.setState({ busy: false }); }
}

async function writePlot(saveAs: boolean): Promise<PlotFile | null> {
  const { document, drafts, file } = usePlot.getState();
  for (const series of document.series) {
    const rows = drafts.get(series.id);
    if (series.kind === "points" && rows && rows.length !== series.points.length) {
      throw new Error("Correct or remove incomplete rows in " + series.label + " before saving.");
    }
  }
  const name = file?.path.split(/[\\/]/).at(-1) ?? "untitled.pmplot";
  const target = saveAs ? null : file;
  const saved = await invoke<PlotFile | null>("save_plot", {
    source: encodePlot(document), path: target?.path ?? null, expected: target?.digest ?? null, name,
  });
  if (!saved) return null;
  usePlot.setState({ file: { path: saved.path, digest: saved.digest }, dirty: false, message: "Saved " + saved.path });
  await remember(saved.path);
  window.dispatchEvent(new Event("studio:refresh-workspace"));
  return saved;
}

export function savePlot(saveAs = false) {
  return exclusive(async () => !!await writePlot(saveAs), false);
}

async function confirmReplace(owner: Document): Promise<boolean | PlotFile> {
  if (!usePlot.getState().dirty) return true;
  const choice = await new Promise<Choice>(resolve => {
    const currentOwner = owner.defaultView && !owner.defaultView.closed ? owner : window.document;
    usePlot.setState({ question: { owner: currentOwner, resolve } });
  });
  usePlot.setState({ question: undefined });
  if (choice === "save") return await writePlot(false) ?? false;
  return choice === "discard";
}

export function confirmPlotExit() {
  return exclusive(async () => !!await confirmReplace(window.document), false);
}

export function createPlot(owner: Document) {
  return exclusive(async () => {
    if (!await confirmReplace(owner)) return false;
    adopt(newPlot(), null);
    await remember(null);
    return true;
  }, false);
}

export function openPlot(owner: Document, relative: string | null = null) {
  return exclusive(async () => {
    const file = await invoke<PlotFile | null>("open_plot", { relative });
    if (!file) return false;
    const document = decodePlot(file.source);
    const decision = await confirmReplace(owner);
    if (!decision) return false;
    const savedSameFile = decision !== true && decision.path === file.path;
    adopt(savedSameFile ? decodePlot(decision.source) : document,
      savedSameFile ? decision : file, "Opened " + file.path);
    await remember(file.path);
    return true;
  }, false);
}

let restored = false;
export function restorePlot() {
  return exclusive(async () => {
    if (restored) return;
    restored = true;
    const file = await invoke<PlotFile | null>("restore_plot");
    if (file) adopt(decodePlot(file.source), file);
  }, undefined);
}
