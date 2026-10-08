use std::{fs,path::{Path,PathBuf},process::{Command,Stdio},io::Write,time::{Duration,Instant}};
use serde_json::Value;
use sha2::{Digest,Sha256};
use std::os::windows::process::CommandExt;
pub fn read(root:&Path)->Result<Value,String>{
 let pointer=root.join("versions/CURRENT.json");if pointer.is_file(){return serde_json::from_slice(&fs::read(pointer).map_err(|e|e.to_string())?).map_err(|e|e.to_string())}
 // A standalone candidate has one explicit manifest, not a guessed directory.
 let identity:Value=serde_json::from_slice(&fs::read(root.join("build-identity.json")).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
 let id=identity["buildId"].as_str().ok_or("Portable build identity missing")?;
 Ok(serde_json::json!({"activeBuildId":id,"previousBuildId":null,"versions":{id:{"directory":".","identity":identity}}}))
}
pub fn selected(root:&Path,previous:bool)->Result<(PathBuf,Value),String>{
 let state=read(root)?;let id=state[if previous{"previousBuildId"}else{"activeBuildId"}].as_str().ok_or("No selected version")?;
 let entry=&state["versions"][id];let rel=entry["directory"].as_str().ok_or("Missing version directory")?;
 let folder=root.join(rel).canonicalize().map_err(|e|e.to_string())?;if root.join("versions/CURRENT.json").is_file(){let versions=root.join("versions").canonicalize().map_err(|e|e.to_string())?;
 if !folder.starts_with(&versions)||folder==versions{return Err("Version directory escapes versions".into())}}else if folder!=root.canonicalize().map_err(|e|e.to_string())?{return Err("Portable runtime must match its own manifest".into())}
 let identity:Value=serde_json::from_slice(&fs::read(folder.join("build-identity.json")).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
 if identity!=entry["identity"]||identity["buildId"]!=id{return Err("Active record and runtime identity disagree".into())}
 let exe=folder.join("Biodiversity Workbench.exe");
 if format!("{:x}",Sha256::digest(fs::read(&exe).map_err(|e|e.to_string())?))!=identity["executableSHA256"].as_str().ok_or("Missing executable hash")?{return Err("Runtime executable hash mismatch".into())}
 let frozen:Value=serde_json::from_slice(&fs::read(folder.join("engine/_internal/web/build-identity.json")).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
 for key in ["version","buildId","sourceFingerprint"]{if frozen[key]!=identity[key]{return Err(format!("Engine identity mismatch: {key}"))}}
 Ok((exe,identity))
}
pub fn launch(root:&Path,args:&[String],expected_id:Option<&str>)->Result<Value,String>{
 let(exe,expected)=selected(root,false)?;
 if expected_id.is_some_and(|id|expected["buildId"].as_str()!=Some(id)){return Err("The active build changed. Recheck the launcher before opening Workbench.".into())}
 let data=std::env::var_os("WORKBENCH_DESKTOP_DATA").map(PathBuf::from).unwrap_or_else(||PathBuf::from(std::env::var_os("LOCALAPPDATA").unwrap()).join("Biodiversity Data Rescue Workbench/projects-data"));
 let log=data.parent().unwrap().join("logs/engine.log");let before=fs::metadata(&log).ok().and_then(|m|m.modified().ok());
 let mut child=Command::new(&exe).args(args).current_dir(exe.parent().unwrap()).creation_flags(0x08000000).stdin(Stdio::null()).spawn().map_err(|e|e.to_string())?;
 let started=Instant::now();
 while started.elapsed()<Duration::from_secs(60){
  if let Some(exit)=child.try_wait().map_err(|e|e.to_string())?{return Err(format!("Workbench exited before identity handshake: {exit}. Close another running Workbench before switching builds."))}
  if fs::metadata(&log).ok().and_then(|m|m.modified().ok())!=before{
   if let Ok(text)=fs::read_to_string(&log){if let Some(line)=text.lines().find_map(|l|l.strip_prefix("Build identity: ")){if let Ok(actual)=serde_json::from_str::<Value>(line){
    if actual["buildId"]!=expected["buildId"]||actual["version"]!=expected["version"]{return Err("Running scientific engine failed the version handshake".into())}
    let record=serde_json::json!({"expected":expected,"observed":actual,"processId":child.id(),"executable":exe,"phase":"engine-identity-observed"});
    let path=root.join("artifacts/qa/reconstruction/last-launch.json");fs::create_dir_all(path.parent().unwrap()).map_err(|e|e.to_string())?;let mut f=fs::File::create(path).map_err(|e|e.to_string())?;f.write_all(serde_json::to_string_pretty(&record).unwrap().as_bytes()).map_err(|e|e.to_string())?;return Ok(record)
   }}}
  }
  std::thread::sleep(Duration::from_millis(200));
 }
 Err("Workbench identity handshake timed out; no successful launch recorded".into())
}

#[cfg(test)] mod tests {
 use super::*;
 fn fixture()->PathBuf{static NEXT:std::sync::atomic::AtomicU64=std::sync::atomic::AtomicU64::new(0);let serial=NEXT.fetch_add(1,std::sync::atomic::Ordering::Relaxed);let path=std::env::temp_dir().join(format!("bio-launcher-test-{}-{}-{}",std::process::id(),std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos(),serial));fs::create_dir_all(path.join("engine/_internal/web")).unwrap();fs::write(path.join("Biodiversity Workbench.exe"),b"synthetic executable").unwrap();let identity=serde_json::json!({"buildId":"synthetic-build","version":"0.7.0-dev.0","sourceFingerprint":"synthetic","executableSHA256":format!("{:x}",Sha256::digest(b"synthetic executable"))});fs::write(path.join("build-identity.json"),serde_json::to_vec(&identity).unwrap()).unwrap();fs::write(path.join("engine/_internal/web/build-identity.json"),serde_json::to_vec(&identity).unwrap()).unwrap();path}
 #[test] fn portable_uses_exact_manifest_and_rejects_tampered_executable(){let root=fixture();assert_eq!(selected(&root,false).unwrap().1["buildId"],"synthetic-build");assert!(selected(&root,true).is_err());fs::write(root.join("Biodiversity Workbench.exe"),b"tampered").unwrap();assert!(selected(&root,false).is_err());fs::remove_dir_all(root).unwrap();}
 #[test] fn corrupt_canonical_pointer_never_falls_back_to_portable(){let root=fixture();fs::create_dir(root.join("versions")).unwrap();fs::write(root.join("versions/CURRENT.json"),b"corrupt").unwrap();assert!(selected(&root,false).is_err());fs::remove_dir_all(root).unwrap();}
 #[test] fn canonical_path_escape_is_rejected(){let root=fixture();fs::create_dir(root.join("versions")).unwrap();let id=read(&root).unwrap();fs::write(root.join("versions/CURRENT.json"),serde_json::to_vec(&id).unwrap()).unwrap();assert!(selected(&root,false).is_err());fs::remove_dir_all(root).unwrap();}
}
