import { useEffect, useRef } from "react";
import { monaco } from "./monaco";
import { useStudio } from "../../model/studio";

const models = new Map<string, monaco.editor.ITextModel>();

export function EditorPane() {
  const host = useRef<HTMLDivElement>(null);
  const editor = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const activeId = useStudio((s) => s.activeId);
  const workspace = useStudio((s) => s.workspace);
  const docs = useStudio((s) => s.documents);
  const select = useStudio((s) => s.select);
  const close = useStudio((s) => s.close);
  const current = docs.find((d) => d.id === activeId) ?? docs[0];
  const modelKey = current ? `${workspace ?? "no-workspace"}::${current.id}` : "";

  useEffect(() => {
    if (!host.current) return;
    const instance = monaco.editor.create(host.current, {
      theme: "plusminus-graphite", language: "plusminus",
      automaticLayout: true, minimap: { enabled: false },
      fontFamily: "Cascadia Code, JetBrains Mono, Consolas, monospace",
      fontSize: 13, lineHeight: 22,
      smoothScrolling: true, cursorSmoothCaretAnimation: "on",
      tabSize: 4, scrollBeyondLastLine: false, padding: { top: 22 },
    });
    editor.current = instance;
    return () => { instance.dispose(); editor.current = null; };
  }, []);

  useEffect(() => {
    if (!editor.current || !current) return;
    let model = models.get(modelKey);
    if (!model || model.isDisposed()) {
      model = monaco.editor.createModel(current.source, /\.(cpp|hpp|h)$/.test(current.path) ? "cpp" : "plusminus",
        monaco.Uri.parse("inmemory://plusminus/" + encodeURIComponent(modelKey)));
      models.set(modelKey, model);
    }
    if (model.getValue() !== current.source) model.setValue(current.source);
    editor.current.setModel(model);
    const sub = model.onDidChangeContent(() => useStudio.getState().edit(current.id, model!.getValue()));
    return () => sub.dispose();
  }, [modelKey]);

  useEffect(() => {
    const ids = new Set(docs.map((d) => `${workspace ?? "no-workspace"}::${d.id}`));
    for (const [id, model] of models) {
      if (!ids.has(id)) { model.dispose(); models.delete(id); }
    }
  }, [docs, workspace]);

  useEffect(() => {
    const handler = (event: Event) => {
      const {path,anchor}=(event as CustomEvent<{path:string;anchor:string}>).detail;
      if (current?.path !== path || !anchor || !editor.current) return;
      const model = editor.current.getModel();
      if (!model) return;
      const source = model.getValue();
      const position = source.indexOf(anchor);
      if (position < 0) return;
      const line = source.slice(0,position).split("\n").length;
      editor.current.revealLineInCenter(line);
      editor.current.setPosition({lineNumber:line,column:1});
      editor.current.focus();
    };
    window.addEventListener("studio:goto-anchor",handler);
    return () => window.removeEventListener("studio:goto-anchor",handler);
  },[current?.path]);

  return (
    <div className="editor-pane">
      <div className="document-tabs" role="tablist" aria-label="Open documents">
        {docs.map((doc) => (
          <div key={doc.id} className={"document-tab " + (doc.id === activeId ? "active" : "")}>
            <button className="tab-select" onClick={() => select(doc.id)} role="tab" aria-selected={doc.id === activeId}>
              <span className="pm-file-icon">±</span>
              {doc.path ? doc.path.split("/").at(-1) : "Untitled.pm"}
              {doc.dirty && <span className="dirty-dot">●</span>}
            </button>
            <button className="tab-close" aria-label={"Close " + doc.id} onClick={() => {
              if (!doc.dirty || window.confirm("Discard unsaved changes in " + (doc.path || "Untitled.pm") + "?")) {
                close(doc.id);
              }
            }}>×</button>
          </div>
        ))}
      </div>
      <div className="editor-surface" ref={host} />
      <div className="editor-footer">
        <span>PLUSMINUS · UTF-8</span><span>MONACO EDITOR</span>
      </div>
    </div>
  );
}
