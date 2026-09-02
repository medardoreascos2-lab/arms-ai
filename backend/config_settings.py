from dataclasses import dataclass


@dataclass
class ArmsSettings:
    provider: str = "SIMULATED"
    symbol: str = "NASDAQ / NQ"
    timeframe: str = "1m"

    candle_limit: int = 100
    max_candles: int = 500

    account_balance: float = 17000.0
    risk_percent: float = 0.5
    internal_daily_loss_limit: float | None = None
    stop_atr_multiplier: float = 1.5
    reward_risk_ratio: float = 2.0
    instrument: str = "MNQ"
    point_value: float = 2.0

    ema_period: int = 50
    rsi_period: int = 14
    atr_period: int = 14
    atr_low_threshold: float = 2.0
    atr_high_threshold: float = 6.0

    liquidity_tolerance: float = 1.0

    trade_log_path: str = "data/trade_plans.jsonl"
    simulated_log_path: str = "data/simulated_trades.jsonl"
    runtime_snapshot_path: str = "data/runtime_state_v2.json"

    def __post_init__(self) -> None:
        self._validate()

    def _validate(self) -> None:
        if not self.provider.strip():
            raise ValueError(
                "provider no puede estar vacío."
            )

        if not self.symbol.strip():
            raise ValueError(
                "symbol no puede estar vacío."
            )

        if not self.timeframe.strip():
            raise ValueError(
                "timeframe no puede estar vacío."
            )

        if self.candle_limit <= 0:
            raise ValueError(
                "candle_limit debe ser mayor que cero."
            )

        if self.max_candles < self.candle_limit:
            raise ValueError(
                "max_candles debe ser mayor o igual "
                "que candle_limit."
            )

        if self.account_balance <= 0:
            raise ValueError(
                "account_balance debe ser mayor que cero."
            )

        if not 0 < self.risk_percent <= 100:
            raise ValueError(
                "risk_percent debe estar entre 0 y 100."
            )

        if (
            self.internal_daily_loss_limit is not None
            and self.internal_daily_loss_limit <= 0
        ):
            raise ValueError(
                "internal_daily_loss_limit debe ser "
                "mayor que cero."
            )

        if self.stop_atr_multiplier <= 0:
            raise ValueError(
                "stop_atr_multiplier debe ser mayor que cero."
            )

        if self.reward_risk_ratio <= 0:
            raise ValueError(
                "reward_risk_ratio debe ser mayor que cero."
            )

        if not self.instrument.strip():
            raise ValueError(
                "instrument no puede estar vacío."
            )

        self.instrument = self.instrument.upper()

        if self.ema_period <= 0:
            raise ValueError(
                "ema_period debe ser mayor que cero."
            )

        if self.rsi_period <= 0:
            raise ValueError(
                "rsi_period debe ser mayor que cero."
            )

        if self.atr_period <= 0:
            raise ValueError(
                "atr_period debe ser mayor que cero."
            )

        if self.atr_low_threshold < 0:
            raise ValueError(
                "atr_low_threshold no puede ser negativo."
            )

        if self.atr_high_threshold <= self.atr_low_threshold:
            raise ValueError(
                "atr_high_threshold debe ser mayor que "
                "atr_low_threshold."
            )

        minimum_required_candles = max(
            self.ema_period,
            self.rsi_period + 1,
            self.atr_period + 1,
        )

        if self.candle_limit < minimum_required_candles:
            raise ValueError(
                "candle_limit es insuficiente para "
                "los períodos configurados."
            )

        if self.liquidity_tolerance < 0:
            raise ValueError(
                "liquidity_tolerance no puede ser negativo."
            )

        if not self.trade_log_path.strip():
            raise ValueError(
                "trade_log_path no puede estar vacío."
            )

        if not self.simulated_log_path.strip():
            raise ValueError(
                "simulated_log_path no puede estar vacío."
            )

        if not self.runtime_snapshot_path.strip():
            raise ValueError(
                "runtime_snapshot_path no puede estar vacío."
            )
