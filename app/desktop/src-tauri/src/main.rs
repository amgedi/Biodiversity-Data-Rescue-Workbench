#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
#[path="../../../support-links.rs"] mod support_links;
use std::{fs, io::{BufRead, BufReader, Write, Read}, path::{Path, PathBuf}, process::{Child, Command, Stdio}, sync::{Mutex, atomic::{AtomicUsize, Ordering}}, time::Duration};
use tauri::{Manager, Emitter, WebviewUrl, WebviewWindowBuilder};
use tauri_plugin_dialog::DialogExt;
use serde::{Serialize, Deserialize};
use base64::{Engine as _, engine::general_purpose::STANDARD};
#[cfg(windows)] use std::os::windows::process::CommandExt;

#[derive(Default)] struct Engine {child:Option<Child>, port:u16, token:String, failed:bool, message:String, starting:bool}
struct State {engine:Mutex<Engine>, counter:AtomicUsize, data:PathBuf, logs:PathBuf, client:Mutex<()>, initial_route:Mutex<String>}
#[cfg(windows)]
fn windows_transparency() -> Option<bool> {
 #[link(name="advapi32")]
 extern "system" {fn RegGetValueW(key:*mut std::ffi::c_void,subkey:*const u16,value:*const u16,flags:u32,kind:*mut u32,data:*mut std::ffi::c_void,size:*mut u32)->i32;}
 let path:Vec<u16>="Software\\Microsoft\\Windows\\CurrentVersion\\Themes\\Personalize".encode_utf16().chain([0]).collect();
 let name:Vec<u16>="EnableTransparency".encode_utf16().chain([0]).collect();
 let mut value=0u32;let mut size=4u32;
 // Read only the current user's DWORD. Missing/unreadable settings stay unknown.
 let result=unsafe{RegGetValueW((0x80000001u32 as i32 as isize) as *mut _,path.as_ptr(),name.as_ptr(),0x10,std::ptr::null_mut(),&mut value as *mut _ as *mut _,&mut size)};
 if result==0&&size==4&&value<=1{Some(value==0)}else{None}
}
#[tauri::command]
fn native_accessibility() -> serde_json::Value {
 #[cfg(windows)] let reduced=windows_transparency();
 #[cfg(not(windows))] let reduced:Option<bool>=None;
 serde_json::json!({"reducedTransparency":reduced})
}
fn caption_theme(window:&tauri::WebviewWindow,name:&str)->Result<(),String>{
 if name=="system"{
  window.set_theme(None).map_err(|e|e.to_string())?;
  #[cfg(windows)]{
   #[link(name="dwmapi")] extern "system"{fn DwmSetWindowAttribute(hwnd:*mut std::ffi::c_void,attribute:u32,value:*const std::ffi::c_void,size:u32)->i32;}
   let hwnd=window.hwnd().map_err(|e|e.to_string())?.0;let default_color=0xffffffffu32;
   unsafe{DwmSetWindowAttribute(hwnd,35,&default_color as *const _ as *const _,4);DwmSetWindowAttribute(hwnd,36,&default_color as *const _ as *const _,4);}
  }
  return Ok(())
 }
 let (dark,bg,fg)=match name{
  "forest"=>(true,0x191c09u32,0xedf4e8u32),
  "dark"=>(true,0x161312u32,0xf4f0f0u32),
  "midnight"=>(true,0x28120bu32,0xfff0edu32),
  "ocean"=>(true,0x291d06u32,0xf6f6e3u32),
  "aurora"=>(true,0x2b1417u32,0xffedf3u32),
  "museum"=>(true,0x171b23u32,0xe1eef6u32),
  "field-notes"=>(false,0xe7f0eeu32,0x2c3524u32),
  "slate"=>(true,0x30251du32,0xfbf5efu32),
  "paper"=>(false,0xe4eef3u32,0x212b33u32),
  "light"=>(false,0xf7f1eau32,0x4b3522u32),
  "mono-dark"=>(true,0x111111u32,0xf5f5f5u32),
  "high-contrast"=>(true,0x000000u32,0xffffffu32),
  _=>return Err("Unknown window theme".into())
 };
 window.set_theme(Some(if dark{tauri::Theme::Dark}else{tauri::Theme::Light})).map_err(|e|e.to_string())?;
 #[cfg(windows)] {
  #[link(name="dwmapi")] extern "system"{fn DwmSetWindowAttribute(hwnd:*mut std::ffi::c_void,attribute:u32,value:*const std::ffi::c_void,size:u32)->i32;}
  let hwnd=window.hwnd().map_err(|e|e.to_string())?.0;
  // Windows 11 caption colors; older Windows keeps the themed native frame.
  unsafe{DwmSetWindowAttribute(hwnd,35,&bg as *const _ as *const _,4);DwmSetWindowAttribute(hwnd,36,&fg as *const _ as *const _,4);}
 }
 Ok(())
}
#[derive(Serialize)] struct Status {phase:String,message:String,ready:bool,failed:bool}
#[derive(Deserialize)] struct Ready {port:u16,token:String}
#[derive(Clone, Serialize)] struct Intake {name:String,base64:String}

fn client_key(key:&str)->bool {key.len()<=160 && (matches!(key,"biorescue-grid-views"|"biorescue-preferences"|"biorescue-workspace-profile"|"biorescue-mode"|"biorescue-language"|"biorescue-local-templates"|"biorescue-theme"|"biorescue-help-read-v7"|"biorescue-support"|"biorescue-search-recent-v7")||key.starts_with("biorescue-product-tour-v"))}
fn identifier(value:&str)->bool {!value.is_empty()&&value.len()<=120&&value.bytes().all(|c|c.is_ascii_alphanumeric()||c==b'-'||c==b'_')}
fn read_json(path:&Path,limit:u64)->Result<serde_json::Value,String>{let file=fs::File::open(path).map_err(|_|"Local client storage could not be read")?;let mut bytes=vec![];file.take(limit+1).read_to_end(&mut bytes).map_err(|_|"Local client storage could not be read")?;if bytes.len() as u64>limit{return Err("Local client storage exceeds its limit".into())}serde_json::from_slice(&bytes).map_err(|_|"Local client configuration is invalid".into())}
fn publish_json(path:&Path,value:&serde_json::Value)->Result<(),String>{let bytes=serde_json::to_vec(value).map_err(|_|"Client state could not be encoded")?;let parent=path.parent().ok_or("Invalid client storage location")?;fs::create_dir_all(parent).map_err(|_|"Local client storage is unavailable")?;let temp=path.with_extension("pending");let mut file=fs::OpenOptions::new().write(true).create_new(true).open(&temp).map_err(|_|"A client write is already pending; keep this window open")?;if file.write_all(&bytes).and_then(|_|file.sync_all()).is_err(){let _=fs::remove_file(&temp);return Err("Client state could not be saved".into())}drop(file);if fs::rename(&temp,path).is_err(){let _=fs::remove_file(&temp);return Err("Client state could not be published".into())}Ok(())}
#[tauri::command] async fn native_client_state(app:tauri::AppHandle,action:String,key:Option<String>,value:Option<String>)->Result<serde_json::Value,String>{tauri::async_runtime::spawn_blocking(move||{
 let state=app.state::<State>();let _lock=state.client.lock().unwrap();let path=state.data.join("client-state.json");
 let mut data=if path.exists(){read_json(&path,1024*1024)?}else{serde_json::json!({})};let map=data.as_object_mut().ok_or("Local client configuration is invalid")?;
 if action=="load"{
  let pending=state.data.join("launcher-appearance.json");
  if pending.exists(){
   let visual=read_json(&pending,4096)?;
   let mut preferences=map.get("biorescue-preferences").and_then(|v|v.as_str()).and_then(|s|serde_json::from_str::<serde_json::Value>(s).ok()).unwrap_or(serde_json::json!({}));
   let values=preferences.as_object_mut().ok_or("Invalid visual preferences")?;
   for (key,allowed) in [("theme",vec!["forest","dark","midnight","ocean","aurora","museum","field-notes","slate","paper","light","mono-dark","high-contrast"]),("surface",vec!["solid","frosted","glass","minimal"]),("motion",vec!["full","off","subtle","reduced","system"])]{
    let value=visual[key].as_str().ok_or("Missing visual preference")?;if !allowed.contains(&value){return Err("Invalid visual preference".into())}values.insert(key.into(),serde_json::Value::String(value.into()));
   }
   map.insert("biorescue-preferences".into(),serde_json::Value::String(serde_json::to_string(&preferences).map_err(|_|"Invalid visual preferences")?));
   publish_json(&path,&data)?;fs::remove_file(&pending).map_err(|_|"Visual preferences saved; pending selector could not be retired")?;
  }
  data.as_object_mut().unwrap().retain(|key,value|client_key(key)&&value.as_str().is_some_and(|text|text.len()<=65536));return Ok(data)
 }
 if action!="save"{return Err("Invalid client-state action".into())}let key=key.ok_or("Missing preference key")?;if !client_key(&key){return Err("Unsupported preference key".into())}if let Some(value)=value{if value.len()>65536{return Err("Preference size limit exceeded".into())}map.insert(key,serde_json::Value::String(value));}else{map.remove(&key);}if serde_json::to_vec(&data).map_err(|_|"Invalid preferences")?.len()>1024*1024{return Err("Client preference limit exceeded".into())}publish_json(&path,&data)?;Ok(serde_json::json!(true))
 }).await.map_err(|e|e.to_string())?}
#[tauri::command] async fn native_window_recovery(app:tauri::AppHandle,action:String,project_id:String,id:Option<String>,copy:Option<String>)->Result<serde_json::Value,String>{tauri::async_runtime::spawn_blocking(move||{
 if !identifier(&project_id){return Err("Invalid recovery project identifier".into())}let state=app.state::<State>();let _lock=state.client.lock().unwrap();let directory=state.data.join("window-recovery");fs::create_dir_all(&directory).map_err(|_|"Recovery storage is unavailable")?;
 if action=="list"{let mut entries=vec![];let mut visited=0;for entry in fs::read_dir(&directory).map_err(|_|"Recovery storage is unavailable")?{visited+=1;if visited>1000{return Err("Recovery archive entry limit exceeded".into())}let entry=entry.map_err(|_|"Recovery entry is unavailable")?;if !entry.file_type().map_err(|_|"Recovery entry is unavailable")?.is_file()||!entry.file_name().to_string_lossy().ends_with(".meta.json"){continue}let value=read_json(&entry.path(),4096)?;if value["projectId"].as_str()==Some(&project_id){entries.push(value);}}return Ok(serde_json::Value::Array(entries))}
 let id=id.ok_or("Missing recovery identifier")?;if !identifier(&id){return Err("Invalid recovery identifier".into())}let path=directory.join(format!("{id}.json"));let metadata=directory.join(format!("{id}.meta.json"));
 if action=="get"{let value=read_json(&path,160*1024*1024)?;if value["projectId"].as_str()!=Some(&project_id){return Err("Recovery project mismatch".into())}return Ok(value)}
 if action!="retain"{return Err("Invalid recovery action".into())}let copy=copy.ok_or("Missing recovery copy")?;if copy.len()>160*1024*1024{return Err("Recovery copy exceeds the native limit; keep this window open".into())}let value:serde_json::Value=serde_json::from_str(&copy).map_err(|_|"Recovery copy is invalid")?;if value["id"].as_str()!=Some(&id)||value["projectId"].as_str()!=Some(&project_id)||value["project"]["id"].as_str()!=Some(&project_id){return Err("Recovery copy identity mismatch".into())}if path.exists()||metadata.exists(){return Err("A recovery copy with this identity already exists".into())}
 publish_json(&path,&value)?;let descriptor=serde_json::json!({"id":id,"projectId":project_id,"at":value["at"],"session":value["session"],"baseRevision":value["project"]["revision"]});publish_json(&metadata,&descriptor)?;Ok(descriptor)
 }).await.map_err(|e|e.to_string())?}

#[tauri::command] fn native_window_action(window:tauri::WebviewWindow,action:String,title:Option<String>)->Result<(),String>{if !window.label().starts_with("workbench-"){return Err("Not a project window".into())}match action.as_str(){"theme"=>caption_theme(&window,&title.ok_or("Missing theme")?),"title"=>{let title=title.ok_or("Missing title")?;if title.chars().count()>240||title.chars().any(char::is_control){return Err("Invalid window title".into())}window.set_title(&title).map_err(|e|e.to_string())},"close"=>window.close().map_err(|e|e.to_string()),"minimize"=>window.minimize().map_err(|e|e.to_string()),"maximize"=>{if window.is_maximized().map_err(|e|e.to_string())?{window.unmaximize().map_err(|e|e.to_string())}else{window.maximize().map_err(|e|e.to_string())}},"drag"=>window.start_dragging().map_err(|e|e.to_string()),_=>Err("Invalid window action".into())}}

fn engine_start(app:tauri::AppHandle){
 let state=app.state::<State>();
 {let mut engine=state.engine.lock().unwrap();if engine.starting || engine.port!=0{return}engine.starting=true;engine.failed=false;engine.message="Starting scientific engine…".into();}
 std::thread::spawn(move||{
  let result=(||->Result<(),String>{
   let state=app.state::<State>();fs::create_dir_all(&state.logs).map_err(|_|"Cannot create local diagnostics directory")?;
   let path=if cfg!(debug_assertions){PathBuf::from(env!("CARGO_MANIFEST_DIR")).join("engine/workbench-engine.exe")}else{app.path().resource_dir().map_err(|e|e.to_string())?.join("engine/workbench-engine.exe")};
   let error_file=fs::File::create(state.logs.join("engine.log")).map_err(|e|e.to_string())?;
   let mut command=Command::new(path);command.stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::from(error_file));
   #[cfg(windows)] command.creation_flags(0x08000000);
   let mut child=command.spawn().map_err(|_|"Scientific engine could not be launched. Reinstall the complete package.".to_string())?;
   let config=serde_json::json!({"dataDir":state.data,"isolated":std::env::var_os("WORKBENCH_DESKTOP_DATA").is_some()});
   writeln!(child.stdin.as_mut().ok_or("Engine input unavailable")?,"{}",config).map_err(|e|e.to_string())?;
   let output=child.stdout.take().ok_or("Engine output unavailable")?;
   let (sender,receiver)=std::sync::mpsc::channel();std::thread::spawn(move||{let mut line=String::new();let result=BufReader::new(output).read_line(&mut line).map(|_|line);let _=sender.send(result);});
   let ready=match receiver.recv_timeout(Duration::from_secs(40)){Ok(Ok(line))=>serde_json::from_str::<Ready>(&line).map_err(|_|"Scientific engine did not report readiness.".to_string()),_=>Err("Scientific engine startup timed out.".into())};
   let ready=match ready{Ok(value)=>value,Err(error)=>{let _=child.kill();let _=child.wait();return Err(error)}};
   if ready.port==0 || ready.token.len()<40{let _=child.kill();return Err("Invalid engine session.".into())}
   let mut engine=state.engine.lock().unwrap();engine.child=Some(child);engine.port=ready.port;engine.token=ready.token;engine.starting=false;engine.message="Loading project library…".into();Ok(())
  })();
  if let Err(error)=result{let state=app.state::<State>();let mut engine=state.engine.lock().unwrap();engine.starting=false;engine.failed=true;engine.message=error;}
 });
}
fn startup(app:&tauri::AppHandle)->Result<(),String>{let id=app.state::<State>().counter.fetch_add(1,Ordering::Relaxed);WebviewWindowBuilder::new(app,format!("startup-{id}"),WebviewUrl::App("index.html".into())).title("Biodiversity Data Rescue Workbench").inner_size(900.,620.).build().map_err(|e|e.to_string())?;Ok(())}
#[tauri::command] fn engine_status(app:tauri::AppHandle)->Status{let state=app.state::<State>();let mut engine=state.engine.lock().unwrap();if let Some(child)=engine.child.as_mut(){if matches!(child.try_wait(),Ok(Some(_))){engine.port=0;engine.failed=true;engine.message="Scientific engine stopped. Your saved projects remain on disk.".into();}}
 Status{phase:if engine.failed{"Workbench could not start"}else if engine.port>0{"Ready"}else{"Starting Workbench…"}.into(),message:engine.message.clone(),ready:engine.port>0,failed:engine.failed}}
#[tauri::command] fn retry_engine(app:tauri::AppHandle){engine_start(app);}
#[tauri::command] fn close_startup(window:tauri::WebviewWindow){if window.label().starts_with("startup-"){let _=window.close();}}
fn launch_route(args:&[String])->String {if let Some(index)=args.iter().position(|v|v=="--project"){if let Some(id)=args.get(index+1){if identifier(id){return format!("view=Overview&project={id}")}}}if args.iter().any(|v|v=="--library"){"view=Projects".into()}else{String::new()}}
#[tauri::command] fn initial_route(app:tauri::AppHandle)->String {std::mem::take(&mut *app.state::<State>().initial_route.lock().unwrap())}
#[tauri::command] async fn open_workbench(app:tauri::AppHandle,route:String)->Result<(),String>{open_window(app,route)}
fn open_window(app:tauri::AppHandle,route:String)->Result<(),String>{
 let state=app.state::<State>();let engine=state.engine.lock().unwrap();if engine.port==0{drop(engine);startup(&app)?;return Ok(())}
 if route.len()>1000 || route.contains(['\r','\n']){return Err("Invalid window route".into())}
 let url=format!("http://127.0.0.1:{}/desktop/{}",engine.port,engine.token);let origin=format!("http://127.0.0.1:{}",engine.port);
 let script=format!("window.__WORKBENCH_DESKTOP__=true;window.__WORKBENCH_WINDOW_ID__={};if(location.pathname==='/' && !location.hash && {})location.hash={};",state.counter.load(Ordering::Relaxed),!route.is_empty(),serde_json::to_string(&route).unwrap());
 let id=state.counter.fetch_add(1,Ordering::Relaxed);drop(engine);
 let window=WebviewWindowBuilder::new(&app,format!("workbench-{id}"),WebviewUrl::External(url.parse().map_err(|_|"Invalid local address")?)).title("Biodiversity Data Rescue Workbench").inner_size(1400.,900.).decorations(true).min_inner_size(320.,480.).initialization_script(script).on_navigation(move|url|url.as_str().starts_with(&(origin.clone()+"/"))).build().map_err(|e|e.to_string())?;
 let emitter=window.clone();window.on_webview_event(move|event|{match event{tauri::WebviewEvent::DragDrop(tauri::DragDropEvent::Enter{..})=>{let _=emitter.emit("workbench-native-drag",true);},tauri::WebviewEvent::DragDrop(tauri::DragDropEvent::Leave|tauri::DragDropEvent::Drop{..})=>{let _=emitter.emit("workbench-native-drag",false);},_=>{}}if let tauri::WebviewEvent::DragDrop(tauri::DragDropEvent::Drop{paths,..})=event{let paths=paths.clone();let window=emitter.clone();std::thread::spawn(move||{let mut items=vec![];let mut total=0;let mut visited=0;let result=(||->Result<(),String>{for path in paths{collect(&path,path.parent().unwrap_or(&path),&mut items,&mut total,0,&mut visited)?;}Ok(())})();match result{Ok(())=>{let _=window.emit("workbench-native-drop",items);},Err(error)=>{let _=window.emit("workbench-native-drop-error",error);}}});}});Ok(())
}
#[tauri::command] fn open_logs(app:tauri::AppHandle)->Result<(),String>{let mut command=Command::new("explorer.exe");command.arg(&app.state::<State>().logs);command.spawn().map_err(|e|e.to_string())?;Ok(())}
fn collect(path:&Path,root:&Path,out:&mut Vec<Intake>,total:&mut u64,depth:usize,visited:&mut usize)->Result<(),String>{
 *visited+=1;if *visited>1000{return Err("Folder import is limited to 1,000 visited entries.".into())}
 let metadata=fs::symlink_metadata(path).map_err(|_|"Cannot read selected file")?;
 #[cfg(windows)] {use std::os::windows::fs::MetadataExt;if metadata.file_attributes() & 0x400 !=0{return Err("Directory links are not imported. Select the original folder.".into())}}
 if metadata.file_type().is_symlink() || depth>32{return Err("Links and deeply nested folders are not imported".into())}
 if metadata.is_dir(){for entry in fs::read_dir(path).map_err(|_|"Cannot read folder")?{collect(&entry.map_err(|_|"Cannot read folder entry")?.path(),root,out,total,depth+1,visited)?;}}else if metadata.is_file(){
  *total+=metadata.len();if out.len()>=100 || metadata.len()>20*1024*1024 || *total>50*1024*1024{return Err("Import is limited to 100 files, 20 MiB per file, and 50 MiB total. Use Large dataset mode for larger CSVs.".into())}
  let file=fs::File::open(path).map_err(|_|"Cannot read file")?;let mut bytes=vec![];file.take(20*1024*1024+1).read_to_end(&mut bytes).map_err(|_|"Cannot read file")?;if bytes.len() as u64!=metadata.len(){return Err("A selected file changed during reading. Select it again.".into())}
  out.push(Intake{name:path.strip_prefix(root).unwrap_or(path).to_string_lossy().replace('\\',"/"),base64:STANDARD.encode(bytes)});
 }Ok(())
}

#[tauri::command]
async fn native_clipboard_intake(window:tauri::WebviewWindow)->Result<Vec<Intake>,String>{
 if !window.label().starts_with("workbench-"){return Err("Not a project window".into())}
 let owner=window.hwnd().map_err(|e|e.to_string())?.0 as usize;
 tauri::async_runtime::spawn_blocking(move||{
  #[link(name="user32")] extern "system"{fn IsClipboardFormatAvailable(format:u32)->i32;fn OpenClipboard(owner:*mut std::ffi::c_void)->i32;fn GetClipboardData(format:u32)->*mut std::ffi::c_void;fn CloseClipboard()->i32;}
  #[link(name="shell32")] extern "system"{fn DragQueryFileW(drop:*mut std::ffi::c_void,index:u32,path:*mut u16,length:u32)->u32;}
  let mut paths=Vec::new();unsafe{
   if IsClipboardFormatAvailable(15)==0{return Ok(vec![])}
   if OpenClipboard(owner as *mut _)==0{return Err("Clipboard is busy. Copy the files again and retry.".into())}
   struct Clipboard;impl Drop for Clipboard{fn drop(&mut self){unsafe{CloseClipboard();}}}let _guard=Clipboard;
   let drop=GetClipboardData(15);if drop.is_null(){return Err("Copied file list is unavailable.".into())}
   let count=DragQueryFileW(drop,u32::MAX,std::ptr::null_mut(),0);if count>100{return Err("Select at most 100 copied files or folders.".into())}
   for i in 0..count{let length=DragQueryFileW(drop,i,std::ptr::null_mut(),0);if length==0||length>32767{return Err("Invalid copied file path.".into())}let mut name=vec![0u16;length as usize+1];if DragQueryFileW(drop,i,name.as_mut_ptr(),length+1)!=length{return Err("Copied file path changed.".into())}paths.push(PathBuf::from(String::from_utf16(&name[..length as usize]).map_err(|_|"Invalid copied file path")?));}
  }
  let mut out=vec![];let mut total=0;let mut visited=0;for path in paths{collect(&path,path.parent().unwrap_or(&path),&mut out,&mut total,0,&mut visited)?;}Ok(out)
 }).await.map_err(|e|e.to_string())?
}

#[tauri::command] async fn native_intake(app:tauri::AppHandle,folder:bool)->Result<Vec<Intake>,String>{tauri::async_runtime::spawn_blocking(move||{
 let paths=if folder{app.dialog().file().blocking_pick_folder().map(|path|vec![path])}else{app.dialog().file().blocking_pick_files()};let mut out=vec![];let mut total=0;let mut visited=0;
 for path in paths.unwrap_or_default(){let path=path.into_path().map_err(|_|"Unsupported file path")?;let root=path.parent().unwrap_or(&path);collect(&path,root,&mut out,&mut total,0,&mut visited)?;}Ok(out)
 }).await.map_err(|e|e.to_string())?}
fn stream_route(kind:&str,id:&str)->Result<String,String>{if id.is_empty()||id.len()>128||!id.chars().all(|c|c.is_ascii_alphanumeric()||c=='-'||c=='_'){return Err("Invalid local download identity".into())}match kind{"package"=>Ok(format!("/api/large-package?id={id}")),"original"=>Ok(format!("/api/large-original?id={id}")),"working"=>Ok(format!("/api/large-export?id={id}")),"history"=>Ok(format!("/api/large-history?id={id}")),"token"=>Ok(format!("/api/large-link-download?token={id}")),_=>Err("Unsupported local download kind".into())}}
#[tauri::command] async fn native_stream_save(app:tauri::AppHandle,name:String,kind:String,id:String)->Result<bool,String>{tauri::async_runtime::spawn_blocking(move||{
 let route=stream_route(&kind,&id)?;let state=app.state::<State>();let (port,token)={let engine=state.engine.lock().unwrap();if engine.port==0{return Err("Scientific engine is not ready".into())}(engine.port,engine.token.clone())};
 let filename=Path::new(&name).file_name().ok_or("Invalid filename")?.to_string_lossy().into_owned();let Some(path)=app.dialog().file().set_file_name(&filename).blocking_save_file() else{return Ok(false)};let path=path.into_path().map_err(|_|"Unsupported file path")?;
 let mut socket=std::net::TcpStream::connect_timeout(&std::net::SocketAddr::from(([127,0,0,1],port)),Duration::from_secs(15)).map_err(|e|e.to_string())?;socket.set_read_timeout(Some(Duration::from_secs(180))).map_err(|e|e.to_string())?;socket.set_write_timeout(Some(Duration::from_secs(15))).map_err(|e|e.to_string())?;write!(socket,"GET {route} HTTP/1.1\r\nHost: 127.0.0.1:{port}\r\nX-Workbench-Token: {token}\r\nConnection: close\r\n\r\n").map_err(|e|e.to_string())?;
 let mut reader=BufReader::new(socket);let mut line=String::new();reader.read_line(&mut line).map_err(|e|e.to_string())?;if !line.starts_with("HTTP/1.0 200 ")&&!line.starts_with("HTTP/1.1 200 "){return Err("Local export request failed; destination retained".into())}let mut header_bytes=line.len();let mut length=None;loop{line.clear();reader.read_line(&mut line).map_err(|e|e.to_string())?;header_bytes+=line.len();if header_bytes>65536||line.len()>8192{return Err("Local export headers exceed bounds".into())}if line=="\r\n"{break}if line.is_empty(){return Err("Incomplete local export headers".into())}let lower=line.to_ascii_lowercase();if let Some(value)=lower.strip_prefix("content-length:"){length=Some(value.trim().parse::<u64>().map_err(|_|"Invalid local export length")?);}if lower.starts_with("transfer-encoding:"){return Err("Unexpected local export transfer encoding".into())}}
 const LIMIT:u64=512*1024*1024;if length.is_some_and(|v|v>LIMIT){return Err("Native streamed export exceeds 512 MiB".into())}let temporary=path.with_extension(format!("workbench-pending-{}-{}",std::process::id(),state.counter.fetch_add(1,Ordering::Relaxed)));let mut created=false;let result=(||->Result<(),String>{let mut file=fs::OpenOptions::new().write(true).create_new(true).open(&temporary).map_err(|e|e.to_string())?;created=true;let copied=std::io::copy(&mut reader.take(LIMIT+1),&mut file).map_err(|e|e.to_string())?;if copied>LIMIT||length.is_some_and(|v|v!=copied){return Err("Local export length mismatch; destination retained".into())}file.sync_all().map_err(|e|e.to_string())?;drop(file);fs::rename(&temporary,&path).map_err(|e|e.to_string())?;Ok(())})();if result.is_err()&&created{let _=fs::remove_file(&temporary);}result.map(|_|true)
 }).await.map_err(|e|e.to_string())?}
#[tauri::command] async fn native_save(app:tauri::AppHandle,name:String,base64:String)->Result<bool,String>{tauri::async_runtime::spawn_blocking(move||{
 if base64.len()>220*1024*1024{return Err("Native save limit exceeded".into())}
 let name=Path::new(&name).file_name().ok_or("Invalid filename")?.to_string_lossy().into_owned();
 let Some(path)=app.dialog().file().set_file_name(&name).blocking_save_file() else{return Ok(false)};let path=path.into_path().map_err(|_|"Unsupported file path")?;let bytes=STANDARD.decode(base64).map_err(|_|"Invalid download bytes")?;
 // Create a new sibling before replacing the destination. Preserve existing destination on write failure.
 let temp=path.with_extension(format!("workbench-pending-{}",std::process::id()));let mut file=fs::OpenOptions::new().write(true).create_new(true).open(&temp).map_err(|_|"Cannot stage saved file")?;
 if let Err(error)=file.write_all(&bytes).and_then(|_|file.sync_all()){let _=fs::remove_file(temp);return Err(error.to_string())}drop(file);
 if let Err(error)=fs::rename(&temp,&path){let _=fs::remove_file(temp);return Err(error.to_string())}Ok(true)
 }).await.map_err(|e|e.to_string())?}
#[tauri::command] fn support_open(destination:String)->Result<(),String>{support_links::open(&destination)}
fn main(){
 // Check before the single-instance plugin forwards anything to an older shell.
 // The identical executable may forward project/library arguments; other builds stay isolated.
 #[cfg(windows)] {
  use std::os::windows::process::CommandExt;
  let this_exe=std::env::current_exe().expect("Executable location unavailable").to_string_lossy().replace("'","''");
  let script=format!("Get-Process -ErrorAction SilentlyContinue | Where-Object {{$_.Id -ne {} -and $_.ProcessName -in @('biodiversity-workbench','Biodiversity Workbench') -and $_.Path -ine '{}'}} | ForEach-Object {{$_.Id}}",std::process::id(),this_exe);
  if let Ok(output)=Command::new("powershell.exe").args(["-NoProfile","-NonInteractive","-Command",&script]).creation_flags(0x08000000).output(){
   if output.status.success() && !String::from_utf8_lossy(&output.stdout).trim().is_empty(){
    #[link(name="user32")] unsafe extern "system" {fn MessageBoxW(window:isize,text:*const u16,caption:*const u16,kind:u32)->i32;}
    let message:Vec<u16>="A Workbench desktop is already running. Save and close it before starting another build. This build will not attach to an older application. Use Open new window inside the running app for additional project windows.\0".encode_utf16().collect();
    let caption:Vec<u16>="Biodiversity · build identity protection\0".encode_utf16().collect();
    unsafe{MessageBoxW(0,message.as_ptr(),caption.as_ptr(),0x40);}
    return;
   }
  }
 }
 let data=std::env::var_os("WORKBENCH_DESKTOP_DATA").map(PathBuf::from).unwrap_or_else(||PathBuf::from(std::env::var_os("LOCALAPPDATA").expect("LOCALAPPDATA unavailable")).join("Biodiversity Data Rescue Workbench").join("projects-data"));
 let logs=data.parent().unwrap_or(&data).join("logs");
 let app=tauri::Builder::default().plugin(tauri_plugin_single_instance::init(|app,args,_|{let handle=app.clone();let route=launch_route(&args);tauri::async_runtime::spawn(async move{let _=open_workbench(handle,route).await;});})).plugin(tauri_plugin_dialog::init()).manage(State{engine:Mutex::new(Engine::default()),counter:AtomicUsize::new(1),data,logs,client:Mutex::new(()),initial_route:Mutex::new(launch_route(&std::env::args().collect::<Vec<_>>()))}).invoke_handler(tauri::generate_handler![support_open,initial_route,native_accessibility,engine_status,retry_engine,close_startup,open_workbench,open_logs,native_intake,native_clipboard_intake,native_stream_save,native_save,native_client_state,native_window_recovery,native_window_action]).setup(|app|{
  startup(app.handle()).map_err(std::io::Error::other)?;engine_start(app.handle().clone());Ok(())
 }).build(tauri::generate_context!()).expect("Could not initialize Workbench desktop");
 app.run(|app,event|{if matches!(event,tauri::RunEvent::Exit){let state=app.state::<State>();let mut engine=state.engine.lock().unwrap();if let Some(mut child)=engine.child.take(){drop(child.stdin.take());for _ in 0..100{if matches!(child.try_wait(),Ok(Some(_))){return}std::thread::sleep(Duration::from_millis(100));}let _=child.kill();let _=child.wait();}}});
}

#[cfg(test)] mod tests {
 use super::*;
 fn temp()->PathBuf {let path=std::env::temp_dir().join(format!("workbench-native-qa-{}-{}",std::process::id(),std::time::SystemTime::now().duration_since(std::time::UNIX_EPOCH).unwrap().as_nanos()));fs::create_dir(&path).unwrap();path}
 #[test] fn bounded_routes_accept_legacy_ids_and_reject_external_targets(){assert_eq!(launch_route(&["app".into(),"--project".into(),"legacy-p1".into()]),"view=Overview&project=legacy-p1");assert!(launch_route(&["--project".into(),"../outside".into()]).is_empty());assert_eq!(stream_route("package","project-123").unwrap(),"/api/large-package?id=project-123");for id in ["../escape","p&token=x","http://remote","p\r\nHeader: x"]{assert!(stream_route("original",id).is_err());}assert!(stream_route("arbitrary-file","project-123").is_err());}
 #[test] fn folder_entry_budget_rejects_empty_directory_flood(){let path=temp();for index in 0..1001{fs::create_dir(path.join(index.to_string())).unwrap();}let result=collect(&path,&path,&mut vec![],&mut 0,0,&mut 0);assert!(result.unwrap_err().contains("1,000"));fs::remove_dir_all(path).unwrap();}
 #[test] fn file_budget_rejects_whole_intake_after_one_hundred(){let path=temp();for index in 0..101{fs::write(path.join(index.to_string()),b"fictional").unwrap();}assert!(collect(&path,&path,&mut vec![],&mut 0,0,&mut 0).is_err());fs::remove_dir_all(path).unwrap();}
 #[test] fn oversized_file_rejected_before_reading(){let path=temp();let source=path.join("oversized.csv");fs::File::create(&source).unwrap().set_len(20*1024*1024+1).unwrap();let mut output=vec![];assert!(collect(&source,&path,&mut output,&mut 0,0,&mut 0).is_err());assert!(output.is_empty());fs::remove_dir_all(path).unwrap();}
 #[test] fn client_storage_rejects_paths_and_unrelated_keys(){assert!(identifier("project-123"));for value in ["../project","a/b","","a.b"]{assert!(!identifier(value));}assert!(client_key("biorescue-preferences"));assert!(!client_key("science-project"));assert!(!client_key(&"biorescue-product-tour-v".repeat(20)));}
 #[test] fn client_json_survives_replacement_and_rejects_corruption(){let directory=temp();let path=directory.join("client-state.json");publish_json(&path,&serde_json::json!({"theme":"light"})).unwrap();publish_json(&path,&serde_json::json!({"theme":"dark"})).unwrap();assert_eq!(read_json(&path,1024).unwrap()["theme"],"dark");assert!(read_json(&path,2).is_err());fs::write(&path,b"corrupt fictional configuration").unwrap();assert!(read_json(&path,1024).is_err());assert_eq!(fs::read(&path).unwrap(),b"corrupt fictional configuration");fs::remove_dir_all(directory).unwrap();}

}

