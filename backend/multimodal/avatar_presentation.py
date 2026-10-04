"""Synthetic presentation coordinator for MEDAR text, TTS timing, and avatar state."""

from __future__ import annotations

from dataclasses import dataclass

from .avatar import AvatarAction, AvatarInstruction
from .avatar_state import AvatarState, AvatarStateMachine
from .lip_sync import LipSyncProvider, LipSyncSequence


@dataclass(frozen=True)
class AvatarPresentationResult:
    instruction: AvatarInstruction
    lip_sync: LipSyncSequence
    states: tuple[AvatarState, ...]
    final_state: AvatarState


class AvatarPresentationCoordinator:
    def __init__(self, lip_sync: LipSyncProvider) -> None:
        self._lip_sync = lip_sync

    def present(self, *, response_text: str, transcript_reference: str,
                audio_reference: str) -> AvatarPresentationResult:
        if not response_text.strip() or not transcript_reference or not audio_reference:
            raise ValueError("MEDAR response, transcript, and audio references required")
        machine = AvatarStateMachine().transition(AvatarState.IDLE)
        instruction = AvatarInstruction(
            instruction_id=f"avatar:{transcript_reference}",
            action=AvatarAction.SPEAK,
            transcript_reference=transcript_reference,
            audio_reference=audio_reference,
        )
        machine = machine.transition(AvatarState.SPEAKING)
        sequence = self._lip_sync.mouth_cue_sequence(audio_reference)
        if sequence.audio_reference != audio_reference:
            raise ValueError("lip-sync audio reference mismatch")
        if any(cue.end_ms > sequence.duration_ms for cue in sequence.cues):
            raise ValueError("lip-sync cue exceeds audio duration")
        machine = machine.transition(AvatarState.IDLE)
        return AvatarPresentationResult(
            instruction=instruction,
            lip_sync=sequence,
            states=(AvatarState.IDLE, AvatarState.SPEAKING, AvatarState.IDLE),
            final_state=machine.state,
        )