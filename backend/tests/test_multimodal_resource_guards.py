import pytest

from backend.multimodal.resource_guards import (
    MultimodalResourceGuard,
    ResourceCode,
    ResourceLimits,
    ResourceRequest,
)


def limits(**changes):
    values = dict(
        max_audio_duration_seconds=10,
        max_image_size_bytes=100,
        max_camera_frames_per_second=2,
        max_concurrent_jobs=1,
        max_memory_bytes_per_job=1000,
        max_queue_depth=1,
    )
    values.update(changes)
    return ResourceLimits(**values)


@pytest.mark.parametrize(
    ("resource_request", "code"),
    [
        (ResourceRequest(audio_duration_seconds=11), ResourceCode.AUDIO_DURATION_LIMIT),
        (ResourceRequest(image_size_bytes=101), ResourceCode.IMAGE_SIZE_LIMIT),
        (ResourceRequest(camera_frames_per_second=3), ResourceCode.CAMERA_FRAME_RATE_LIMIT),
        (ResourceRequest(estimated_memory_bytes=1001), ResourceCode.MEMORY_LIMIT),
    ],
)
def test_invalid_resource_demands_fail_closed_without_admission(resource_request, code):
    guard = MultimodalResourceGuard(limits())
    decision = guard.try_acquire(resource_request)
    assert decision.allowed is False
    assert decision.code is code
    assert guard.active_jobs == 0
    assert guard.queued_jobs == 0


def test_concurrency_and_queue_depth_are_never_silently_exceeded():
    guard = MultimodalResourceGuard(limits())
    request = ResourceRequest(audio_duration_seconds=1, image_size_bytes=10,
                              camera_frames_per_second=1, estimated_memory_bytes=50)
    assert guard.try_acquire(request).allowed is True
    assert guard.try_acquire(request).code is ResourceCode.QUEUED
    assert guard.try_acquire(request).code is ResourceCode.QUEUE_LIMIT
    assert (guard.active_jobs, guard.queued_jobs) == (1, 1)
    guard.release()
    guard.discard_queued()
    assert (guard.active_jobs, guard.queued_jobs) == (0, 0)


def test_invalid_limit_configuration_and_counter_underflow_fail_fast():
    with pytest.raises(ValueError):
        limits(max_concurrent_jobs=0)
    guard = MultimodalResourceGuard(limits())
    with pytest.raises(RuntimeError):
        guard.release()
    with pytest.raises(RuntimeError):
        guard.discard_queued()