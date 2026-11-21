//! User-defined Studio 4 test cases. Original ~/.plusminus/user_tests.json
//! is never modified. Studio 5 uses a copy with optimistic concurrency.
use serde::{Serialize,Deserialize};
use sha2::{Digest,Sha256};
use std::{fs,io::Write,path::{Path,PathBuf}};
use tauri_plugin_dialog::DialogExt;
use tauri::AppHandle;

#[derive(Clone,Serialize,Deserialize)]
pub struct UserCase {
  pub name:String,pub source:String,pub kind:String,pub expected:String,
  #[serde(default="default_mode")] pub mode:String,
  #[serde(default="default_true")] pub expect_ok:bool,
  #[serde(default="default_timeout")] pub timeout:f64,
}
fn default_mode()->String{"run".into()}
fn default_true()->bool{true}
fn default_timeout()->f64{5.0}

#[derive(Serialize,Deserialize)]
pub struct UserBundle {pub cases:Vec<UserCase>,pub revision:String}
fn hash(data:&[u8])->String{format!("{:x}",Sha256::digest(data))}
fn home()->Result<PathBuf,String>{
  let home=dirs::home_dir().ok_or("Home folder unavailable")?;
  let dir=home.join(".plusminus");
  fs::create_dir_all(&dir).map_err(|e|e.to_string())?;
  Ok(dir)
}
fn validate(cases:&[UserCase])->Result<(),String>{
  if cases.len()>500{return Err("Maximum 500 user tests".into());}
  for c in cases{
    if c.name.trim().is_empty()||c.name.len()>180||c.source.len()>1024*1024||c.expected.len()>1024*1024{
      return Err("Invalid user test size or name".into());
    }
    if !["output","result","bytecode_contains","error_contains"].contains(&c.kind.as_str()){
      return Err("Invalid user test expected-value kind".into());
    }
    if !["run","compile","profile","trace"].contains(&c.mode.as_str()){
      return Err("Invalid test run mode".into());
    }
    if !c.timeout.is_finite() || c.timeout<0.1||c.timeout>300.0{
      return Err("Invalid test timeout".into());
    }
  }
  Ok(())
}
fn from_bytes(data:&[u8])->Result<Vec<UserCase>,String>{
  let cases:Vec<UserCase>=serde_json::from_slice(data).map_err(|e|e.to_string())?;
  validate(&cases)?;Ok(cases)
}
fn path()->Result<PathBuf,String>{
  let dir=home()?;
  let new=dir.join("user_tests-v5.json");
  if !new.exists(){
    let original=dir.join("user_tests.json");
    let initial=if original.is_file(){
      let bytes=fs::read(&original).map_err(|e|e.to_string())?;
      if bytes.len()>4*1024*1024{return Err("Original user test file too large".into());}
      let cases=from_bytes(&bytes)?;
      serde_json::to_vec_pretty(&cases).map_err(|e|e.to_string())?
    }else{b"[]".to_vec()};
    match fs::OpenOptions::new().write(true).create_new(true).open(&new){
      Ok(mut f)=>{f.write_all(&initial).map_err(|e|e.to_string())?;f.sync_all().map_err(|e|e.to_string())?;}
      Err(e) if e.kind()==std::io::ErrorKind::AlreadyExists=>{},
      Err(e)=>return Err(e.to_string())
    }
  }
  Ok(new)
}
pub fn list()->Result<UserBundle,String>{
  let data=fs::read(path()?).map_err(|e|e.to_string())?;
  let cases=from_bytes(&data)?;
  Ok(UserBundle{cases,revision:hash(&data)})
}
pub fn save(cases:Vec<UserCase>,expected_revision:String)->Result<UserBundle,String>{
  validate(&cases)?;
  let target=path()?;
  let old=fs::read(&target).map_err(|e|e.to_string())?;
  if hash(&old)!=expected_revision{return Err("User test file was changed elsewhere; reload".into());}
  let new=serde_json::to_vec_pretty(&cases).map_err(|e|e.to_string())?;
  let tmp=target.with_extension(format!("{}.tmp",std::process::id()));
  let result=(||->Result<(),String>{
    let mut f=fs::OpenOptions::new().write(true).create_new(true).open(&tmp).map_err(|e|e.to_string())?;
    f.write_all(&new).map_err(|e|e.to_string())?;
    f.sync_all().map_err(|e|e.to_string())?;
    #[cfg(windows)]
    {
      let backup=target.with_extension(format!("{}.backup",std::process::id()));
      fs::rename(&target,&backup).map_err(|e|e.to_string())?;
      if let Err(e)=fs::rename(&tmp,&target){
        return Err(match fs::rename(&backup,&target){
          Ok(())=>e.to_string(),
          Err(restore)=>format!("Failed to save tests: {e}; original at {} (restore: {restore})",backup.display()),
        });
      }
      let _=fs::remove_file(&backup);
    }
    #[cfg(not(windows))]
    fs::rename(&tmp,&target).map_err(|e|e.to_string())?;
    Ok(())
  })();
  if result.is_err(){let _=fs::remove_file(&tmp);}
  result?;
  Ok(UserBundle{cases,revision:hash(&new)})
}
fn dialog_path(app:AppHandle,save_dialog:bool)->Result<PathBuf,String>{
  let selection=if save_dialog {
    app.dialog().file().add_filter("JSON",&["json"]).blocking_save_file()
  }else{
    app.dialog().file().add_filter("JSON",&["json"]).blocking_pick_file()
  };
  selection.ok_or("File selection canceled".to_string())?
    .into_path().map_err(|e|e.to_string())
}
pub fn import_file(app:AppHandle,expected:String)->Result<UserBundle,String>{
  let file=dialog_path(app,false)?;
  if fs::metadata(&file).map_err(|e|e.to_string())?.len()>4*1024*1024{
    return Err("Import file exceeds 4 MiB".into());
  }
  let imported=from_bytes(&fs::read(file).map_err(|e|e.to_string())?)?;
  let existing=list()?;
  if existing.revision!=expected{return Err("Test list changed externally; reload".into());}
  let mut cases=existing.cases;
  cases.extend(imported);
  save(cases,expected)
}
pub fn export_file(app:AppHandle)->Result<String,String>{
  let file=dialog_path(app,true)?;
  let bundle=list()?;
  let content=serde_json::to_vec_pretty(&bundle.cases).map_err(|e|e.to_string())?;
  // Never overwrite a file implicitly, including an original Studio 4 file.
  if file.exists(){return Err("Export destination exists; choose another filename".into());}
  let mut f=fs::OpenOptions::new().write(true).create_new(true).open(&file)
    .map_err(|e|e.to_string())?;
  f.write_all(&content).map_err(|e|e.to_string())?;
  Ok(file.to_string_lossy().to_string())
}
#[cfg(test)]
mod tests{
  use super::*;
  #[test]fn rejects_unknown_kind(){
    let case=UserCase{name:"x".into(),source:"print(1);".into(),kind:"unknown".into(),
      expected:String::new(),mode:"run".into(),expect_ok:true,timeout:5.0};
    assert!(validate(&[case]).is_err());
  }
  #[test]fn old_studio4_format_is_accepted(){
    let data=br#"[{"name":"A","source":"print(1);","kind":"output","expected":"1\n"}]"#;
    assert_eq!(from_bytes(data).unwrap()[0].mode,"run");
  }
}
