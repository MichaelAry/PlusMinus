import * as monaco from "monaco-editor";
import EditorWorker from "monaco-editor/esm/vs/editor/editor.worker?worker";

(globalThis as typeof globalThis & {
  MonacoEnvironment?: { getWorker: (_: string, label: string) => Worker }
}).MonacoEnvironment = {
  getWorker: () => new EditorWorker(),
};

monaco.languages.register({ id: "plusminus", extensions: [".pm"] });
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
