#![windows_subsystem = "windows"]
#[path="../active.rs"] mod active;
fn main(){let exe=std::env::current_exe().unwrap();let root=exe.parent().unwrap();if let Err(error)=active::launch(root,&std::env::args().skip(1).collect::<Vec<_>>(),None){let text:Vec<u16>=format!("{error}\0").encode_utf16().collect();let title:Vec<u16>="Workbench launch failed\0".encode_utf16().collect();#[link(name="user32")] extern "system"{fn MessageBoxW(w:isize,t:*const u16,c:*const u16,k:u32)->i32;}unsafe{MessageBoxW(0,text.as_ptr(),title.as_ptr(),0x10);}std::process::exit(1);}}
