import * as monaco from "monaco-editor";
import { completionCandidates } from "../../model/completion";
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";

(globalThis as typeof globalThis & {
  MonacoEnvironment?: { getWorker: (_: string, label: string) => Worker }
}).MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
};

monaco.languages.register({ id: "plusminus", extensions: [".pm"] });
monaco.languages.setLanguageConfiguration("plusminus", {
  comments: { lineComment: "//", blockComment: ["/*", "*/"] },
  brackets: [["{", "}"], ["[", "]"], ["(", ")"]],
  autoClosingPairs: [
    {open:"{",close:"}"}, {open:"[",close:"]"}, {open:"(",close:")"},
    {open:'"',close:'"'}
  ]
});
// Monaco's standard Find and Toggle Line Comment commands now use
// the registered PlusMinus language configuration, without a custom editor.
monaco.languages.registerCompletionItemProvider("plusminus", {
  provideCompletionItems(model, position) {
    const word=model.getWordUntilPosition(position);
    const range={
      startLineNumber:position.lineNumber,endLineNumber:position.lineNumber,
      startColumn:word.startColumn,endColumn:word.endColumn,
    };
    return {suggestions:completionCandidates(model.getValue(),word.word).map(label=>({
      label,kind:monaco.languages.CompletionItemKind.Keyword,insertText:label,range,
    }))};
  },
});
monaco.languages.setMonarchTokensProvider("plusminus", {
  tokenizer: {
    root: [
      [/\/\/.*$/, "comment"],
      [/"(?:[^"\\]|\\.)*"/, "string"],
      [/\b(?:if|else|while|for|return|func|proc|go|sync|lock|unlock|print)\b/, "keyword"],
      [/\b\d+(?:\.\d+)?\b/, "number"],
      [/[{}()[\]]/, "@brackets"],
      [/[+\-*/^%=<>!&|]+/, "operator"],
      [/[a-zA-Z_]\w*/, "identifier"],
    ],
  },
});
monaco.editor.defineTheme("plusminus-graphite", {
  base: "vs-dark", inherit: true,
  rules: [
    { token: "comment", foreground: "6F777E" },
    { token: "keyword", foreground: "D4DADF", fontStyle: "bold" },
    { token: "number", foreground: "C6BBA8" },
    { token: "string", foreground: "AFC2B5" },
  ],
  colors: {
    "editor.background": "#121518",
    "editor.foreground": "#D9DCE1",
    "editorLineNumber.foreground": "#646D75",
    "editorLineNumber.activeForeground": "#C3CCD5",
    "editor.selectionBackground": "#39434A",
    "editor.lineHighlightBackground": "#1B2025",
  },
});
export { monaco };
