import pytest

from backend.api.app import create_app
from backend.execution.execution_decision_engine_v2 import (
    ExecutionDecisionEngineV2,
)
from backend.intelligence.confluence_engine_v2 import (
    ConfluenceEngineV2,
)
from backend.intelligence.probability_engine_v2 import (
    ProbabilityEngineV2,
)
from backend.market_analysis.market_regime_engine import (
    MarketRegimeEngine,
)
from backend.smart_money.smart_money_engine_v2 import (
    SmartMoneyEngineV2,
)


def test_create_app_builds_default_v2_engines():
    app = create_app()

    assert isinstance(
        app.state.smart_money_engine_v2,
        SmartMoneyEngineV2,
    )

    assert isinstance(
        app.state.market_regime_engine,
        MarketRegimeEngine,
    )

    assert isinstance(
        app.state.confluence_engine_v2,
        ConfluenceEngineV2,
    )

    assert isinstance(
        app.state.probability_engine_v2,
        ProbabilityEngineV2,
    )

    assert isinstance(
        app.state.execution_decision_engine_v2,
        ExecutionDecisionEngineV2,
    )


def test_default_probability_v2_configuration():
    app = create_app()

    engine = (
        app.state.probability_engine_v2
    )

    assert (
        engine.minimum_approval_probability
        == 0.80
    )

    assert engine.very_high_threshold == 0.90
    assert engine.high_threshold == 0.80
    assert engine.medium_threshold == 0.65


def test_default_execution_v2_configuration():
    app = create_app()

    engine = (
        app.state.execution_decision_engine_v2
    )

    assert engine.minimum_probability == 0.80

    assert (
        engine.minimum_confluence_score
        == 0.80
    )


def test_create_app_accepts_custom_v2_engines():
    smart_money_engine = SmartMoneyEngineV2()

    market_regime_engine = MarketRegimeEngine(
        trend_threshold=0.70,
        high_volatility_threshold=0.90,
        low_volatility_threshold=0.10,
        compression_threshold=0.20,
    )

    confluence_engine = ConfluenceEngineV2()

    probability_engine = ProbabilityEngineV2(
        minimum_approval_probability=0.85,
        very_high_threshold=0.95,
        high_threshold=0.85,
        medium_threshold=0.70,
    )

    execution_engine = ExecutionDecisionEngineV2(
        minimum_probability=0.85,
        minimum_confluence_score=0.85,
    )

    app = create_app(
        smart_money_engine_v2=(
            smart_money_engine
        ),
        market_regime_engine=(
            market_regime_engine
        ),
        confluence_engine_v2=(
            confluence_engine
        ),
        probability_engine_v2=(
            probability_engine
        ),
        execution_decision_engine_v2=(
            execution_engine
        ),
    )

    assert (
        app.state.smart_money_engine_v2
        is smart_money_engine
    )

    assert (
        app.state.market_regime_engine
        is market_regime_engine
    )

    assert (
        app.state.confluence_engine_v2
        is confluence_engine
    )

    assert (
        app.state.probability_engine_v2
        is probability_engine
    )

    assert (
        app.state.execution_decision_engine_v2
        is execution_engine
    )


@pytest.mark.parametrize(
    "argument_name",
    [
        "smart_money_engine_v2",
        "market_regime_engine",
        "confluence_engine_v2",
        "probability_engine_v2",
        "execution_decision_engine_v2",
    ],
)
def test_create_app_rejects_invalid_v2_engine(
    argument_name: str,
):
    arguments = {
        argument_name: object(),
    }

    with pytest.raises(
        TypeError,
        match=argument_name,
    ):
        create_app(
            **arguments
        )
