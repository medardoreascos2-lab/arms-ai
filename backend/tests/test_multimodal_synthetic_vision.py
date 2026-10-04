import pytest
from backend.multimodal.synthetic_vision import SyntheticVisionProvider
from backend.multimodal.vision_provider import VisionObservation

def test_synthetic_vision_returns_only_registered_explicit_fixture():
 fixture=VisionObservation("image:1","DESCRIBE",("Synthetic blue square.",),(),1.0,"LOCAL_TEST_ONLY_SYNTHETIC_VISION",True,("No real visual analysis performed.",));provider=SyntheticVisionProvider({("image:1","DESCRIBE"):fixture})
 assert provider.describe_image("image:1") == fixture
 with pytest.raises(LookupError): provider.identify_objects("image:1")

def test_provider_rejects_fixture_that_claims_real_analysis():
 fake=VisionObservation("image:1","DESCRIBE",("claim",),(),1.0,"REAL",False)
 with pytest.raises(ValueError): SyntheticVisionProvider({("image:1","DESCRIBE"):fake}).describe_image("image:1")
