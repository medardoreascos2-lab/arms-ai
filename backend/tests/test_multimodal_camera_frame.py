from datetime import datetime,timezone
import pytest
from backend.multimodal.camera_frame import CameraFrame,FrameRetentionPolicy
NOW=datetime(2026,10,4,12,tzinfo=timezone.utc)
def test_frame_is_metadata_only_and_defaults_can_prohibit_storage():
 f=CameraFrame("f","c",NOW,"image/jpeg",640,480,FrameRetentionPolicy.NO_STORAGE,"consent","frame:1");assert f.retention_policy==FrameRetentionPolicy.NO_STORAGE
def test_frame_contract_has_no_raw_bytes_or_long_term_retention():
 assert {x.value for x in FrameRetentionPolicy}=={"NO_STORAGE","SESSION_ONLY"}
 with pytest.raises(TypeError):CameraFrame("f","c",NOW,"image/jpeg",1,1,FrameRetentionPolicy.NO_STORAGE,"consent","frame:1",raw_bytes=b"x")
