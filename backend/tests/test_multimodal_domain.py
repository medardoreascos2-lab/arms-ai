from backend.multimodal.domain import Modality, ModalityAuthority


def test_canonical_modalities_are_fixed():
    assert {item.value for item in Modality} == {
        "TEXT", "AUDIO_INPUT", "AUDIO_OUTPUT", "IMAGE", "DOCUMENT",
        "CAMERA_FRAME", "VIDEO_CLIP", "AVATAR_OUTPUT", "NOTIFICATION",
    }


def test_multimodal_interfaces_have_zero_independent_authority():
    authority = ModalityAuthority()
    assert not any((
        authority.broker, authority.paper, authority.live,
        authority.portfolio_mutation, authority.payments,
        authority.external_delivery, authority.device_control,
    ))
