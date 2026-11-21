// Bounded, non-AST completion like the original Qt editor's vocabulary hints.
// No unsupported language syntax or external language server is implied.
export const plusminusKeywords=[
  "if","else","while","func","proc","return","go","sync","lock","unlock",
  "int","float","double","print","len","resize","sin","cos","pow","fact","multifact",
] as const;
export function completionCandidates(source:string,prefix:string,limit=100):string[] {
  const partial=source.slice(0,160_000);
  // Ignore comments when collecting user identifiers; this is lexical only.
  const code=partial.replace(/\/\/[^\n]*|\/\*[\s\S]*?\*\//g," ");
  const candidates=code.match(/\b[A-Za-z_]\w*\b/g)??[];
  const lower=prefix.toLowerCase();
  return [...new Set<string>([...plusminusKeywords,...candidates])]
    .filter(word=>word!==prefix && word.toLowerCase().startsWith(lower))
    .slice(0,Math.max(0,Math.min(100,limit)));
}
