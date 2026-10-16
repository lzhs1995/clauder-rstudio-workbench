"""流式检查纯数值矩形 DAT 的预期干预；只写显式指定的审计 JSON。"""
import argparse
import hashlib
import json
from decimal import Decimal, InvalidOperation
from itertools import zip_longest
from pathlib import Path


def compare(baseline, candidate, names, keys, expected, allowed, missing=()):
    if not names or len(names)!=len(set(names)):
        raise ValueError('NAMES 必须非空且唯一')
    if not keys or not expected or not set(keys+expected+allowed)<=set(names):
        raise ValueError('必须声明存在的行键、预期变化列及允许变化列')
    if not set(expected)<=set(allowed) or set(keys)&set(allowed):
        raise ValueError('预期列须属于允许列，行键不可作为干预列')
    ki=[names.index(k) for k in keys];seen=set();changes=[0]*len(names);tokens=[0]*len(names);count=0
    # 每行一个个案；空白行忽略。长 ID 使用 Decimal，不通过浮点转换。
    with Path(baseline).open(encoding='utf-8-sig') as a, Path(candidate).open(encoding='utf-8-sig') as b:
        for x,y in zip_longest((s.split() for s in a if s.strip()),(s.split() for s in b if s.strip())):
            if x is None or y is None or len(x)!=len(names) or len(y)!=len(names):
                raise ValueError('样本行数或列数不符')
            def parse(s):return None if s in missing else Decimal(s.replace('D','E').replace('d','e'))
            try:u=[parse(s) for s in x];v=[parse(s) for s in y]
            except InvalidOperation as e:raise ValueError('非数值 DAT token') from e
            if not all(z is None or z.is_finite() for z in u+v):raise ValueError('NaN/Inf 不支持，请核查缺失编码')
            key=tuple(u[j] for j in ki)
            if None in key or key in seen or key!=tuple(v[j] for j in ki):raise ValueError('行键缺失/重复或顺序/身份变化')
            seen.add(key);count+=1
            for j in range(len(names)):
                tokens[j]+=x[j]!=y[j];changes[j]+=u[j]!=v[j]
    if count==0:raise ValueError('空数据不能作为有效对照')
    actual={names[j]:n for j,n in enumerate(changes) if n}
    ok=set(expected)<=set(actual) and set(actual)<=set(allowed)
    def sha(p):
        with Path(p).open('rb') as f:return hashlib.file_digest(f,'sha256').hexdigest()
    return {'rows':count,'columns':len(names),'baseline_sha256':sha(baseline),'candidate_sha256':sha(candidate),
            'numeric_changed_rows_by_column':actual,'token_changed_rows_by_column':{names[j]:n for j,n in enumerate(tokens) if n},
            'expected_changed_columns':expected,'allowed_changed_columns':allowed,'declared_missing_tokens':list(missing),'intervention_present':bool(actual),
            'data_contract_pass':ok,'model_consumption_checked':False,'scientific_release':False}


def main():
    p=argparse.ArgumentParser(description=__doc__)
    for name in ['baseline','candidate','names','output']:p.add_argument('--'+name,required=True)
    for name in ['keys','expected','allowed']:p.add_argument('--'+name,nargs='+',required=True)
    p.add_argument('--missing',nargs='*',default=[],help='显式声明原模型的缺失 token，例如 .；不要猜测缺失编码')
    a=p.parse_args();output=Path(a.output)
    if output.resolve() in {Path(q).resolve() for q in [a.baseline,a.candidate,a.names]}:
        p.error('输出不得覆盖输入')
    result=compare(a.baseline,a.candidate,Path(a.names).read_text(encoding='utf-8-sig').split(),a.keys,a.expected,a.allowed,a.missing)
    output.write_text(json.dumps(result,ensure_ascii=False,indent=2)+'\n',encoding='utf-8')
    print(json.dumps(result,ensure_ascii=False))
    raise SystemExit(0 if result['data_contract_pass'] else 2)


if __name__=='__main__':main()
