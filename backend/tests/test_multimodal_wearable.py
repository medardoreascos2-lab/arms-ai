import pytest
from backend.multimodal.wearable import WearableDataStatus,WearableMetric,WearableObservation
def test_unknown_wearable_data_remains_unknown_without_value():
 o=WearableObservation("t","u",WearableMetric.HEART_RATE,None,None,None,WearableDataStatus.UNKNOWN,None);assert o.value is None and not o.diagnosis_provided
def test_missing_data_and_diagnosis_cannot_be_inferred():
 with pytest.raises(ValueError):WearableObservation("t","u",WearableMetric.SLEEP,8,"hours",None,WearableDataStatus.UNKNOWN,None)
 with pytest.raises(ValueError):WearableObservation("t","u",WearableMetric.HEART_RATE,80,"bpm",None,WearableDataStatus.USER_REPORTED,"user",True)
