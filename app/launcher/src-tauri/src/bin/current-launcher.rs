#![windows_subsystem = "windows"]
use std::{fs,process::Command};use serde_json::Value;use sha2::{Digest,Sha256};use std::os::windows::process::CommandExt;
fn run()->Result<(),String>{let exe=std::env::current_exe().map_err(|e|e.to_string())?;let root=exe.parent().unwrap();let state:Value=serde_json::from_slice(&fs::read(root.join("versions/CURRENT.json")).map_err(|e|e.to_string())?).map_err(|e|e.to_string())?;
 let path=root.join(state["launcher"]["path"].as_str().ok_or("Missing active launcher")?).canonicalize().map_err(|e|e.to_string())?;let allowed=root.join("app/launcher/runtime").canonicalize().map_err(|e|e.to_string())?;
 if !path.starts_with(allowed){return Err("Launcher path escapes its runtime directory".into())}
 if format!("{:x}",Sha256::digest(fs::read(&path).map_err(|e|e.to_string())?))!=state["launcher"]["sha256"].as_str().ok_or("Missing launcher checksum")?{return Err("Launcher checksum mismatch".into())}
 let mut command=Command::new(path);command.current_dir(root).creation_flags(0x08000000);
 if std::env::var_os("WORKBENCH_VERIFY_CURRENT").is_some(){let code=command.status().map_err(|e|e.to_string())?;if !code.success(){return Err("Native launcher identity verification failed".into())}}else{command.spawn().map_err(|e|e.to_string())?;}Ok(())}
fn main(){if let Err(error)=run(){let text:Vec<u16>=format!("{error}\0").encode_utf16().collect();let title:Vec<u16>="Workbench launcher failed\0".encode_utf16().collect();#[link(name="user32")] extern "system"{fn MessageBoxW(w:isize,t:*const u16,c:*const u16,k:u32)->i32;}unsafe{MessageBoxW(0,text.as_ptr(),title.as_ptr(),0x10);}std::process::exit(1);}}
