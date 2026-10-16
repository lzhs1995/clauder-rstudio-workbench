"""只读提取Mplus模板实例的执行规格；不生成INP、不调用R或Mplus。"""
import argparse
import csv
import hashlib
import json
import re
from collections import Counter
from pathlib import Path, PureWindowsPath


def sha(path):
    with path.open('rb') as stream: return hashlib.file_digest(stream,'sha256').hexdigest()


def active_code(text):
    """保留引号与换行位置；移除!行注释和!*...*!块注释。"""
    out=[];quote=None;block=False;line=False;i=0
    while i<len(text):
        c=text[i];pair=text[i:i+2]
        if block:
            if pair=='*!':out.extend('  ');block=False;i+=2;continue
            out.append('\n' if c=='\n' else ' ')
        elif line:
            out.append('\n' if c=='\n' else ' ')
            if c=='\n':line=False
        elif quote:
            out.append(c)
            if c==quote:quote=None
        elif c in ('"',"'"):quote=c;out.append(c)
        elif pair=='!*':block=True;out.extend('  ');i+=2;continue
        elif c=='!':line=True;out.append(' ')
        else:out.append(c)
        i+=1
    if quote or block:raise ValueError('Unclosed quote or block comment; manual review required')
    return ''.join(out)


def outside_strings(text):
    return re.sub(r'"[^"\n]*"|\x27[^\x27\n]*\x27',lambda m:' '*len(m[0]),text)


def statements(text):
    out=[];start=0;masked=outside_strings(text)
    for m in re.finditer(';',masked):
        value=text[start:m.start()].strip();start=m.end()
        if value:out.append(value)
    tail=text[start:].strip()
    if tail:out.append(tail)
    return out,bool(tail)


def sections(code):
    names=r'MODEL\s+(?:INDIRECT|CONSTRAINT|TEST|POPULATION|COVERAGE)|TITLE|DATA|VARIABLE|DEFINE|ANALYSIS|MODEL|OUTPUT|SAVEDATA|PLOT|MONTECARLO'
    matches=list(re.finditer(r'(?<![\w])('+names+r')\s*:',outside_strings(code),re.I))
    result={};blocks=[]
    for i,m in enumerate(matches):
        name=' '.join(m[1].upper().split())
        body=code[m.end():matches[i+1].start() if i+1<len(matches) else len(code)].strip()
        parsed,tail=([body],False) if name=='TITLE' else statements(body)
        blocks.append(dict(command=name,statements=parsed,trailing_statement_without_semicolon=tail))
        result.setdefault(name,[]).extend(parsed)
    if not {'DATA','VARIABLE','MODEL'}<=result.keys():raise ValueError('Required commands not found')
    return result,blocks


def option(rows, aliases):
    found=[]
    for row in rows:
        m=re.fullmatch(r'\s*(?:'+aliases+r')\s*(?:=|\bARE\b|\bIS\b)\s*(.*?)\s*',row,re.S|re.I)
        if m:found.append(m[1])
    if len(found)>1:raise ValueError('Duplicate option: '+aliases)
    return found[0] if found else None


def inspect(text):
    code=active_code(text);part,blocks=sections(code)
    variable=part['VARIABLE'];analysis=part.get('ANALYSIS',[]);model=part['MODEL']
    constraints=part.get('MODEL CONSTRAINT',[])
    labels=[]
    for index,row in enumerate(model):
        labels.extend(dict(label=m[1].upper(),statement_index=index,statement=row)
                      for m in re.finditer(r'\(\s*([A-Za-z][A-Za-z0-9_]*)\s*\)',row))
    repeated={label:count for label,count in Counter(r['label'] for r in labels).items() if count>1}
    new=[]
    for row in constraints:
        m=re.fullmatch(r'NEW\s*\((.*?)\)',row,re.S|re.I)
        if m:new.extend(re.findall(r'\b[A-Za-z][A-Za-z0-9_]*\b',m[1]))
    output='; '.join(part.get('OUTPUT',[]))
    ci=re.search(r'\bCINT(?:ERVAL)?\s*(?:\(([^)]+)\))?',output,re.I)
    paths={'ON':[],'WITH':[],'PWITH':[],'other':[]}
    for row in model:
        operator=next((k for k in ['ON','PWITH','WITH'] if re.search(r'\b'+k+r'\b',outside_strings(row),re.I)), 'other')
        paths[operator].append(row)
    quoted=re.split(r'("[^"\n]*"|\x27[^\x27\n]*\x27)',code)
    canonical=''.join(s if i%2 else re.sub(r'\s+',' ',s) for i,s in enumerate(quoted)).strip()
    return dict(active_code_sha256=hashlib.sha256(canonical.encode('utf-8')).hexdigest(),
      sections=part,ordered_command_blocks=blocks,
      repeated_commands={k:v for k,v in Counter(b['command'] for b in blocks).items() if v>1},
      trailing_statement_commands=[b['command'] for b in blocks if b['trailing_statement_without_semicolon']],
      data_file=option(part['DATA'],'FILE'),
      names_declaration=option(variable,'NAMES?|NAMESOFVARIABLES'),
      usevariables_declaration=option(variable,'USEVAR(?:IABLES)?'),
      missing_declaration=option(variable,'MISSING'),id_variable=option(variable,'IDVARIABLE'),
      cluster=option(variable,'CLUSTER'),useobservations=option(variable,'USEOBS(?:ERVATIONS)?'),
      subpopulation=option(variable,'SUBPOPULATION'),grouping=option(variable,'GROUPING'),
      estimator=option(analysis,'ESTIMATOR'),analysis_type=option(analysis,'TYPE'),
      bootstrap=option(analysis,'BOOTSTRAP'),processors=option(analysis,'PROCESSORS?'),
      starts=option(analysis,'STARTS'),cinterval=ci[1].upper() if ci and ci[1] else 'SYMMETRIC_DEFAULT' if ci else None,
      equations=paths,label_occurrences=labels,repeated_single_labels=repeated,
      additional_parameter_names=new,additional_parameter_names_unique=len(new)==len(set(v.upper() for v in new)),
      new_parameter_block_count=sum(bool(re.match(r'^NEW\s*\(',row,re.I)) for row in constraints),
      active_indirect_statements=part.get('MODEL INDIRECT',[]),
      constraint_statements=constraints,
      interpretation='Literal syntax inventory; no native syntax or scientific acceptance')


def manifest_contract(manifest, output):
    rows=list(csv.DictReader(manifest.open(encoding='utf-8-sig',newline='')))
    required=['model_id','registered_inp','registered_inp_sha256','template','template_sha256','substitutions','sandbox_relative_path']
    if not rows or any(k not in rows[0] for k in required):raise ValueError('Missing manifest fields')
    # Windows将斜杠、反斜杠及单点目录视为同一路径，先标准化再判重。
    output_paths=[PureWindowsPath(r['sandbox_relative_path']) for r in rows]
    if len({str(p).casefold() for p in output_paths})!=len(rows):raise ValueError('Output path collision')
    for p in output_paths:
        if p.drive or p.root or '..' in p.parts or p.suffix.lower()!='.inp':
            raise ValueError('Expected confined relative INP output path')
    if output.exists():raise ValueError('Use a fresh contract directory')
    output.mkdir(parents=True);seen={};records=[]
    with (output/'model_specifications.jsonl').open('w',encoding='utf-8') as destination:
        for i,r in enumerate(rows):
            inp=Path(r['registered_inp']);template=Path(r['template'])
            for p,expected in [(inp,r['registered_inp_sha256']),(template,r['template_sha256'])]:
                if str(p) not in seen:seen[str(p)]=sha(p)
                if seen[str(p)]!=expected:raise ValueError('Frozen source hash changed: '+str(p))
            try:model=inspect(inp.read_text(encoding='utf-8-sig'))
            except Exception as exc:
                (output/'failure.json').write_text(json.dumps(dict(model_id=r['model_id'],input=str(inp),
                    completed_models=i,error=str(exc),authorizes_execution=False),ensure_ascii=False,indent=2),encoding='utf-8')
                raise
            record=dict(model_id=r['model_id'],input_path=str(inp),input_sha256=r['registered_inp_sha256'],
              template=str(template),template_sha256=r['template_sha256'],substitutions=json.loads(r['substitutions']),
              manuscript_dependency=r.get('manuscript_dependency','False')=='True',
              planned_output=r['sandbox_relative_path'],specification=model,
              source_chain_status='NOT_ASSESSED_BY_SYNTAX_INVENTORY',authorizes_execution=False)
            destination.write(json.dumps(record,ensure_ascii=False)+'\n')
            records.append(dict(model_id=r['model_id'],manuscript_dependency=record['manuscript_dependency'],
              input_sha256=record['input_sha256'],active_code_sha256=model['active_code_sha256'],
              repeated_single_labels=';'.join(model['repeated_single_labels']),
              equality_label_count=len(model['repeated_single_labels']),estimator=model['estimator'],
              analysis_type=model['analysis_type'],cinterval=model['cinterval'],bootstrap=model['bootstrap'],
              equation_statements=sum(len(v) for v in model['equations'].values()),
              new_parameters=len(model['additional_parameter_names']),
              indirect_statements=len(model['active_indirect_statements']),
              repeated_commands=';'.join(model['repeated_commands']),
              trailing_statement_commands=';'.join(model['trailing_statement_commands'])))
            if (i+1)%200==0:print('STATIC_SPECIFICATIONS',i+1,'/',len(rows),flush=True)
    with (output/'model_features.csv').open('w',encoding='utf-8-sig',newline='') as stream:
        writer=csv.DictWriter(stream,fieldnames=records[0]);writer.writeheader();writer.writerows(records)
    result=dict(status='STATIC_LITERAL_SPECIFICATIONS_ONLY',models=len(records),templates=len({r['template'] for r in rows}),
      manuscript_models=sum(r['manuscript_dependency'] for r in records),
      models_with_repeated_single_labels=sum(bool(r['repeated_single_labels']) for r in records),
      required_with_repeated_single_labels=sum(bool(r['repeated_single_labels']) and r['manuscript_dependency'] for r in records),
      inference_counts=dict(Counter(str(r['estimator'])+' / '+str(r['analysis_type'])+' / '+str(r['cinterval']) for r in records)),
      manifest_sha256=sha(manifest),specifications_sha256=sha(output/'model_specifications.jsonl'),
      features_sha256=sha(output/'model_features.csv'),parser_sha256=sha(Path(__file__)),
      original_files_changed=False,runnable_inputs_written=0,new_estimation=0,authorizes_execution=False)
    (output/'receipt.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False));return result


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('manifest',type=Path);p.add_argument('--output',type=Path,required=True)
    a=p.parse_args();manifest_contract(a.manifest,a.output)
