import inspect,pytest
from backend.multimodal.observable_context import ObservableContext,ObservableCue,ObservationValue
def test_context_accepts_only_conservative_observable_cues():
 c=ObservableContext({ObservableCue.SITTING:ObservationValue.TRUE,ObservableCue.EYES_APPARENTLY_CLOSED:ObservationValue.UNKNOWN},1,"fixture:1",True,("No diagnosis.",));assert c.observations[ObservableCue.SITTING]==ObservationValue.TRUE
def test_sensitive_traits_and_diagnoses_are_not_in_schema():
 source=inspect.getsource(ObservableContext).lower()
 for forbidden in ("mental_illness","intoxication","political","religion","sexual_orientation","diagnosis"):assert forbidden not in source
 with pytest.raises(TypeError):ObservableContext({},1,"x",True,(),medical_diagnosis="x")
