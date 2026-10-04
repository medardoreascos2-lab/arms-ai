import pytest
from backend.multimodal.avatar_state import AvatarState,AvatarStateMachine
def test_avatar_state_machine_supports_listen_think_speak_idle_flow():
 m=AvatarStateMachine().transition(AvatarState.IDLE).transition(AvatarState.LISTENING).transition(AvatarState.THINKING).transition(AvatarState.SPEAKING).transition(AvatarState.IDLE);assert m.state==AvatarState.IDLE
def test_avatar_invalid_state_jump_is_rejected():
 with pytest.raises(ValueError):AvatarStateMachine().transition(AvatarState.SPEAKING)
