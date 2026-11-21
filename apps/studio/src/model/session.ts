/** Only file paths and active tab are persisted. Unsaved source stays in memory. */
export interface SavedSession { version: 1; paths: string[]; activePath: string | null }
export const MAX_SESSION_TABS = 100;
const PREFIX = "studio5:workspace-session:";

export function validSessionPath(path: unknown): path is string {
  return typeof path === "string" && path.length > 0 && path.length <= 1024 &&
    !path.startsWith("/") && !path.includes("\\") && !path.includes("\0") &&
    path.split("/").every(part => part.length > 0 && part !== "." && part !== "..") &&
    /\.(pm|cpp|hpp|h|ipynb)$/.test(path);
}

export function parseSession(raw: string | null): SavedSession {
  const empty: SavedSession = { version: 1, paths: [], activePath: null };
  if (!raw || raw.length > 32768)return empty;
  try {
    const data: unknown = JSON.parse(raw);
    if (!data || typeof data !== "object" || !("version" in data) ||
        data.version !== 1 || !("paths" in data) || !Array.isArray(data.paths)) return empty;
    const paths = [...new Set(data.paths.filter(validSessionPath))].slice(0,MAX_SESSION_TABS);
    const activePath = "activePath" in data && validSessionPath(data.activePath) &&
      paths.includes(data.activePath) ? data.activePath : null;
    return { version:1, paths, activePath };
  } catch { return empty; }
}

export function snapshotSession(
  documents: readonly {path:string}[], activeId: string,
): SavedSession {
  const paths = [...new Set(documents.map(d=>d.path).filter(validSessionPath))].slice(0,MAX_SESSION_TABS);
  return { version:1, paths, activePath:paths.includes(activeId)?activeId:null };
}

export function readSession(workspace: string): SavedSession {
  try { return parseSession(localStorage.getItem(PREFIX + workspace)); }
  catch { return parseSession(null); }
}

export function saveSession(workspace:string, documents:readonly {path:string}[], activeId:string):void {
  try { localStorage.setItem(PREFIX + workspace, JSON.stringify(snapshotSession(documents,activeId))); }
  catch { /* Storage may be unavailable or full; no source content is written here. */ }
}
