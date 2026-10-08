#![cfg_attr(not(debug_assertions), windows_subsystem = "windows")]
#[path="../../../support-links.rs"] mod support_links;
mod active;
mod updates;
use std::{fs,io::{BufRead,BufReader,Write},path::{Path,PathBuf},process::{Command,Stdio},sync::{Mutex,atomic::{AtomicBool,Ordering}}};
use std::os::windows::process::CommandExt;
use std::os::windows::io::AsRawHandle;
use windows_sys::Win32::{Foundation::CloseHandle,System::JobObjects::*};
use serde_json::{json,Value};
use tauri::{Manager,Emitter};
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

#[tauri::command]
fn launcher_window_theme(window:tauri::WebviewWindow,name:String)->Result<(),String>{caption_theme(&window,&name)}
fn taskbar_identity(window:&tauri::WebviewWindow)->Result<(),Box<dyn std::error::Error>>{
 use windows::{core::GUID,Win32::{Foundation::{HWND,PROPERTYKEY},UI::Shell::PropertiesSystem::{SHGetPropertyStoreForWindow,IPropertyStore},System::Com::StructuredStorage::PROPVARIANT}};
 let executable=root().join("Launch Workbench.exe");
 let path=executable.to_str().ok_or("Launcher path is not valid Unicode")?;
 let properties=[(2,format!("\"{path}\"")),(3,format!("{path},0")),(4,"Biodiversity · Launch Workbench".into()),(5,"org.biodiversity.rescue.launcher".into())];
 unsafe{
  let store:IPropertyStore=SHGetPropertyStoreForWindow(HWND(window.hwnd()?.0))?;
  for (pid,value) in &properties{
   let key=PROPERTYKEY{fmtid:GUID::from_u128(0x9f4c2855_9f79_4b39_a8d0_e1d42de1d5f3),pid:*pid};
   store.SetValue(&key,&PROPVARIANT::from(value.as_str()))?;
  }
  store.Commit()?;
  for (pid,value) in &properties{
   let key=PROPERTYKEY{fmtid:GUID::from_u128(0x9f4c2855_9f79_4b39_a8d0_e1d42de1d5f3),pid:*pid};
   if store.GetValue(&key)?.to_string()!=*value{return Err("Windows taskbar identity did not persist".into())}
  }
 }
 Ok(())
}

struct State{root:PathBuf,busy:AtomicBool,cancelled:AtomicBool,logs:Mutex<Vec<String>>,job:Mutex<Option<usize>>}
fn root()->PathBuf{let exe=std::env::current_exe().expect("Executable location unavailable");for parent in exe.ancestors().skip(1){if parent.join("versions/CURRENT.json").is_file()||(parent.join("build-identity.json").is_file()&&parent.join("Biodiversity Workbench.exe").is_file()){return parent.into()}}panic!("Canonical active-version state not found")}
fn hidden(program:&Path)->Command{let mut c=Command::new(program);c.creation_flags(0x08000000);c}
fn python(root:&Path)->Option<PathBuf>{let local=std::env::var("LOCALAPPDATA").unwrap_or_default();[root.join(".venv/Scripts/python.exe"),PathBuf::from(local).join("Python/pythoncore-3.14-64/python.exe")].into_iter().find(|p|p.is_file())}
fn verified_exe(root:&Path,previous:bool)->Result<(PathBuf,Value),String>{active::selected(root,previous)}
fn visual_preferences()->Value{let local=std::env::var("LOCALAPPDATA").unwrap_or_default();let data=std::env::var("WORKBENCH_DESKTOP_DATA").map(PathBuf::from).unwrap_or_else(|_|PathBuf::from(local).join("Biodiversity Data Rescue Workbench/projects-data"));let pending=data.join("launcher-appearance.json");if pending.is_file(){if let Ok(bytes)=fs::read(&pending){if bytes.len()<=4096{if let Ok(value)=serde_json::from_slice::<Value>(&bytes){return value}}}}let path=data.join("client-state.json");let read=||->Option<Value>{if fs::metadata(&path).ok()?.len()>1_048_576{return None}let client:Value=serde_json::from_slice(&fs::read(path).ok()?).ok()?;let preferences:Value=serde_json::from_str(client["biorescue-preferences"].as_str()?).ok()?;Some(json!({"theme":preferences["theme"],"surface":preferences["surface"],"motion":preferences["motion"],"reducedTransparency":preferences["reducedTransparency"]}))};read().unwrap_or(json!({"theme":"forest","surface":"frosted","motion":"full"}))}
fn recent_projects()->Value{
 let local=std::env::var("LOCALAPPDATA").unwrap_or_default();let data=std::env::var("WORKBENCH_DESKTOP_DATA").map(PathBuf::from).unwrap_or_else(|_|PathBuf::from(local).join("Biodiversity Data Rescue Workbench/projects-data"));
 let Ok(entries)=fs::read_dir(data.join("projects")) else{return json!([])};
 let mut files:Vec<_>=entries.take(1000).filter_map(Result::ok).filter(|e|e.file_type().is_ok_and(|t|t.is_file())&&e.path().extension().is_some_and(|x|x=="json")&&!e.file_name().to_string_lossy().ends_with(".previous.json")).collect();
 files.sort_by_key(|e|std::cmp::Reverse(e.metadata().ok().and_then(|m|m.modified().ok())));
 let mut result=vec![];
 for e in files.into_iter().take(8){if e.metadata().is_ok_and(|m|m.len()<=16*1024*1024){if let Ok(bytes)=fs::read(e.path()){if let Ok(p)=serde_json::from_slice::<Value>(&bytes){if p["id"].is_string()&&p["metadata"]["title"]["value"].is_string(){result.push(json!({"id":p["id"],"title":p["metadata"]["title"]["value"],"updatedAt":p["updatedAt"]}));}}}}}
 json!(result)
}
#[tauri::command] async fn launcher_status(app:tauri::AppHandle)->Result<Value,String>{
 let state=app.state::<State>();let verified=verified_exe(&state.root,false);let previous_verified=verified_exe(&state.root,true).is_ok();let mut tools=Value::Null;let mut expected=Value::Null;
 if let Some(py)=python(&state.root){if let Ok(output)=hidden(&py).args(["-X","utf8","scripts/build/workbench.py","status"]).current_dir(&state.root).output(){if let Ok(value)=serde_json::from_slice::<Value>(&output.stdout){tools=value["prerequisites"].clone();expected=value["source"]["sourceFingerprint"].clone();}}}
 match verified{Ok((exe,manifest))=>Ok(json!({"version":manifest["version"],"buildId":manifest["buildId"],"current":true,"verified":true,"tools":tools,"sourceMatchesActive":expected==manifest["sourceFingerprint"],"previousVerified":previous_verified,"source":state.root.join("package.json").is_file(),"path":exe,"preferences":visual_preferences(),"projects":recent_projects()})),Err(error)=>Err(error)}
}
#[tauri::command] fn launcher_activate(app:tauri::AppHandle,build_id:String)->Result<(),String>{
 let state=app.state::<State>();if state.busy.load(Ordering::SeqCst){return Err("Wait for the owned task to finish".into())}
 let py=python(&state.root).ok_or("Python is required to activate a local history build")?;
 let output=hidden(&py).args(["-X","utf8","scripts/launcher/versions.py","activate",&build_id]).current_dir(&state.root).output().map_err(|e|e.to_string())?;
 if !output.status.success(){return Err(String::from_utf8_lossy(&output.stdout).to_string()+&String::from_utf8_lossy(&output.stderr))}Ok(())
}
#[tauri::command] fn launcher_versions(app:tauri::AppHandle)->Result<Value,String>{active::read(&app.state::<State>().root)}
#[tauri::command] async fn launcher_updates()->Value{updates::check().await}
#[tauri::command] fn launcher_release_page()->Result<(),String>{Command::new("explorer.exe").arg("https://github.com/amgedi/Biodiversity-Data-Rescue-Workbench/releases").creation_flags(0x08000000).spawn().map(|_|()).map_err(|_|"The official release page could not be opened.".into())}
fn log(app:&tauri::AppHandle,line:String){let state=app.state::<State>();let mut logs=state.logs.lock().unwrap();if logs.len()>=2000{logs.remove(0);}logs.push(line.clone());let _=app.emit("launcher-progress",line);}
#[tauri::command] async fn launcher_open(app:tauri::AppHandle,previous:bool,project_id:Option<String>,library:Option<bool>,expected_build_id:Option<String>)->Result<(),String>{
 let state=app.state::<State>();if state.busy.load(Ordering::SeqCst){return Err("A build is already running".into())}
 if previous{return Err("Restore a history build in Updates before launching it".into())}
 let mut args=vec![];if let Some(id)=project_id{if id.is_empty()||id.len()>120||!id.chars().all(|c|c.is_ascii_alphanumeric()||c=='-'||c=='_'){return Err("Invalid project identity".into())}args.extend(["--project".into(),id]);}else if library==Some(true){args.push("--library".into())}
 let root=state.root.clone();tauri::async_runtime::spawn_blocking(move||active::launch(&root,&args,expected_build_id.as_deref())).await.map_err(|e|e.to_string())??;Ok(())
}
#[tauri::command] async fn launcher_build(app:tauri::AppHandle)->Result<(),String>{run_task(app,"build".into()).await}
#[tauri::command] async fn launcher_task(app:tauri::AppHandle,action:String)->Result<(),String>{if !["regression","web","development","package"].contains(&action.as_str()){return Err("Unsupported local task".into())}run_task(app,action).await}
async fn run_task(app:tauri::AppHandle,action:String)->Result<(),String>{let state=app.state::<State>();if state.busy.swap(true,Ordering::SeqCst){return Err("A build is already running".into())}state.cancelled.store(false,Ordering::SeqCst);let root=state.root.clone();let worker=app.clone();let result=tauri::async_runtime::spawn_blocking(move||{let app=worker;
 let py=python(&root).ok_or("Python is needed only for source builds. Your previous verified package remains safe.")?;
 if !root.join("package.json").is_file(){return Err("Development actions require the source checkout. No tools are installed by this launcher.".into())}
 let (script,mode)=if action=="package"{("scripts/release/ui_v7_candidate.py",None)}else{("scripts/build/workbench.py",Some(action.as_str()))};
 let mut command=hidden(&py);command.args(["-X","utf8",script]);if let Some(mode)=mode{command.arg(mode);}
 let mut child=command.current_dir(&root).env("WORKBENCH_LAUNCHER_GATE","1").stdin(Stdio::piped()).stdout(Stdio::piped()).stderr(Stdio::piped()).spawn().map_err(|e|e.to_string())?;
 unsafe{let job=CreateJobObjectW(std::ptr::null(),std::ptr::null());if job.is_null(){let _=child.kill();return Err("Could not create owned build job".into())}let mut limits:JOBOBJECT_EXTENDED_LIMIT_INFORMATION=std::mem::zeroed();limits.BasicLimitInformation.LimitFlags=JOB_OBJECT_LIMIT_KILL_ON_JOB_CLOSE;if SetInformationJobObject(job,JobObjectExtendedLimitInformation,&limits as *const _ as *const _,std::mem::size_of_val(&limits) as u32)==0||AssignProcessToJobObject(job,child.as_raw_handle())==0{CloseHandle(job);let _=child.kill();return Err("Could not establish safe build cancellation".into())}*app.state::<State>().job.lock().unwrap()=Some(job as usize);}
 if app.state::<State>().cancelled.load(Ordering::SeqCst){let _=launcher_cancel(app.clone());}
 child.stdin.take().unwrap().write_all(b"START\n").map_err(|e|e.to_string())?;
 let stderr=child.stderr.take().unwrap();let copy=app.clone();let reader=std::thread::spawn(move||for line in BufReader::new(stderr).lines().map_while(Result::ok){log(&copy,line)});
 for line in BufReader::new(child.stdout.take().unwrap()).lines().map_while(Result::ok){log(&app,line)}
 let status=child.wait().map_err(|e|e.to_string())?;let _=reader.join();if let Some(job)=app.state::<State>().job.lock().unwrap().take(){unsafe{CloseHandle(job as _);}}if status.success(){Ok(())}else{Err("Build failed. Your last verified Workbench is still safe. Open details for the exact error.".into())}
 }).await.map_err(|e|e.to_string());if let Some(job)=state.job.lock().unwrap().take(){unsafe{CloseHandle(job as _);}}state.busy.store(false,Ordering::SeqCst);result?}
#[tauri::command] fn launcher_preferences(preferences:Value)->Result<(),String>{
 let theme=preferences["theme"].as_str().ok_or("Missing theme")?;
 let surface=preferences["surface"].as_str().ok_or("Missing material")?;
 let motion=preferences["motion"].as_str().ok_or("Missing motion")?;
 if !["forest","dark","midnight","ocean","aurora","museum","field-notes","slate","paper","light","mono-dark","high-contrast"].contains(&theme)||!["solid","frosted","glass","minimal"].contains(&surface)||!["full","off","subtle","reduced","system"].contains(&motion){return Err("Invalid visual preference".into())}
 let local=std::env::var("LOCALAPPDATA").unwrap_or_default();
 let data=std::env::var("WORKBENCH_DESKTOP_DATA").map(PathBuf::from).unwrap_or_else(|_|PathBuf::from(local).join("Biodiversity Data Rescue Workbench/projects-data"));
 fs::create_dir_all(&data).map_err(|e|e.to_string())?;
 let target=data.join("launcher-appearance.json");let temp=data.join("launcher-appearance.pending");
 let bytes=serde_json::to_vec(&json!({"theme":theme,"surface":surface,"motion":motion})).map_err(|e|e.to_string())?;
 let mut file=fs::File::create(&temp).map_err(|e|e.to_string())?;file.write_all(&bytes).map_err(|e|e.to_string())?;file.sync_all().map_err(|e|e.to_string())?;drop(file);
 fs::rename(&temp,&target).map_err(|e|e.to_string())?;Ok(())
}
#[tauri::command] fn launcher_logs(app:tauri::AppHandle)->Vec<String>{app.state::<State>().logs.lock().unwrap().clone()}
#[tauri::command] fn launcher_cancel(app:tauri::AppHandle)->Result<(),String>{app.state::<State>().cancelled.store(true,Ordering::SeqCst);if let Some(job)=app.state::<State>().job.lock().unwrap().take(){unsafe{TerminateJobObject(job as _,1);CloseHandle(job as _);}}Ok(())}
#[tauri::command] fn support_open(destination:String)->Result<(),String>{support_links::open(&destination)}
fn main(){if std::env::var_os("WORKBENCH_VERIFY_CURRENT").is_some(){match active::launch(&root(),&[],None){Ok(_)=>return,Err(e)=>{eprintln!("{e}");std::process::exit(1);}}}tauri::Builder::default().plugin(tauri_plugin_single_instance::init(|app,_,_|{if let Some(w)=app.get_webview_window("launcher"){let _=w.show();let _=w.set_focus();}})).setup(|app|{if let Some(window)=app.get_webview_window("launcher"){taskbar_identity(&window)?;caption_theme(&window,visual_preferences()["theme"].as_str().unwrap_or("forest"))?;}let handle=app.handle().clone();let pointer=root().join("versions/CURRENT.json");std::thread::spawn(move||{let mut previous=fs::metadata(&pointer).ok().and_then(|m|m.modified().ok());loop{std::thread::sleep(std::time::Duration::from_millis(500));let current=fs::metadata(&pointer).ok().and_then(|m|m.modified().ok());if current!=previous{previous=current;let _=handle.emit("launcher-current-changed",());}}});Ok(())}).manage(State{root:root(),busy:AtomicBool::new(false),cancelled:AtomicBool::new(false),logs:Mutex::new(vec![]),job:Mutex::new(None)}).invoke_handler(tauri::generate_handler![support_open,launcher_window_theme,launcher_status,launcher_open,launcher_build,launcher_task,launcher_logs,launcher_cancel,launcher_preferences,launcher_activate,launcher_versions,launcher_updates,launcher_release_page]).on_window_event(|window,event|{if let tauri::WindowEvent::CloseRequested{api,..}=event{if window.app_handle().state::<State>().busy.load(Ordering::SeqCst){api.prevent_close();let _=window.emit("launcher-progress","STAGE Build is running. Cancel the owned build before closing.");}}}).run(tauri::generate_context!()).expect("Launcher runtime failed");}
