use std::process::Command;
use std::os::windows::process::CommandExt;
pub fn destination(id:&str)->Result<&'static str,&'static str>{match id{
 "github-sponsors"=>Ok("https://github.com/sponsors/amgedi"),
 "ko-fi"=>Ok("https://ko-fi.com/openfhs"),
 _=>Err("Unknown support destination")
}}
pub fn open(id:&str)->Result<(),String>{let url=destination(id).map_err(str::to_owned)?;Command::new("explorer.exe").arg(url).creation_flags(0x08000000).spawn().map(|_|()).map_err(|_|"The support page could not be opened.".into())}
#[cfg(test)]mod tests{use super::*;#[test]fn verified_destinations_only(){assert_eq!(destination("github-sponsors").unwrap(),"https://github.com/sponsors/amgedi");assert_eq!(destination("ko-fi").unwrap(),"https://ko-fi.com/openfhs");}#[test]fn arbitrary_destinations_rejected(){for id in ["https://example.com","ko-fi?url=other","","../github-sponsors"]{assert!(destination(id).is_err());}}}
