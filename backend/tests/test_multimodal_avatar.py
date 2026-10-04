import pytest
from backend.multimodal.avatar import AvatarAction,AvatarEmotionStyle,AvatarInstruction
def test_avatar_instruction_is_presentation_only():
 i=AvatarInstruction("i",AvatarAction.SPEAK,"transcript:1",emotion_display=AvatarEmotionStyle.WARM);assert i.presentation_only and not i.user_emotion_inferred and not i.execution_authorized
def test_avatar_cannot_claim_user_emotion_or_execution_authority():
 with pytest.raises(ValueError):AvatarInstruction("i",AvatarAction.IDLE,user_emotion_inferred=True)
 with pytest.raises(ValueError):AvatarInstruction("i",AvatarAction.IDLE,execution_authorized=True)
