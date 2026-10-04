from backend.multimodal.creative import CreativeCapability,CreativeRequest,CreativeResult
def test_creative_seams_cover_requested_capabilities_without_output_claim():
 assert {x.value for x in CreativeCapability}=={"IMAGE_GENERATION","VIDEO_GENERATION","IMAGE_TO_VIDEO","STORYBOARD","AVATAR_ANIMATION"}
 r=CreativeResult("r");assert r.status=="INTEGRATION_PENDING" and r.output_reference is None and r.provider is None and not r.external_purchase_authorized
