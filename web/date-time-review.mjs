import {translateCalendarDate} from './date-calendar-v2.mjs';
const fail=()=>{throw Error('DATE_TIME_UNRESOLVED');};
export function reviewedOffset(value){
 if(value==='Z')return value;
 if(typeof value!=='string'||!/^[-+]\d{2}:\d{2}$/.test(value)||value==='-00:00')fail();
 const hours=Number(value.slice(1,3)),minutes=Number(value.slice(4));
 if(hours>14||minutes>59||hours===14&&minutes!==0)fail();return value;
}
export function reviewedTime(value,assumedOffset=''){
 const m=typeof value==='string'&&value.match(/^(\d{2}):(\d{2})(?::(\d{2})(\.\d{1,9})?)?(Z|[-+]\d{2}:\d{2})?$/);
 if(!m||Number(m[1])>23||Number(m[2])>59||m[3]&&Number(m[3])>59)fail();
 const explicit=m[5]||'',offset=reviewedOffset(explicit||assumedOffset);
 if(explicit&&assumedOffset&&reviewedOffset(assumedOffset)!==explicit)fail();
 return value.slice(0,value.length-explicit.length)+offset;
}
export function translateReviewedDateTime(dateLiteral,spec,timeLiteral=null){
 if(spec.dateTimePolicy!=='offset-v1')fail();
 if(spec.format==='ISO-datetime'){
  const m=typeof dateLiteral==='string'&&dateLiteral.match(/^(\d{4}-\d{2}-\d{2})[T ](.+)$/);
  if(!m)fail();return translateCalendarDate(m[1],'ISO')+'T'+reviewedTime(m[2],spec.dateUTCOffset||'');
 }
 if(typeof timeLiteral!=='string'||!timeLiteral)fail();
 const date=translateCalendarDate(dateLiteral,spec.format,spec.dateCentury??null);
 if(!/^\d{4}-\d{2}-\d{2}$/.test(date))fail();
 return date+'T'+reviewedTime(timeLiteral,spec.dateUTCOffset||'');
}
