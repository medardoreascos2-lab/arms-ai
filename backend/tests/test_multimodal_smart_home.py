import inspect,pytest
from backend.multimodal.smart_home import SmartHomeCapability,SmartHomeProposal
def test_smart_home_capabilities_are_proposed_only():
 assert {x.value for x in SmartHomeCapability}=={"LIGHT","HVAC","CURTAIN","TV","SPEAKER","APPLIANCE"}
 p=SmartHomeProposal("p",SmartHomeCapability.LIGHT,"device:1","Would turn on light");assert p.state=="PROPOSED_ONLY" and not p.device_control_authorized and not p.execution_authorized
def test_smart_home_seam_rejects_control_authority():
 with pytest.raises(ValueError):SmartHomeProposal("p",SmartHomeCapability.TV,"d","x",device_control_authorized=True)
