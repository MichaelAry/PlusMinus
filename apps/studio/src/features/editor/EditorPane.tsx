import { useEffect, useRef, useState } from "react";
import { monaco } from "./monaco";
import { useStudio } from "../../model/studio";
import { diagnose } from "../../model/sourceDiagnostics";

const models = new Map<string, monaco.editor.ITextModel>();
const listeners = new Map<string, monaco.IDisposable>();
const markerTimers = new Map<string, ReturnType<typeof setTimeout>>();

function lexicalMarkers(model:monaco.editor.ITextModel,cpp:boolean){
  if(model.isDisposed()||cpp)return;
  monaco.editor.setModelMarkers(model,"plusminus-lexical",diagnose(model.getValue()).map(p=>({
    startLineNumber:p.line,endLineNumber:p.line,startColumn:p.column,
    endColumn:p.column+1,severity:p.severity==="error"?monaco.MarkerSeverity.Error:
      p.severity==="warning"?monaco.MarkerSeverity.Warning:monaco.MarkerSeverity.Info,
    message:p.message,code:p.code,
  })));
}

// One content handler per shared Monaco model, regardless of split editors.
// Prune even when every editor pane has been closed. Never dispose a still-open tab.
let previousIdentity="";
const unsubscribe=useStudio.subscribe(s=>{
  const identity=JSON.stringify([s.workspace,s.documents.map(d=>d.id)]);
  if(identity===previousIdentity)return;
  previousIdentity=identity;
  const live=new Set(s.documents.map(d=>`${s.workspace??"no-workspace"}::${d.id}`));
  for(const [key,model] of models){
    if(!live.has(key)){
      listeners.get(key)?.dispose();listeners.delete(key);
      const timer=markerTimers.get(key);
      if(timer)clearTimeout(timer);
      markerTimers.delete(key);
      model.dispose();
      models.delete(key);
    }
  }
});
import.meta.hot?.dispose(()=>{
  unsubscribe();
  for(const timer of markerTimers.values())clearTimeout(timer);
  for(const listener of listeners.values())listener.dispose();
  for(const model of models.values())model.dispose();
  markerTimers.clear();listeners.clear();models.clear();
});

export function EditorPane() {
  const host = useRef<HTMLDivElement>(null);
  const editor = useRef<monaco.editor.IStandaloneCodeEditor | null>(null);
  const activeId = useStudio((s) => s.activeId);
  const workspace = useStudio((s) => s.workspace);
  const docs = useStudio((s) => s.documents);
  const select = useStudio((s) => s.select);
  const close = useStudio((s) => s.close);
  const response = useStudio((s) => s.response);
  const reportedSource = useStudio((s) => s.reportedSource);
  const [paneSelection,setPaneSelection]=useState<string|null>(null);
  const current = docs.find(d=>d.id===(paneSelection??activeId)) ??
    docs.find(d=>d.id===activeId) ?? docs[0];
  useEffect(()=>setPaneSelection(null),[workspace]);
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
    if (!listeners.has(modelKey)) {
      const id=current.id;
      const cpp=/\.(cpp|hpp|h)$/.test(current.path);
      lexicalMarkers(model,cpp);
      const sharedModel=model;
      listeners.set(modelKey,sharedModel.onDidChangeContent(()=>{
        useStudio.getState().edit(id,sharedModel.getValue());
        const pending=markerTimers.get(modelKey);
        if(pending)clearTimeout(pending);
        markerTimers.set(modelKey,setTimeout(()=>{
          markerTimers.delete(modelKey);
          lexicalMarkers(sharedModel,cpp);
        },350));
      }));
    }
    if (model.getValue() !== current.source) model.setValue(current.source);
    editor.current.setModel(model);
  }, [modelKey]);

  // Authoritative native diagnostics belong only to the exact source snapshot
  // that produced them. Never attach late responses to another tab or edited text.
  useEffect(() => {
    const model = editor.current?.getModel();
    if (!model || !current) return;
    const valid = response && reportedSource?.id===current.id
      && reportedSource.source===current.source;
    const markers = valid ? response.report.diagnostics.map(d => {
      const line=Math.max(1,Math.min(model.getLineCount(),d.line||1));
      const column=Math.max(1,Math.min(model.getLineMaxColumn(line),d.column||1));
      return {
        startLineNumber:line,endLineNumber:line,
        startColumn:column,endColumn:Math.min(model.getLineMaxColumn(line),column+1),
        severity:d.severity==="error"?monaco.MarkerSeverity.Error:
          d.severity==="warning"?monaco.MarkerSeverity.Warning:monaco.MarkerSeverity.Info,
        message:d.message,source:"PlusMinus C++ compiler/runtime",
      };
    }) : [];
    monaco.editor.setModelMarkers(model,"plusminus-native",markers);
  },[modelKey,response,reportedSource,current?.id,current?.source]);

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
            <button className="tab-select" onClick={() => {setPaneSelection(doc.id);select(doc.id);}} role="tab" aria-selected={doc.id === current.id}>
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
