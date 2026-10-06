"""Reversible, user-scoped Windows LocalDumps configuration for certification."""
import argparse
import json
import os
from pathlib import Path
import re
import sys
from uuid import uuid4


SCHEMA='arms.windows-localdumps-rollback.v1'
ROOT=r'Software\Microsoft\Windows\Windows Error Reporting\LocalDumps'
VALUE_NAMES=('DumpFolder','DumpCount','DumpType')


def _winreg():
    if os.name!='nt':
        raise RuntimeError('WINDOWS_REQUIRED')
    import winreg
    return winreg


def _image(value):
    if type(value) is not str or re.fullmatch(r'[A-Za-z0-9._-]{1,120}\.exe',value) is None:
        raise ValueError('DUMP_IMAGE_NAME_INVALID')
    return value


def _atomic(path,value):
    raw=json.dumps(value,sort_keys=True,indent=2).encode('utf-8')
    temporary=path.with_name(path.name+'.'+uuid4().hex+'.tmp')
    try:
        with temporary.open('xb') as stream:
            stream.write(raw);stream.flush();os.fsync(stream.fileno())
        os.replace(temporary,path)
    finally:
        temporary.unlink(missing_ok=True)


def enable_local_dumps(*,image_name,dump_folder,rollback_path,dump_count=10):
    winreg=_winreg();image_name=_image(image_name)
    if type(dump_count) is not int or not 1<=dump_count<=100:
        raise ValueError('DUMP_COUNT_INVALID')
    dump_folder=Path(dump_folder).resolve()
    rollback_path=Path(rollback_path).resolve()
    if rollback_path.exists():
        raise FileExistsError('ROLLBACK_ALREADY_EXISTS')
    dump_folder.mkdir(parents=True,exist_ok=True)
    key_path=ROOT+'\\'+image_name
    prior={};key_existed=True
    try:
        key=winreg.OpenKey(winreg.HKEY_CURRENT_USER,key_path,0,
            winreg.KEY_QUERY_VALUE|winreg.KEY_SET_VALUE)
    except FileNotFoundError:
        key_existed=False
        key=winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,key_path,0,
            winreg.KEY_QUERY_VALUE|winreg.KEY_SET_VALUE)
    with key:
        for name in VALUE_NAMES:
            try:
                value,kind=winreg.QueryValueEx(key,name)
                prior[name]={'present':True,'value':value,'kind':kind}
            except FileNotFoundError:
                prior[name]={'present':False}
        rollback={'schema':SCHEMA,'image_name':image_name,'key_path':key_path,
            'key_existed':key_existed,'prior':prior,
            'configured':{'DumpFolder':str(dump_folder),
                'DumpCount':dump_count,'DumpType':2}}
        _atomic(rollback_path,rollback)
        winreg.SetValueEx(key,'DumpFolder',0,winreg.REG_EXPAND_SZ,str(dump_folder))
        winreg.SetValueEx(key,'DumpCount',0,winreg.REG_DWORD,dump_count)
        winreg.SetValueEx(key,'DumpType',0,winreg.REG_DWORD,2)
        winreg.FlushKey(key)
    return rollback


def restore_local_dumps(*,rollback_path):
    winreg=_winreg();rollback_path=Path(rollback_path).resolve()
    value=json.loads(rollback_path.read_text(encoding='utf-8'))
    if (type(value) is not dict or value.get('schema')!=SCHEMA
            or _image(value.get('image_name'))!=value['image_name']
            or value.get('key_path')!=ROOT+'\\'+value['image_name']
            or set(value.get('prior',{}))!=set(VALUE_NAMES)):
        raise ValueError('ROLLBACK_INVALID')
    key=winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER,value['key_path'],0,
        winreg.KEY_QUERY_VALUE|winreg.KEY_SET_VALUE)
    with key:
        for name in VALUE_NAMES:
            prior=value['prior'][name]
            if prior.get('present') is True:
                winreg.SetValueEx(key,name,0,prior['kind'],prior['value'])
            elif prior=={'present':False}:
                try:winreg.DeleteValue(key,name)
                except FileNotFoundError:pass
            else:
                raise ValueError('ROLLBACK_VALUE_INVALID')
        winreg.FlushKey(key)
    if value.get('key_existed') is False:
        try:winreg.DeleteKey(winreg.HKEY_CURRENT_USER,value['key_path'])
        except OSError:pass
    return {'schema':SCHEMA,'restored':True,'image_name':value['image_name']}


def main(argv=None):
    parser=argparse.ArgumentParser(
        description='Reversible HKCU LocalDumps setup for offline certification.')
    commands=parser.add_subparsers(dest='command',required=True)
    enable=commands.add_parser('enable')
    enable.add_argument('--image-name',required=True)
    enable.add_argument('--dump-folder',type=Path,required=True)
    enable.add_argument('--rollback-file',type=Path,required=True)
    enable.add_argument('--dump-count',type=int,default=10)
    restore=commands.add_parser('restore')
    restore.add_argument('--rollback-file',type=Path,required=True)
    args=parser.parse_args(argv)
    if args.command=='enable':
        result=enable_local_dumps(image_name=args.image_name,
            dump_folder=args.dump_folder,rollback_path=args.rollback_file,
            dump_count=args.dump_count)
    else:
        result=restore_local_dumps(rollback_path=args.rollback_file)
    print(json.dumps(result,sort_keys=True),flush=True)
    return 0


if __name__=='__main__':
    sys.exit(main())
