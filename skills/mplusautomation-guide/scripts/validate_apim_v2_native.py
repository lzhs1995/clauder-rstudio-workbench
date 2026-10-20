"""独立读取 APIM v2 原生输出，复算 MODEL CONSTRAINT 的效应表达式。"""
from __future__ import annotations
import argparse, csv, hashlib, json, math
from pathlib import Path

def read(path):
    with Path(path).open(encoding='utf-8-sig', newline='') as f:return list(csv.DictReader(f))
def sha(path):return hashlib.sha256(Path(path).read_bytes()).hexdigest()
def validate(root):
    root=Path(root);manifest=read(root/'manifest.csv');checks=[];maxerr=0.0
    for m in manifest:
        folder=root/'models'/m['model_id']/'attempts'/'001'
        params=read(folder/'precision_parameters.csv'); paths=read(folder/'path_dictionary.csv'); effects=read(folder/'effect_dictionary.csv'); values=read(folder/'effects.csv')
        bykey={(x['header'],x['param']):float(x['estimate']) for x in params}
        coeff={}
        for p in paths:
            key=(p['target'].upper()+'.ON',p['pred'].upper())
            if key not in bykey: raise AssertionError((m['model_id'],p['label'],key))
            coeff[p['label'].lower()]=bykey[key]
        if len(effects)!=len(values):raise AssertionError((m['model_id'],'effect_count'))
        # MODEL CONSTRAINT may define a total/conditional effect from earlier
        # NEW parameters.  Expand those derived labels before replacing the
        # free path labels; otherwise a valid expression is mistaken for an
        # unresolved symbol.
        effect_expr={d['label'].lower():d['expression'].lower() for d in effects}
        def expand(expr, stack=()):
            for label in sorted(effect_expr,key=len,reverse=True):
                if label in expr and label not in stack:
                    expr=expr.replace(label, f'({expand(effect_expr[label], stack + (label,))})')
            return expr
        for d,v in zip(effects,values):
            expr=expand(d['expression'].lower())
            for label,value in sorted(coeff.items(),key=lambda x:-len(x[0])):expr=expr.replace(label,f'({value:.17g})')
            if any(ch.isalpha() for ch in expr):raise AssertionError((m['model_id'],d['label'],expr))
            expected=float(eval(expr,{'__builtins__':{}},{})); observed=float(v['estimate']);err=abs(expected-observed);maxerr=max(maxerr,err)
            if err>2e-5:raise AssertionError((m['model_id'],d['label'],err,expr))
            checks.append({'model_id':m['model_id'],'label':d['label'],'formula_error':err})
        binding=json.loads((folder/'output_binding.json').read_text())
        if binding['out_sha256']!=sha(folder/(m['model_id']+'.out')):raise AssertionError((m['model_id'],'output_binding'))
        if binding['results_sha256']!=sha(folder/'results.dat'):raise AssertionError((m['model_id'],'results_binding'))
        if not (folder/(m['model_id']+'.out')).stat().st_size>100:raise AssertionError((m['model_id'],'empty_out'))
    result={'status':'PASS','models':len(manifest),'effects':len(checks),'max_formula_error':maxerr,'independent_numeric_validation':True,'source_artifact_only':True,'checks':checks}
    (root/'independent_native_validation.json').write_text(json.dumps(result,indent=2),encoding='utf-8');print(json.dumps({k:v for k,v in result.items() if k!='checks'}))
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('root');validate(p.parse_args().root)
