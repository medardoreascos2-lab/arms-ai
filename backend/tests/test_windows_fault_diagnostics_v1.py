"""Transient HKCU LocalDumps test using a unique non-existent image name."""
from pathlib import Path
import sys
from uuid import uuid4

import pytest

from tools.windows_fault_diagnostics_v1 import (
    ROOT,enable_local_dumps,restore_local_dumps,
)


pytestmark=pytest.mark.skipif(sys.platform!='win32',reason='Windows registry required')


def test_localdumps_configuration_is_exact_and_reversible(tmp_path):
    import winreg
    image='arms-r24b-test-'+uuid4().hex+'.exe'
    rollback=tmp_path/'rollback.json'
    dumps=tmp_path/'dumps'
    try:
        result=enable_local_dumps(image_name=image,dump_folder=dumps,
            rollback_path=rollback,dump_count=3)
        assert result['key_existed'] is False
        assert rollback.is_file() and dumps.is_dir()
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER,ROOT+'\\'+image) as key:
            assert winreg.QueryValueEx(key,'DumpFolder')[0]==str(dumps.resolve())
            assert winreg.QueryValueEx(key,'DumpCount')[0]==3
            assert winreg.QueryValueEx(key,'DumpType')[0]==2
        restored=restore_local_dumps(rollback_path=rollback)
        assert restored=={'schema':'arms.windows-localdumps-rollback.v1',
            'restored':True,'image_name':image}
        with pytest.raises(FileNotFoundError):
            winreg.OpenKey(winreg.HKEY_CURRENT_USER,ROOT+'\\'+image)
    finally:
        try:restore_local_dumps(rollback_path=rollback)
        except (OSError,ValueError,FileNotFoundError):pass
