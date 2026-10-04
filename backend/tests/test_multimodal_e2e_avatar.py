import pytest

from backend.multimodal.avatar_state import AvatarState
from backend.multimodal.avatar_presentation import AvatarPresentationCoordinator
from backend.multimodal.lip_sync import LipSyncSequence, MouthCue, SyntheticLipSyncProvider


def fixture(duration=300, final_end=300):
    sequence = LipSyncSequence(
        "synthetic-audio:medar", duration,
        (MouthCue(0, 120, "A"), MouthCue(120, final_end, "REST")),
        "LOCAL_TEST_ONLY_SYNTHETIC_LIP_SYNC", True,
    )
    return SyntheticLipSyncProvider({"synthetic-audio:medar": sequence})


def test_synthetic_medar_response_tts_timing_speaking_cues_and_idle_return():
    result = AvatarPresentationCoordinator(fixture()).present(
        response_text="Synthetic MEDAR response.",
        transcript_reference="transcript:medar",
        audio_reference="synthetic-audio:medar",
    )
    assert result.states == (AvatarState.IDLE, AvatarState.SPEAKING, AvatarState.IDLE)
    assert result.final_state is AvatarState.IDLE
    assert result.lip_sync.duration_ms == 300
    assert [cue.viseme for cue in result.lip_sync.cues] == ["A", "REST"]
    assert result.instruction.presentation_only is True
    assert result.instruction.execution_authorized is False
    assert result.instruction.user_emotion_inferred is False


def test_invalid_lip_sync_timing_fails_without_presenting_authority():
    with pytest.raises(ValueError, match="exceeds audio duration"):
        AvatarPresentationCoordinator(fixture(duration=200, final_end=300)).present(
            response_text="Synthetic MEDAR response.",
            transcript_reference="transcript:medar",
            audio_reference="synthetic-audio:medar",
        )