//! Language Lab source anchors correspond to ide/internals.py, without
//! requiring changes to the C++ compiler or VM.
use serde::{Deserialize,Serialize};
use sha2::{Digest,Sha256};
use tauri::{AppHandle,Manager};
use std::fs;
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

/** Content digest for the *built native engine*. Unlike the historical Qt
 * session source_hash, this also covers runner, CMake and test generator. */
pub fn build_fingerprint(root:&Path)->Result<String,String>{
  let mut digest=Sha256::new();
  for folder in ["src","include","tests/cpp","tests/portable"]{
    let base=root.join(folder);
    if !base.exists(){continue;}
    let mut paths=Vec::new();
    for entry in walkdir::WalkDir::new(base).follow_links(false){
      let entry=entry.map_err(|e|e.to_string())?;
      if entry.file_type().is_file()&&
        matches!(entry.path().extension().and_then(|s|s.to_str()),Some("cpp"|"hpp"|"h")){
        paths.push(entry.into_path());
      }
    }
    paths.sort();
    for p in paths {
      let relative=p.strip_prefix(root).map_err(|e|e.to_string())?;
      digest.update(relative.to_string_lossy().as_bytes());
      digest.update(fs::read(&p).map_err(|e|e.to_string())?);
    }
  }
  for relative in ["CMakeLists.txt","ide/CMakeLists.txt","ide/runner.cpp",
    "Parser.h","tools/generate_native_tests.py"] {
    let p=root.join(relative);
    if p.is_file(){
      digest.update(relative.replace('/',std::path::MAIN_SEPARATOR_STR).as_bytes());
      digest.update(fs::read(&p).map_err(|e|e.to_string())?);
    }
  }
  Ok(format!("{:x}",digest.finalize()))
}
#[derive(Deserialize)]
struct SourceManifest {schema:u32,sha256:String}
/// Sidecars and manifest must originate from the same staged CMake build.
pub fn packaged_fingerprint(app:&AppHandle)->Result<String,String>{
  let mut candidates=Vec::new();
  if let Ok(resources)=app.path().resource_dir(){
    candidates.push(resources.join("binaries/source-fingerprint.json"));
    candidates.push(resources.join("source-fingerprint.json"));
  }
  if let Ok(exe)=std::env::current_exe(){
    if let Some(parent)=exe.parent(){
      candidates.push(parent.join("binaries/source-fingerprint.json"));
    }
  }
  candidates.push(Path::new(env!("CARGO_MANIFEST_DIR")).join("binaries/source-fingerprint.json"));
  for path in candidates {
    if let Ok(bytes)=fs::read(path){
      if let Ok(manifest)=serde_json::from_slice::<SourceManifest>(&bytes){
        if manifest.schema==1&&manifest.sha256.len()==64&&
           manifest.sha256.bytes().all(|b|b.is_ascii_hexdigit()){
          return Ok(manifest.sha256);
        }
      }
    }
  }
  Err("Missing C++ sidecar source manifest; rebuild native sidecars".into())
}
#[cfg(test)]
mod fingerprint_tests{
  use super::*;
  #[test] fn changed_cpp_source_invalidates_build_fingerprint(){
    let root=std::env::temp_dir().join(format!("studio5-fp-{}-{}",
      std::process::id(),
      std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));
    fs::create_dir_all(root.join("src")).unwrap();
    fs::write(root.join("src/engine.cpp"),"int value=1;").unwrap();
    let first=build_fingerprint(&root).unwrap();
    fs::write(root.join("src/engine.cpp"),"int value=2;").unwrap();
    assert_ne!(first,build_fingerprint(&root).unwrap());
    fs::remove_dir_all(root).unwrap();
  }
  #[test] fn native_stage_manifest_matches_real_checkout_when_staged(){
    let staged=Path::new(env!("CARGO_MANIFEST_DIR")).join("binaries/source-fingerprint.json");
    if !staged.is_file(){return;} // Running cargo test before initial staging is supported.
    let json:serde_json::Value=serde_json::from_slice(&fs::read(staged).unwrap()).unwrap();
    let root=Path::new(env!("CARGO_MANIFEST_DIR")).ancestors().nth(3).unwrap();
    assert_eq!(json["sha256"],build_fingerprint(root).unwrap());
  }
}
