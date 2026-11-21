export interface GraphNode { id: string; label: string }
export interface GraphEdge { source: string; target: string; label: string }
export interface LanguageGraph { nodes: GraphNode[]; edges: GraphEdge[]; truncated: boolean; method: string }

export function bytecodeGraph(listing: string, limit=200): LanguageGraph {
  const all = [...listing.matchAll(/^\s*(\d+)\s+([A-Za-z_]\w*)(.*)$/gm)].map(m => ({
    ip: Number(m[1]), op: m[2], target: m[3].match(/->\s*(\d+)/)?.[1],
  }));
  const part = all.slice(0, limit), ids = new Set(part.map(x=>x.ip));
  const nodes = part.map(x=>({ id: String(x.ip), label: x.ip.toString().padStart(4,"0")+" · "+x.op }));
  const edges: GraphEdge[] = [];
  part.forEach((x,i) => {
    const next = part[i+1];
    if (x.op === "Halt" || x.op === "Return") return;
    if ((x.op === "Jmp" || x.op === "Jz") && x.target !== undefined && ids.has(Number(x.target)))
      edges.push({ source:String(x.ip),target:x.target,label:x.op });
    if (x.op !== "Jmp" && next) edges.push({source:String(x.ip),target:String(next.ip),label:"fallthrough"});
  });
  return {nodes, edges, truncated:all.length>limit, method:"Bytecode instruction control-flow graph"};
}

function maskNonCode(source:string):string{
  // Remove strings, // comments and /*...*/ without moving character offsets.
  return source.replace(/"(?:\\.|[^"\\])*"|\'(?:\\.|[^\'\\])*\'|\/\/[^\n]*|\/\*[\s\S]*?\*\//g,
    token=>token.replace(/[^\n]/g," "));
}
export function callGraph(source:string): LanguageGraph{
  const masked = maskNonCode(source);
  const declarations=[...masked.matchAll(/\b(?:func|proc)\s+([A-Za-z_]\w*)\s*\(/g)];
  const names=new Set(declarations.map(x=>x[1]));
  const nodes:GraphNode[]=[{id:"__main__",label:"Top level"},...[...names].sort().map(name=>({id:name,label:name+"()"}))];
  const edges:GraphEdge[]=[];
  const covered = masked.split("");
  for(const match of declarations){
    const start=masked.indexOf("{",match.index!+match[0].length);
    if(start<0)continue;
    let depth=0,end=start;
    for(let i=start;i<masked.length;i++){if(masked[i]==="{")depth++;if(masked[i]==="}"&&--depth===0){end=i+1;break;}}
    const body=masked.slice(start,end);
    for(const call of body.matchAll(/\b([A-Za-z_]\w*)\s*\(/g)){
      if(names.has(call[1]))edges.push({source:match[1],target:call[1],label:"call"});
    }
    for(let i=match.index!;i<end;i++)covered[i]=" ";
  }
  for(const call of covered.join("").matchAll(/\b([A-Za-z_]\w*)\s*\(/g)){
    if(names.has(call[1]))edges.push({source:"__main__",target:call[1],label:"call"});
  }
  const unique=[...new Map(edges.map(e=>[e.source+"/"+e.target,e])).values()];
  return {nodes,edges:unique,truncated:false,method:"Heuristic source-level function call graph (not compiler AST)"};
}
