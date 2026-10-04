from backend.multimodal.session_isolation import (
    IsolatedSessionStore,
    MultimodalScope,
    ScopedArtifact,
    SessionChannel,
)


CHANNELS = (
    SessionChannel.VOICE,
    SessionChannel.CAMERA,
    SessionChannel.PRESENCE,
    SessionChannel.NOTIFICATIONS,
    SessionChannel.AVATAR,
    SessionChannel.MEMORY_REFERENCES,
)


def test_two_users_have_zero_cross_channel_multimodal_leakage():
    store = IsolatedSessionStore()
    alice = MultimodalScope("tenant-shared", "user-alice", "session-alice", "device-alice")
    bob = MultimodalScope("tenant-shared", "user-bob", "session-bob", "device-bob")

    for channel in CHANNELS:
        store.append(ScopedArtifact(
            f"alice-{channel.value}", alice, channel, f"private:alice:{channel.value}"
        ))
        store.append(ScopedArtifact(
            f"bob-{channel.value}", bob, channel, f"private:bob:{channel.value}"
        ))

    for channel in CHANNELS:
        alice_items = store.read(alice, channel)
        bob_items = store.read(bob, channel)
        assert tuple(item.content_reference for item in alice_items) == (
            f"private:alice:{channel.value}",
        )
        assert tuple(item.content_reference for item in bob_items) == (
            f"private:bob:{channel.value}",
        )
        assert all("bob" not in item.content_reference for item in alice_items)
        assert all("alice" not in item.content_reference for item in bob_items)

    crossed = (
        MultimodalScope(alice.tenant_id, bob.user_id, alice.session_id, alice.device_id),
        MultimodalScope(alice.tenant_id, alice.user_id, bob.session_id, alice.device_id),
        MultimodalScope(alice.tenant_id, alice.user_id, alice.session_id, bob.device_id),
    )
    assert all(store.read(scope, channel) == () for scope in crossed for channel in CHANNELS)