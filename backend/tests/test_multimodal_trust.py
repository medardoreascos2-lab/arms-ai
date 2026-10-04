from backend.multimodal.consent import ConsentState
from backend.multimodal.domain import Modality
from backend.multimodal.trust import EvidenceClass,MultimodalTrustProjection,TrustEvidence
def test_trust_layer_separates_observation_inference_and_synthetic_source():
 t=MultimodalTrustProjection("fixture:1",Modality.IMAGE,"synthetic-vision",1.0,ConsentState.GRANTED_SESSION,"NO_STORAGE",("LOCAL_TEST_ONLY",),("blue square fixture",),(),(TrustEvidence(EvidenceClass.SYNTHETIC,("fixture",)),TrustEvidence(EvidenceClass.OBSERVATION,("blue square fixture",))))
 assert t.what_was_observed and not t.what_was_inferred and {x.classification for x in t.evidence}=={EvidenceClass.SYNTHETIC,EvidenceClass.OBSERVATION}
