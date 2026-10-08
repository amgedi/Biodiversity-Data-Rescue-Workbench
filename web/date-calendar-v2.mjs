const months=['january','february','march','april','may','june','july','august','september','october','november','december'];
export const DATE_FORMATS=['ISO','DMY','MDY','english-day-month','english-month-day','year','month','excel1900','excel1904'];
const fail=()=>{throw new Error('DATE_UNRESOLVED');};
const valid=(year,month,day)=>Number.isInteger(year)&&year>=0&&year<=9999&&month>=1&&month<=12&&day>=1&&day<=[31,year%4===0&&(year%100!==0||year%400===0)?29:28,31,30,31,30,31,31,30,31,30,31][month-1];
const iso=(year,month,day)=>{if(!valid(year,month,day))fail();return `${String(year).padStart(4,'0')}-${String(month).padStart(2,'0')}-${String(day).padStart(2,'0')}`;};
const namedMonth=value=>months.findIndex(month=>month===value.toLowerCase()||month.slice(0,3)===value.toLowerCase())+1;
export function translateCalendarDate(value,format,century=null){
 if(typeof value!=='string'||!DATE_FORMATS.includes(format)||century!==null&&(!Number.isInteger(century)||century<0||century>9900||century%100!==0))fail();if(value==='')return value;
 if(format==='ISO'){const m=value.match(/^(\d{4})-(\d{2})-(\d{2})$/);if(!m)fail();return iso(+m[1],+m[2],+m[3]);}
 if(format==='year'){if(!/^\d{4}$/.test(value))fail();return value;}
 if(format==='month'){const m=value.match(/^(\d{4})-(\d{2})$/);if(!m||+m[2]<1||+m[2]>12)fail();return value;}
 if(format==='excel1900'||format==='excel1904'){if(!/^\d+(?:\.0+)?$/.test(value))fail();const serial=Number(value);if(!Number.isSafeInteger(serial)||serial<0||serial>2958465||format==='excel1900'&&serial===60)fail();const base=format==='excel1904'?Date.UTC(1904,0,1):Date.UTC(1899,11,31),date=new Date(base+(serial-(format==='excel1900'&&serial>60?1:0))*86400000);return iso(date.getUTCFullYear(),date.getUTCMonth()+1,date.getUTCDate());}
 if(format==='DMY'||format==='MDY'){const m=value.match(/^(\d{1,2})([\/-])(\d{1,2})\2(\d{2}|\d{4})$/);if(!m||m[4].length===2&&century===null)fail();const year=m[4].length===2?century+Number(m[4]):Number(m[4]);return iso(year,+(format==='DMY'?m[3]:m[1]),+(format==='DMY'?m[1]:m[3]));}
 let m;if(format==='english-day-month'){m=value.match(/^(\d{1,2})([- ])([A-Za-z]+)\2(\d{4})$/);if(!m)fail();return iso(+m[4],namedMonth(m[3]),+m[1]);}
 m=value.match(/^([A-Za-z]+) (\d{1,2})(?:,)? (\d{4})$/);if(!m)fail();return iso(+m[3],namedMonth(m[1]),+m[2]);
}
export function dateHypotheses(value){if(typeof value!=='string')return [];const m=value.match(/^(\d{1,2})([\/-])(\d{1,2})\2(\d{2}|\d{4})$/);if(!m)return [];return ['DMY','MDY'].flatMap(format=>{const day=+(format==='DMY'?m[1]:m[3]),month=+(format==='DMY'?m[3]:m[1]),year=m[4];if(month<1||month>12||day<1||day>(year.length===4?[31,+year%4===0&&(+year%100!==0||+year%400===0)?29:28,31,30,31,30,31,31,30,31,30,31][month-1]:[31,29,31,30,31,30,31,31,30,31,30,31][month-1]))return [];return [{format,day,month,yearToken:year,centuryUnresolved:year.length===2,scientificInterpretationConfirmed:false}];});}
