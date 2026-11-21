//! Language Lab source anchors correspond to ide/internals.py, without
//! requiring changes to the C++ compiler or VM.
use serde::Serialize;
use std::{path::Path,process::Stdio};
use tokio::process::Command;

#[derive(Clone,Serialize)]
pub struct Target {pub keyword:String,pub path:String,pub anchor:String,
    pub line:usize,pub label:String}
const MAP:&[(&str,&str,&str,&str)]=&[
 ("if","src/compiler/statements.cpp","void Compiler::parseIf()","compiler"),
 ("else","src/compiler/statements.cpp","void Compiler::parseIf()","compiler"),
 ("while","src/compiler/statements.cpp","void Compiler::parseWhile()","compiler"),
 ("func","src/compiler/statements.cpp","void Compiler::parseFunctionDef(","compiler"),
 ("proc","src/compiler/statements.cpp","void Compiler::parseFunctionDef(","compiler"),
 ("print","src/compiler/expressions.cpp","void Compiler::parseOperand()","compiler"),
 ("go","src/compiler/statements.cpp","if (checkKeyword(\"go\"))","compiler"),
 ("sync","src/compiler/statements.cpp","if (checkKeyword(\"sync\"))","compiler"),
 ("return","src/compiler/statements.cpp","if (checkKeyword(\"return\"))","compiler"),
 ("lock","src/compiler/statements.cpp","if (checkKeyword(\"lock\"))","compiler"),
 ("unlock","src/compiler/statements.cpp","if (checkKeyword(\"unlock\"))","compiler"),
 ("int","src/compiler/statements.cpp","if (checkKeyword(\"int\"))","compiler"),
 ("float","src/compiler/statements.cpp","else if (checkKeyword(\"float\"))","compiler"),
 ("double","src/compiler/statements.cpp","else if (checkKeyword(\"double\"))","compiler"),
 ("len","src/compiler/expressions.cpp","void Compiler::parseOperand()","compiler"),
 ("resize","src/compiler/expressions.cpp","void Compiler::parseOperand()","compiler"),
 ("sin","src/compiler/expressions.cpp","void Compiler::parseOperand()","compiler"),
 ("cos","src/compiler/expressions.cpp","void Compiler::parseOperand()","compiler"),
 ("pow","src/compiler/expressions.cpp","void Compiler::parseOperand()","compiler"),
 ("fact","src/compiler/expressions.cpp","void Compiler::parseOperand()","compiler"),
 ("multifact","src/compiler/expressions.cpp","void Compiler::parseOperand()","compiler"),
 ("if","src/vm/executor.cpp","case OpCode::Jz:","runtime"),
 ("while","src/vm/executor.cpp","case OpCode::Jz:","runtime"),
 ("print","src/vm/builtins.cpp","if (c.name == \"print\")","runtime"),
 ("go","src/vm/executor.cpp","case OpCode::GoCall:","runtime"),
 ("sync","src/vm/executor.cpp","case OpCode::Sync:","runtime"),
 ("return","src/vm/executor.cpp","case OpCode::Return:","runtime"),
];
pub fn targets(root:&Path,keyword:&str)->Result<Vec<Target>,String>{
  let mut rows=Vec::new();
  for &(key,path,anchor,label) in MAP {
    if key!=keyword{continue;}
    let source=std::fs::read_to_string(root.join(path)).map_err(|e|e.to_string())?;
    let offset=source.find(anchor).ok_or(format!("C++ source anchor missing: {anchor}"))?;
    rows.push(Target{keyword:key.into(),path:path.into(),anchor:anchor.into(),
      label:label.into(),line:source[..offset].bytes().filter(|b|*b==b'\n').count()+1});
  }
  Ok(rows)
}
pub fn checkout(root:&Path)->bool{
 ["CMakeLists.txt","ide/runner.cpp","include/plusminus/api.hpp",
  "src/compiler/statements.cpp","src/vm/executor.cpp"].iter()
  .all(|p|root.join(p).is_file())
}
pub async fn rebuild(root:&Path)->Result<String,String>{
 if !checkout(root){return Err("Select a PlusMinus source checkout to rebuild C++".into());}
 let build=root.join("build/studio5");
 let mut log=String::new();
 for args in [vec!["-S",root.to_str().ok_or("Non-UTF8 checkout path")?,
                 "-B",build.to_str().ok_or("Non-UTF8 build path")?],
              vec!["--build",build.to_str().ok_or("Non-UTF8 build path")?,
                   "--config","Release","--parallel","2"]]{
    let output=tokio::time::timeout(std::time::Duration::from_secs(240),
      Command::new("cmake").args(&args).stdin(Stdio::null()).kill_on_drop(true).output()
    ).await.map_err(|_|"CMake timed out".to_string())?
     .map_err(|e|format!("Cannot run CMake: {e}"))?;
    if output.stdout.len()>2*1024*1024||output.stderr.len()>1024*1024{
       return Err("CMake log output exceeds limit".into());
    }
    log.push_str(&String::from_utf8_lossy(&output.stdout));
    log.push_str(&String::from_utf8_lossy(&output.stderr));
    if !output.status.success(){return Err(format!("CMake failed ({}): {}",output.status,log));}
 }
 Ok(log)
}
