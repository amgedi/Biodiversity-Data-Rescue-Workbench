use serde_json::{json,Value};
use semver::Version;
const API:&str="https://api.github.com/repos/amgedi/Biodiversity-Data-Rescue-Workbench/releases/latest";
pub fn unavailable(reason:&str)->Value{json!({"status":"unable-to-check","message":format!("Unable to check for updates. {reason}")})}
pub fn compare(release:&Value,current:&str)->Result<Value,String>{
 if release["draft"]!=false||release["prerelease"]!=false{return Err("The feed did not identify a public stable release.".into())}
 let tag=release["tag_name"].as_str().ok_or("Release version is missing.")?;
 let latest=Version::parse(tag.strip_prefix('v').unwrap_or(tag)).map_err(|_|"Release version is invalid.")?;
 if !latest.pre.is_empty(){return Err("The stable feed contains a prerelease.".into())}
 let installed=Version::parse(current).map_err(|_|"Installed version is invalid.")?;
 let downloadable=release["assets"].as_array().is_some_and(|items|items.iter().any(|item|item["name"].as_str().is_some_and(|name|name.ends_with("-Portable.zip")||name.ends_with("-Setup.exe"))));
 if !downloadable{return Err("The release has no supported Windows download.".into())}
 if latest>installed{Ok(json!({"status":"update-available","version":latest.to_string(),"message":format!("Version {latest} is available. Open the official release page to download and verify it.")}))}
 else{Ok(json!({"status":"up-to-date","version":latest.to_string(),"message":format!("Up to date. Successfully checked the official release source ({latest}).")}))}
}
pub async fn check()->Value{
 let client=match reqwest::Client::builder().timeout(std::time::Duration::from_secs(15)).redirect(reqwest::redirect::Policy::none()).user_agent(concat!("Biodiversity-Data-Rescue-Workbench/",env!("CARGO_PKG_VERSION"))).build(){Ok(c)=>c,Err(_)=>return unavailable("A secure connection could not be initialized.")};
 let mut response=match client.get(API).header("Accept","application/vnd.github+json").send().await{Ok(r)=>r,Err(_)=>return unavailable("The network or official release source is unavailable.")};
 if !response.status().is_success(){return unavailable("The official release source is unavailable or has no public release yet.")}
 const LIMIT:usize=512*1024;let mut bytes=Vec::new();
 loop{match response.chunk().await{Ok(Some(chunk))=>{if bytes.len()+chunk.len()>LIMIT{return unavailable("Release metadata exceeded its size limit.")}bytes.extend_from_slice(&chunk)},Ok(None)=>break,Err(_)=>return unavailable("Release metadata could not be read.")}}
 let release:Value=match serde_json::from_slice(&bytes){Ok(value)=>value,Err(_)=>return unavailable("Release metadata is invalid.")};
 match compare(&release,env!("CARGO_PKG_VERSION")){Ok(value)=>value,Err(reason)=>unavailable(&reason)}
}
#[cfg(test)]mod tests{
 use super::*;
 fn release(tag:&str)->Value{json!({"tag_name":tag,"draft":false,"prerelease":false,"assets":[{"name":"Biodiversity-Data-Rescue-Workbench-0.7.1-Portable.zip"}]})}
 #[test]fn current_success_is_up_to_date(){assert_eq!(compare(&release("v0.7.0"),"0.7.0").unwrap()["status"],"up-to-date")}
 #[test]fn later_patch_is_discovered(){assert_eq!(compare(&release("v0.7.1"),"0.7.0").unwrap()["status"],"update-available")}
 #[test]fn dev_version_can_discover_stable(){assert_eq!(compare(&release("v0.7.0"),"0.7.0-dev.0").unwrap()["status"],"update-available")}
 #[test]fn invalid_metadata_is_not_current(){assert!(compare(&json!({}),"0.7.0").is_err());assert_eq!(unavailable("Network failed")["status"],"unable-to-check")}
 #[test]fn draft_or_missing_download_is_rejected(){let mut r=release("v0.7.1");r["draft"]=json!(true);assert!(compare(&r,"0.7.0").is_err());r["draft"]=json!(false);r["assets"]=json!([]);assert!(compare(&r,"0.7.0").is_err())}
}
