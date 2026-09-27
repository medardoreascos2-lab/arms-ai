from pathlib import Path


SOURCE = Path(
    "integrations/ninjatrader/"
    "ArmsSimNativeSubmitBridgeV2.cs"
)


def source():
    return SOURCE.read_text(
        encoding="utf-8"
    )


def submit_flow(text):
    start = text.index(
        "private void AttemptOneShotSubmit()"
    )

    end = text.index(
        "private void ReadActivationEvidence(",
        start,
    )

    return text[start:end]


def activation_reader(text):
    start = text.index(
        "private void ReadActivationEvidence("
    )

    end = text.index(
        "private SubmitCommandEvidence ReadSubmitCommand(",
        start,
    )

    return text[start:end]


def test_submit_activation_has_consumed_marker_contract():
    text = source()

    assert ".arm.json.consumed" in text


def test_activation_reader_rejects_consumed_marker():
    text = source()
    reader = activation_reader(text)

    assert "File.Exists(consumedPath)" in reader

    assert (
        "Submit activation evidence was already consumed."
        in reader
    )


def test_submit_activation_has_explicit_consume_method():
    text = source()

    assert (
        "private void ConsumeSubmitActivation()"
        in text
    )


def test_consume_uses_create_new():
    text = source()

    start = text.index(
        "private void ConsumeSubmitActivation()"
    )

    end = text.index(
        "private ",
        start + 10,
    )

    method = text[start:end]

    assert "FileMode.CreateNew" in method
    assert "FileAccess.Write" in method
    assert "FileShare.None" in method


def test_consumed_marker_is_fsynced():
    text = source()

    start = text.index(
        "private void ConsumeSubmitActivation()"
    )

    end = text.index(
        "private ",
        start + 10,
    )

    method = text[start:end]

    assert "Flush(true)" in method


def test_submit_activation_is_consumed_only_after_hard_enable_gate():
    text = source()
    flow = submit_flow(text)

    hard_gate = flow.index(
        "if (!NATIVE_SUBMIT_ENABLED)"
    )

    consume = flow.index(
        "ConsumeSubmitActivation();"
    )

    create_order = flow.index(
        "selectedAccount.CreateOrder("
    )

    assert hard_gate < consume
    assert consume < create_order


def test_consumption_occurs_before_any_native_submit():
    text = source()
    flow = submit_flow(text)

    consume = flow.index(
        "ConsumeSubmitActivation();"
    )

    create_order = flow.index(
        "selectedAccount.CreateOrder("
    )

    submit = flow.index(
        "selectedAccount.Submit("
    )

    assert consume < create_order
    assert consume < submit


def test_native_submit_remains_hard_disabled():
    text = source()

    assert (
        "private const bool NATIVE_SUBMIT_ENABLED = false;"
        in text
    )
