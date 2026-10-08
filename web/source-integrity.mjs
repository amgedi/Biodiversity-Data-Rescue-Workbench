// A checksum alone cannot certify the declared byte length of a retained source.
export function sourceIntegrityPassed(results){return Array.isArray(results)&&results.length>0&&results.every(r=>r.backupMatches===true&&r.diskMatches===true&&r.backupByteLengthMatches===true&&r.diskByteLengthMatches===true);}
