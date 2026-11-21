// Lexical-only hints equivalent in intent to ide/source_diagnostics.py.
// The authoritative compiler errors remain provided by C++ runner.
export interface StaticDiagnostic {
  code:string;severity:"error"|"warning"|"info";phase:"static";
  confidence:"lexical";line:number;column:number;message:string;
}
function maskedSource(source:string):string {
  const result=source.split("");
  let state:"code"|"line"|"block"|"string"="code";
  for(let i=0;i<source.length;i++){
    const x=source[i],next=source[i+1]??"";
    if(state==="code"){
      if(x==="/"&&next==="/"){result[i]=" ";result[i+1]=" ";i++;state="line";continue;}
      if(x==="/"&&next==="*"){result[i]=" ";result[i+1]=" ";i++;state="block";continue;}
      if(x==='"'){result[i]=" ";state="string";continue;}
    }else if(state==="line"){
      if(x==="\n")state="code";else result[i]=" ";
    }else if(state==="block"){
      if(x==="*"&&next==="/"){result[i]=" ";result[i+1]=" ";i++;state="code";}
      else if(x!=="\n")result[i]=" ";
    }else{
      if(x==="\\"&&i+1<source.length){result[i]=" ";result[i+1]=" ";i++;continue;}
      if(x==='"')state="code";
      if(x!=="\n")result[i]=" ";
    }
  }
  return result.join("");
}
function position(source:string,index:number){
  const prefix=source.slice(0,index);
  const line=prefix.split("\n").length;
  const last=prefix.lastIndexOf("\n");
  return {line,column:index-last};
}
export function diagnose(source:string):StaticDiagnostic[]{
  const masked=maskedSource(source),stack:{token:string;index:number}[]=[];
  const result:StaticDiagnostic[]=[];
  const closes:Record<string,string>={")":"(","]":"[","}":"{"};
  const add=(index:number,severity:StaticDiagnostic["severity"],code:string,message:string)=>{
    result.push({severity,code,message,phase:"static",confidence:"lexical",...position(source,index)});
  };
  let depth=0,maxDepth=0;
  for(let i=0;i<masked.length;i++){
    const token=masked[i];
    if("([{".includes(token)){stack.push({token,index:i});if(token==="{")maxDepth=Math.max(maxDepth,++depth);}
    else if(")]}".includes(token)){
      if(!stack.length||stack[stack.length-1].token!==closes[token])add(i,"error","PM1002","Unexpected closing bracket "+token);
      else stack.pop();
      if(token==="}")depth=Math.max(0,depth-1);
    }
  }
  for(const x of stack)add(x.index,"error","PM1001","Unclosed bracket "+x.token);
  if(/\bgo\b/.test(masked)&&!/\bsync\b/.test(masked)){
    add(masked.search(/\bgo\b/),"warning","PM3001","Concurrent call without explicit sync");
  }
  const lock=masked.match(/\block\b/g)?.length??0,unlock=masked.match(/\bunlock\b/g)?.length??0;
  if(lock!==unlock){add(Math.max(0,masked.search(/\block\b/)),"warning","PM3002","Lock/unlock counts differ");}
  if(maxDepth>=5)add(0,"info","PM4001","High block nesting: "+maxDepth);
  return result.sort((a,b)=>a.line-b.line||a.column-b.column||a.code.localeCompare(b.code));
}
