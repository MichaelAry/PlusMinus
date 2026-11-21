//! Restricted document operations for PlusMinus notebooks and checked-out C++ sources.
use serde::{Deserialize,Serialize};
use serde_json::Value;
use sha2::{Digest,Sha256};
use std::{fs,io::Write,path::{Component,Path,PathBuf}};

#[derive(Clone,Serialize,Deserialize)]
pub struct TextDocument {pub path:String,pub source:String,pub digest:String}

fn digest(bytes:&[u8])->String{format!("{:x}",Sha256::digest(bytes))}
fn category(relative:&str)->Result<&'static str,String>{
 let p=Path::new(relative);
 if p.as_os_str().is_empty()||!p.components().all(|c|matches!(c,Component::Normal(_))){
   return Err("Only workspace-relative paths are allowed".into());
 }
 match p.extension().and_then(|x|x.to_str()) {
   Some("ipynb")=>"notebook",
   Some("pm")=>"pm",
   Some("cpp"|"hpp"|"h")=>{
       let allowed=relative.starts_with("src/")||relative.starts_with("include/")||
         relative.starts_with("tests/cpp/")||relative.starts_with("tests/portable/")||
         relative=="ide/runner.cpp"||relative=="Parser.h";
       if !allowed{return Err("C++ file outside language source tree".into());}
       "cpp"
   }
   _=>return Err("Unsupported document extension".into()),
 }.pipe(Ok)
}
trait Pipe:Sized {fn pipe<R>(self,f:impl FnOnce(Self)->R)->R{f(self)}}
impl<T> Pipe for T {}

fn safe_path(root:&Path,relative:&str,create:bool)->Result<PathBuf,String>{
 category(relative)?;
 let p=root.join(relative);
 let parent=p.parent().ok_or("No file parent")?.canonicalize().map_err(|e|e.to_string())?;
 if !parent.starts_with(root){return Err("Path escapes workspace".into());}
 if p.exists(){
    let actual=p.canonicalize().map_err(|e|e.to_string())?;
    if !actual.starts_with(root)||!actual.is_file(){return Err("File is outside workspace or is not a file".into());}
    Ok(actual)
 } else if create {Ok(p)} else {Err("File does not exist".into())}
}

pub fn check_notebook(value:&Value)->Result<(),String>{
 if value["nbformat"]!=4{return Err("Expected nbformat v4".into());}
 if !value["cells"].is_array(){return Err("Missing cells array".into());}
 let cells=value["cells"].as_array().ok_or("Invalid cells")?;
 if cells.len()>2000{return Err("Notebook contains more than 2000 cells".into());}
 let kernel=value.pointer("/metadata/kernelspec/name").and_then(Value::as_str).unwrap_or("");
 if !kernel.is_empty()&&!kernel.starts_with("plusminus"){
    return Err("Notebook uses a different kernel".into());
 }
 let lang=value.pointer("/metadata/language_info/name").and_then(Value::as_str).unwrap_or("");
 if !lang.is_empty()&&lang!="plusminus"{return Err("Notebook language is not PlusMinus".into());}
 for c in cells {
    if !matches!(c["cell_type"].as_str(),Some("code"|"markdown")) {return Err("Unsupported cell type".into());}
    if !c["metadata"].is_object(){return Err("Cell metadata must be object".into());}
    let source_ok=c["source"].is_string()||c["source"].as_array()
      .is_some_and(|a|a.iter().all(Value::is_string));
    if !source_ok {return Err("Cell source must be string or string array".into());}
    if c["cell_type"]=="code" && !c["outputs"].as_array()
      .is_some_and(|a|a.iter().all(Value::is_object)){return Err("Invalid code cell outputs".into());}
 }
 Ok(())
}

pub fn open(root:&Path,relative:&str)->Result<TextDocument,String>{
 let p=safe_path(root,relative,false)?;
 let max=if category(relative)?=="notebook"{32*1024*1024}else{4*1024*1024};
 if fs::metadata(&p).map_err(|e|e.to_string())?.len()>max{return Err("Document exceeds size limit".into());}
 let bytes=fs::read(&p).map_err(|e|e.to_string())?;
 let text=String::from_utf8(bytes.clone()).map_err(|_|"Document not UTF-8")?;
 if category(relative)?=="notebook"{
    let parsed:Value=serde_json::from_str(text.trim_start_matches('\u{feff}'))
       .map_err(|e|e.to_string())?;
    check_notebook(&parsed)?;
 }
 Ok(TextDocument{path:relative.into(),source:text,digest:digest(&bytes)})
}

pub fn save(root:&Path,relative:&str,source:&str,expected:&str)->Result<TextDocument,String>{
 let category=category(relative)?;
 if source.len() > (if category=="notebook"{32*1024*1024}else{4*1024*1024}) {
    return Err("Document exceeds size limit".into());
 }
 if category=="notebook"{
    let value:Value=serde_json::from_str(source.trim_start_matches('\u{feff}')).map_err(|e|e.to_string())?;
    check_notebook(&value)?;
 }
 let p=safe_path(root,relative,false)?;
 let old=fs::read(&p).map_err(|e|e.to_string())?;
 if digest(&old)!=expected{return Err("Document changed externally; reopen before writing".into());}
 let parent=p.parent().ok_or("Missing parent")?;
 let candidate=parent.join(format!(".studio5-save-{}-{}",std::process::id(),now_nanos()));
 let result=(||->Result<(),String>{
   let mut out=fs::OpenOptions::new().create_new(true).write(true).open(&candidate)
       .map_err(|e|e.to_string())?;
   out.write_all(source.as_bytes()).map_err(|e|e.to_string())?;
   out.sync_all().map_err(|e|e.to_string())?;
   // QFile-like backup-and-replace: on Windows rename over an existing file
   // fails. Keep original if replacement fails; never silently truncate it.
   #[cfg(windows)]
   {
     let backup=parent.join(format!(".studio5-backup-{}-{}",std::process::id(),now_nanos()));
     fs::rename(&p,&backup).map_err(|e|e.to_string())?;
     if let Err(e)=fs::rename(&candidate,&p){
       let _=fs::rename(&backup,&p);
       return Err(e.to_string());
     }
     let _=fs::remove_file(&backup);
   }
   #[cfg(not(windows))]
   fs::rename(&candidate,&p).map_err(|e|e.to_string())?;
   Ok(())
 })();
 if result.is_err(){let _=fs::remove_file(&candidate);}
 result?;
 Ok(TextDocument{path:relative.into(),source:source.into(),digest:digest(source.as_bytes())})
}

pub fn create(root:&Path,relative:&str,source:&str)->Result<TextDocument,String>{
 if category(relative)?!="notebook"{return Err("Only notebook creation is supported here".into());}
 let value:Value=serde_json::from_str(source).map_err(|e|e.to_string())?;
 check_notebook(&value)?;
 let p=safe_path(root,relative,true)?;
 if p.exists(){return Err("File already exists".into());}
 fs::OpenOptions::new().create_new(true).write(true).open(&p)
  .and_then(|mut f|f.write_all(source.as_bytes())).map_err(|e|e.to_string())?;
 Ok(TextDocument{path:relative.into(),source:source.into(),digest:digest(source.as_bytes())})
}

fn now_nanos()->u128{
 use std::time::{SystemTime,UNIX_EPOCH};
 SystemTime::now().duration_since(UNIX_EPOCH).unwrap_or_default().as_nanos()
}

pub fn is_cpp_file(relative:&str)->bool{category(relative).is_ok_and(|s|s=="cpp")}

#[cfg(test)]
mod tests {
 use super::*;
 #[test]fn traversal_rejected(){assert!(category("../src/vm.cpp").is_err());assert!(category("/etc/a.cpp").is_err());}
 #[test]fn notebook_round_trip_conflict_and_metadata_preservation(){
   let nonce=std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH)
      .unwrap().as_nanos();
   let root=std::env::temp_dir().join(format!("studio5-notebook-{}-{nonce}",std::process::id()));
   fs::create_dir(&root).unwrap();
   let input=serde_json::json!({
      "nbformat":4,"nbformat_minor":5,
      "metadata":{"language_info":{"name":"plusminus"},"custom":{"note":"preserve"}},
      "cells":[{"cell_type":"code","id":"cell-1","metadata":{},
          "source":["print(0);\n"],"execution_count":null,"outputs":[]}]
   }).to_string();
   let created=create(&root,"research.ipynb",&input).unwrap();
   assert_eq!(open(&root,"research.ipynb").unwrap().source,input);
   let new=serde_json::json!({
      "nbformat":4,"nbformat_minor":5,
      "metadata":{"language_info":{"name":"plusminus"},"custom":{"note":"preserve"}},
      "cells":[{"cell_type":"code","id":"cell-1","metadata":{},
          "source":"print(1);","execution_count":1,"outputs":[{
            "output_type":"stream","name":"stdout","text":"1\n"}]}]
   }).to_string();
   let saved=save(&root,"research.ipynb",&new,&created.digest).unwrap();
   assert_eq!(open(&root,"research.ipynb").unwrap().source,new);
   assert!(save(&root,"research.ipynb",&input,&created.digest).is_err());
   assert_eq!(open(&root,"research.ipynb").unwrap().digest,saved.digest);
   assert!(open(&root,"../research.ipynb").is_err());
   fs::remove_dir_all(&root).unwrap();
 }

 #[test]fn foreign_kernel_rejected(){
   let x=serde_json::json!({"nbformat":4,"metadata":{"kernelspec":{"name":"python3"}},
      "cells":[]});
   assert!(check_notebook(&x).is_err());
 }
}
