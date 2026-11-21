import { useEffect, useRef } from "react";
import { monaco } from "./monaco";
import { useStudio } from "../../model/studio";

const models = new Map<string, monaco.editor.ITextModel>();

export function EditorPane() {
  const host = useRef<HTMLDivElement>(null);
  const editor = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const activeId = useStudio((s) => s.activeId);
  const docs = useStudio((s) => s.documents);
  const select = useStudio((s) => s.select);
  const close = useStudio((s) => s.close);
  const current = docs.find((d) => d.id === activeId) ?? docs[0];

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
    let model = models.get(current.id);
    if (!model || model.isDisposed()) {
      model = monaco.editor.createModel(current.source, "plusminus",
        monaco.Uri.parse("inmemory://plusminus/" + encodeURIComponent(current.id)));
      models.set(current.id, model);
    }
    if (model.getValue() !== current.source) model.setValue(current.source);
    editor.current.setModel(model);
    const sub = model.onDidChangeContent(() => useStudio.getState().edit(current.id, model!.getValue()));
    return () => sub.dispose();
  }, [current?.id]);

  useEffect(() => {
    const ids = new Set(docs.map((d) => d.id));
    for (const [id, model] of models) {
      if (!ids.has(id)) { model.dispose(); models.delete(id); }
    }
  }, [docs]);

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
