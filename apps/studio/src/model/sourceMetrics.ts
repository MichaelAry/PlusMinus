// A lexical source analyzer, explicitly NOT a compiler AST.
export interface SourceMetrics {
  lines:number;code_lines:number;comments:number;functions:number;procedures:number;
  function_names:string[];variables:number;branches:number;loops:number;go_calls:number;
  sync:number;locks:number;max_nesting:number;complexity_estimate:number;
  warnings:string[];method:string;
}
const words=new Set(["if","else","while","func","proc","return","go","sync","lock","unlock",
  "print","len","resize","sin","cos","pow","fact","multifact"]);
function sanitize(source:string):{masked:string;comments:number}{
  const chars=source.split("");
  let comments=0;
  let i=0;
  while(i<source.length){
    let end=i;
    if(source.startsWith("//",i)){
      comments++;end=source.indexOf("\n",i);
      if(end<0)end=source.length;
    }else if(source.startsWith("/*",i)){
      comments++;const close=source.indexOf("*/",i+2);
      end=close<0?source.length:close+2;
    }else if(source[i]==='"'||source[i]==="'"){
      const quote=source[i];
      end=i+1;
      while(end<source.length){
        if(source[end]==="\\")end+=2;
        else if(source[end]===quote){end++;break;}
        else end++;
      }
      end=Math.min(end,source.length);
    }else{i++;continue;}
    for(let j=i;j<end;j++)if(source[j]!=="\n")chars[j]=" ";
    i=end;
  }
  return {masked:chars.join(""),comments};
}
export function analyzeSource(source:string):SourceMetrics{
  const {masked,comments}=sanitize(source);
  const tokens=masked.match(/\b[A-Za-z_]\w*\b/g)??[];
  const counts=new Map<string,number>();
  for(const token of tokens)if(words.has(token))counts.set(token,(counts.get(token)??0)+1);
  const count=(key:string)=>counts.get(key)??0;
  const function_names=[...masked.matchAll(/\b(?:func|proc)\s+([A-Za-z_]\w*)/g)].map(x=>x[1]);
  const variables=new Set([...masked.matchAll(/(?<![=!<>])\b([A-Za-z_]\w*)\s*=(?!=)/g)]
    .map(x=>x[1]).filter(key=>!words.has(key)));
  let nesting=0,max_nesting=0;
  for(const ch of masked){
    if(ch==="{"){nesting++;max_nesting=Math.max(max_nesting,nesting);}
    if(ch==="}")nesting=Math.max(0,nesting-1);
  }
  const warnings:string[]=[];
  if(max_nesting>=5)warnings.push("High syntactic nesting depth: "+max_nesting);
  if(count("go")&&!count("sync"))warnings.push("Concurrent call without explicit sync");
  if(count("lock")!==count("unlock"))warnings.push("Lock/unlock counts differ");
  const code_lines=masked.split("\n").filter(x=>x.trim().length>0).length;
  if(code_lines>=300)warnings.push("Large source file: consider extracting functions");
  return {
    lines:source.split(/\r?\n/).length,code_lines,comments,
    functions:count("func"),procedures:count("proc"),function_names,
    variables:variables.size,branches:count("if"),loops:count("while"),
    go_calls:count("go"),sync:count("sync"),locks:count("lock"),
    max_nesting,complexity_estimate:1+count("if")+count("while")+
      (masked.match(/&&|\|\|/g)?.length??0),warnings,
    method:"Lexical heuristic; not an AST correctness proof",
  };
}
