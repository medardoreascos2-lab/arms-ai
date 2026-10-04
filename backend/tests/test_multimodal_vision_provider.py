from backend.multimodal.vision_provider import VisionObservation,VisionProvider

def test_vision_contract_exposes_provider_neutral_observation_operations():
 assert {"describe_image","extract_visible_text","identify_objects","analyze_document_page"} <= set(VisionProvider.__dict__)
 value=VisionObservation("image:1","DESCRIBE",("unknown",),(),None,"UNAVAILABLE",False,("No provider configured",))
 assert value.confidence is None and not value.synthetic
