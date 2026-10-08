import html, json
from datetime import datetime,timezone
def report_data(p,checks,locale="en"):
    from standards import PROFILES
    from dwc_dp import capability
    data={'applicationVersion':'0.5.0-dev.2','projectSchemaVersion':p.get('projectSchemaVersion',2),'projectId':p['id'],'title':p['metadata']['title']['value'],'generatedAt':datetime.now(timezone.utc).isoformat(),'sources':[{k:v for k,v in r.items() if k!='base64'} for r in p['resources']],'tables':[{'id':t['id'],'name':t['name'],'rows':len(t['rows']),'fields':t['columns']} for t in p['tables']],'metadata':p['metadata'],'relationships':p['relationships'],'evidenceAssertions':p.get('evidenceAssertions',[]),'migrationHistory':p.get('migrationHistory',[]),'audit':[ {k:v for k,v in e.items() if k not in ('before','after')} for e in p['audit']],'validation':checks,'standards':p['profiles'],'standardCapabilities':PROFILES,'dwcDP':capability(),'reportLanguage':'en','scientificallyValidated':False,'citation':p['metadata'].get('citation',{}).get('value') or 'Creators/citation unknown or not reviewed; no authorship invented.'}
    from localization import catalog,display_findings
    catalog(locale)
    data["reportLanguage"]=locale;data["displayValidation"]=display_findings(checks,locale)
    data["translationReview"]="machine-assisted; independent linguistic review pending" if locale!="en" else "source language"
    return data

SECTION_LABELS={'sources':'Sources','tables':'Tables','metadata':'Metadata','relationships':'Relationships','evidenceAssertions':'Evidence assertions','migrationHistory':'Migration history','audit':'Audit history','validation':'Validation findings','standards':'Selected standards','standardCapabilities':'Standard capabilities','dwcDP':'Darwin Core Data Package'}
NOTICE='Technical validity is not scientific correctness. Unknowns, inferences and conflicts remain visible. This private report can contain sensitive original context.'
def report_html(data):
    from localization import message
    locale=data.get('reportLanguage','en');tr=lambda text,args=None:message(text,locale,args);esc=lambda v:html.escape(str(v))
    parts=[]
    for name,label in SECTION_LABELS.items():
        value=data.get('displayValidation',data['validation']) if name=='validation' else data[name]
        parts.append('<section><h2>'+esc(tr(label))+'</h2><pre>'+esc(json.dumps(value,ensure_ascii=False,indent=2))+'</pre></section>')
    direction='rtl' if locale=='ar' else 'ltr'
    return ('<!doctype html><html lang="'+locale+'" dir="'+direction+'"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>'+esc(data['title'])+' · '+esc(tr('Rescue Report'))+'</title><style>body{font:16px system-ui;color:#173e35;background:#f6f8f3;max-width:1000px;margin:auto;padding:32px}section{background:white;padding:20px;margin:20px 0;border:1px solid #cad4c7}pre{white-space:pre-wrap;overflow-wrap:anywhere;font-size:13px;unicode-bidi:plaintext}h1{font:36px Georgia}</style></head><body><h1>'+esc(data['title'])+'</h1><p>'+esc(tr('Rescue Report · Workbench {version} · schema {schema}',{'version':data['applicationVersion'],'schema':data['projectSchemaVersion']}))+'</p><p>'+esc(tr('Generated {at}',{'at':data['generatedAt']}))+'</p><p>'+esc(tr(NOTICE))+'</p>'+''.join(parts)+'</body></html>').encode('utf-8')
def report_markdown(data):
    from localization import message
    locale=data.get('reportLanguage','en');tr=lambda text:message(text,locale)
    lines=['# '+data['title'],'',tr('Rescue Report'),'',tr(NOTICE),'']
    for name,label in SECTION_LABELS.items():
        value=data.get('displayValidation',data['validation']) if name=='validation' else data[name]
        lines.extend(['## '+tr(label),'','```json',json.dumps(value,ensure_ascii=False,indent=2),'```',''])
    return '\n'.join(lines).encode('utf-8')
