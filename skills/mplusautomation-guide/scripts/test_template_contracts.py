"""测试执行规格读取边界；仅使用临时合成输入。"""
import argparse
import csv
import hashlib
import json
import tempfile
from pathlib import Path
import template_contracts as t

BASE='''TITLE: synthetic;
DATA: FILE = "a!b; data.dat";
VARIABLE:
NAMES = x1 x2 y1 y2;
USEVARIABLES = x1 x2 y1 y2;
ANALYSIS: TYPE = COMPLEX; ESTIMATOR = MLR;
MODEL:
y1 ON x1 (a); ! y1 ON x2 (fake);
y2 ON x2 (A);
y1 WITH y2;
!* MODEL INDIRECT:
y1 IND x1;
*!
MODEL CONSTRAINT: NEW(i); i = a*a;
OUTPUT: CINTERVAL;
'''


def run(output):
    checks={}
    def check(name,value): assert value,name;checks[name]=True
    def rejects(fn):
        try:fn()
        except (ValueError,AssertionError):return True
        return False
    model=t.inspect(BASE)
    check('quoted_bang_and_semicolon_preserved',model['data_file']=='"a!b; data.dat"')
    check('line_comment_does_not_add_label',not any(r['label']=='FAKE' for r in model['label_occurrences']))
    check('block_comment_hides_indirect',model['active_indirect_statements']==[])
    check('case_insensitive_equality_label',model['repeated_single_labels']=={'A':2})
    check('derived_expression_preserved',model['constraint_statements']==['NEW(i)','i = a*a'])
    check('command_options_parsed',model['estimator']=='MLR' and model['analysis_type']=='COMPLEX')
    check('normal_CI_default_recorded',model['cinterval']=='SYMMETRIC_DEFAULT')
    duplicated=t.inspect(BASE.replace('VARIABLE:','VARIABLE:\nVARIABLE:'))
    check('empty_repeated_command_preserved',duplicated['repeated_commands']=={'VARIABLE':2} and
          sum(b['command']=='VARIABLE' for b in duplicated['ordered_command_blocks'])==2)
    tail=t.inspect(BASE.replace('USEVARIABLES = x1 x2 y1 y2;','USEVARIABLES = x1 x2 y1 y2'))
    check('missing_final_semicolon_recorded_not_repaired',tail['trailing_statement_commands']==['VARIABLE'])
    check('quoted_spaces_affect_identity',t.inspect(BASE.replace('a!b; data','a!b;  data'))['active_code_sha256']!=model['active_code_sha256'])
    check('unclosed_block_rejected',rejects(lambda:t.inspect(BASE.replace('*!',''))))
    check('unclosed_quote_rejected',rejects(lambda:t.inspect(BASE.replace('data.dat"','data.dat'))))
    with tempfile.TemporaryDirectory() as folder:
        root=Path(folder);inp=root/'m.inp';template=root/'m.txt';inp.write_text(BASE,encoding='utf-8');template.write_text('synthetic template marker',encoding='utf-8')
        original=inp.read_bytes();row=dict(model_id='m',registered_inp=str(inp),registered_inp_sha256=t.sha(inp),
          template=str(template),template_sha256=t.sha(template),substitutions='{}',sandbox_relative_path='layer/m.inp',manuscript_dependency='True')
        path=root/'manifest.csv'
        def write(rows):
            with path.open('w',encoding='utf-8',newline='') as stream:
                w=csv.DictWriter(stream,fieldnames=row);w.writeheader();w.writerows(rows)
        write([row]);result=t.manifest_contract(path,root/'contracts')
        check('source_bytes_unchanged',inp.read_bytes()==original)
        check('no_runnable_inputs_written',result['runnable_inputs_written']==0 and not list((root/'contracts').rglob('*.inp')))
        check('existing_contract_directory_rejected',rejects(lambda:t.manifest_contract(path,root/'contracts')))
        write([row,row]);check('output_collision_rejected',rejects(lambda:t.manifest_contract(path,root/'collision')))
        for alias in ['LAYER\\M.inp','layer/./m.inp']:
            write([row,dict(row,model_id='second',sandbox_relative_path=alias)])
            check('windows_path_alias_collision_'+alias,rejects(lambda:t.manifest_contract(path,root/'alias_collision')))
        for value in ['../outside.inp','C:/outside.inp','\\outside.inp']:
            write([dict(row,sandbox_relative_path=value)])
            check('reject_output_'+value,rejects(lambda:t.manifest_contract(path,root/'escape')))
        write([dict(row,registered_inp_sha256='0'*64)])
        check('changed_input_hash_rejected',rejects(lambda:t.manifest_contract(path,root/'wrong_hash')))
    result=dict(status='PASS_STATIC_CONTRACT_TESTS',checks=checks,parser_sha256=t.sha(Path(t.__file__)),
                new_mplus_calls=0,research_files_modified=0)
    output.parent.mkdir(parents=True,exist_ok=True);output.write_text(json.dumps(result,indent=2),encoding='utf-8')
    print('STATIC_CONTRACT_CHECKS_PASS',len(checks))


if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('output',type=Path);run(p.parse_args().output)
