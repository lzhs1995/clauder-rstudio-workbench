"""独立复算实际输出效应与区间；仅读取生成资产，写独立验收回执。"""
import argparse
import csv
import hashlib
import json
import math
import re
import zipfile
import xml.etree.ElementTree as ET
from pathlib import Path
from statistics import NormalDist


def rows(path):
    with path.open(encoding='utf-8-sig', newline='') as f:
        return list(csv.DictReader(f))


def native_bc_new_parameters(raw):
    """独立读原生OUT区间表，避免把R的CI提取错误再当作参考。"""
    lines = raw.splitlines()
    start = [i for i, line in enumerate(lines) if line.strip() == 'CONFIDENCE INTERVALS OF MODEL RESULTS']
    assert len(start) == 1
    numeric = r'[+-]?(?:\d+(?:\.\d*)?|\.\d+)(?:[EeDd][+-]?\d+)?'
    row = re.compile(r'^\s*(\w+)\s+' + r'\s+'.join([f'({numeric})'] * 7) + r'\s*$')
    result, active = {}, False
    for line in lines[start[0]+1:]:
        if re.match(r'^\s*(CONFIDENCE INTERVALS OF|TECHNICAL|STANDARDIZED|TOTAL, TOTAL INDIRECT|DIAGRAM|PLOT INFORMATION|SAVEDATA INFORMATION|RESULTS SAVING)', line):
            break
        if line.strip() == 'New/Additional Parameters':
            active = True
        match = row.match(line) if active else None
        if match:
            label = match[1].upper()
            assert label not in result
            result[label] = [float(v.replace('D','E').replace('d','e')) for v in match.groups()[1:]]
    assert result, 'Missing native additional-parameter CI table'
    return result


def validate(root, render_root=None):
    root = Path(root)
    render = Path(render_root) if render_root else root
    manifest = rows(root / 'manifest.csv')
    effects = rows(root / 'effects.csv')
    assert len({m['model_id'] for m in manifest}) == len(manifest)
    assert len({(e['model_id'], e['label']) for e in effects}) == len(effects)
    checks = []
    for m in manifest:
        folder = root / m['model_id']
        params = rows(folder / 'precision_parameters.csv')
        get = {(r['header'], r['param']): float(r['estimate']) for r in params}
        coefficient = lambda outcome, predictor: get[(outcome + '.ON', predictor)]
        c = lambda j, k: coefficient(f'Y{j}', f'X{k}')
        a = lambda v, k: coefficient(f'M{v}', f'X{k}')
        b = lambda j, v: coefficient(f'Y{j}', f'M{v}')
        z = lambda j, v, h: coefficient(f'Y{j}', f'P{v}{h}')
        model_effects = [e for e in effects if e['model_id'] == m['model_id']]
        # 独立读取实际展开INP中的条件点，不默认把名称lo/hi当作正负1SD。
        syntax = (folder/'model_1.inp').read_text(encoding='utf-8')
        bc = any(e['interval_method'] == 'Mplus_native_ML_BCbootstrap' for e in model_effects)
        native = native_bc_new_parameters((folder/'model_1.out').read_text(encoding='utf-8')) if bc else {}
        probes = {name:(float(w1),float(w2)) for name,w1,w2 in re.findall(
            r'^s11([a-z0-9]+) = [bc]11 \+ z111\*\(([^)]+)\) \+ z112\*\(([^)]+)\);',syntax,re.M)}
        mediation = m['family'] in ('APIMeM', 'APIMeMoM')
        slope = lambda j, v, w: (b(j, v) if mediation else c(j, v)) + sum(z(j, v, h) * w[h-1] for h in (1, 2))
        for e in model_effects:
            j, k = int(e['target']), int(e['source'])
            kind, probe = e['kind'], e['probe']
            if kind == 'direct': expected = c(j, k)
            elif kind == 'indirect': expected = a(int(e['via']), k) * b(j, int(e['via']))
            elif kind == 'total': expected = c(j, k) + sum(a(v, k) * b(j, v) for v in (1, 2))
            elif kind == 'simple_slope': expected = slope(j, k, probes[probe])
            elif kind == 'conditional_indirect': expected = a(int(e['via']), k) * slope(j, int(e['via']), probes[probe])
            elif kind == 'conditional_contrast':
                hi,lo=probe.split('-')
                expected = a(int(e['via']), k) * (slope(j, int(e['via']), probes[hi]) - slope(j, int(e['via']), probes[lo]))
            elif kind == 'slope_contrast':
                hi,lo=probe.split('-')
                expected = slope(j, k, probes[hi]) - slope(j, k, probes[lo])
            else: raise ValueError(kind)
            est, se = float(e['estimate']), float(e['se'])
            error = abs(est-expected)
            # SAVEDATA各参数有限有效位，乘积有累积舍入误差；提前固定绝对阈值。
            assert error < 2e-6, (m['model_id'], e['label'], error)
            if bc:
                assert e['interval_method'] == 'Mplus_native_ML_BCbootstrap'
                ci = native[e['label']]
                for level, lo, hi in ((90,2,4),(95,1,5),(99,0,6)):
                    assert float(e[f'lower{level}']) == ci[lo]
                    assert float(e[f'upper{level}']) == ci[hi]
                assert abs(est-ci[3]) <= .00050001
                assert e['p_method'] == 'Wald_normal_with_native_bootstrap_SE_not_BC_pvalue'
                assert e['bootstrap_requested'] == e['bootstrap_completed']
                assert e['resampling_unit'] == 'row'
            else:
                assert e['interval_method'] == 'Mplus_MLR_spouse_cluster_delta_normal'
                for level in (90, 95):
                    critical = NormalDist().inv_cdf((1 + level/100)/2)
                    assert abs(float(e[f'lower{level}']) - (est-critical*se)) < 1e-10
                    assert abs(float(e[f'upper{level}']) - (est+critical*se)) < 1e-10
            assert e['scientific_released'].upper() == 'FALSE'
            checks.append({'model_id': m['model_id'], 'label': e['label'], 'formula_error': error})
        for ext in ('png','pdf','svg'):
            assert (render / 'figures' / (m['model_id']+'.'+ext)).stat().st_size > 100
        plot=rows(render/'figures'/(m['model_id']+'_plot_data.csv'))
        assert len(plot)==len(model_effects)
        for original,display in zip(model_effects,plot,strict=True):
            assert all(original[k]==display[k] for k in original), 'Plot data differ from effect source'
    assert (render/'tables.docx').stat().st_size > 1000
    # 实际Word列宽必须落在页面内；逐格核查显示的舍入值。
    word='{http://schemas.openxmlformats.org/wordprocessingml/2006/main}'
    doc=ET.fromstring(zipfile.ZipFile(render/'tables.docx').read('word/document.xml'))
    section=doc.find('.//'+word+'sectPr');page=section.find(word+'pgSz');margin=section.find(word+'pgMar')
    available=int(page.get(word+'w'))-int(margin.get(word+'left'))-int(margin.get(word+'right'))
    widths=[sum(int(c.get(word+'w')) for c in g) for g in doc.iter(word+'tblGrid')]
    assert len(widths)==len(manifest) and max(widths)<=available, 'Word table exceeds page content width'
    cells=0
    for model,table in zip(manifest,list(doc.iter(word+'tbl')),strict=True):
        expected=[e for e in effects if e['model_id']==model['model_id']]
        table_rows=table.findall(word+'tr');assert len(table_rows)==len(expected)+1
        values=lambda row:[''.join(x.text or '' for x in c.iter(word+'t')) for c in row.findall(word+'tc')]
        header=values(table_rows[0])
        for e,row in zip(expected,table_rows[1:],strict=True):
            for name,text in zip(header,values(row),strict=True):
                if name in ('label','kind','probe'):assert text==e[name]
                elif e[name] in ('NA',''):assert text in ('NA','')
                else:
                    tolerance=.000050001 if name in ('p','p_BH','p_BY') else .00050001
                    assert abs(float(text.replace(',',''))-float(e[name]))<=tolerance
                cells+=1
    result = dict(models=len(manifest), effects=len(checks), max_formula_error=max(c['formula_error'] for c in checks),
                  effects_sha256=hashlib.sha256((root/'effects.csv').read_bytes()).hexdigest(),
                  independent_numeric_validation=True, word_cells_checked=cells,
                  word_tables_fit_page=True, render_root=str(render),visual_review='pending', scientific_closed=False,
                  scope='four-family executable workflow; probe values independently read from expanded INP', checks=checks)
    (root/'independent_validation.json').write_text(json.dumps(result,ensure_ascii=False,indent=2),encoding='utf-8')
    print(json.dumps({k:v for k,v in result.items() if k!='checks'},ensure_ascii=False))


if __name__ == '__main__':
    p = argparse.ArgumentParser(); p.add_argument('root');p.add_argument('--render-root')
    args=p.parse_args();validate(args.root,args.render_root)
