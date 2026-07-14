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
    stop_atr_multiplier: float = 1.5
    reward_risk_ratio: float = 2.0
    point_value: float = 2.0

    ema_period: int = 50
    rsi_period: int = 14
    atr_period: int = 14

    liquidity_tolerance: float = 1.0

    trade_log_path: str = "data/trade_plans.jsonl"
    simulated_log_path: str = "data/simulated_trades.jsonl"

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

        if self.stop_atr_multiplier <= 0:
            raise ValueError(
                "stop_atr_multiplier debe ser mayor que cero."
            )

        if self.reward_risk_ratio <= 0:
            raise ValueError(
                "reward_risk_ratio debe ser mayor que cero."
            )

        if self.point_value <= 0:
            raise ValueError(
                "point_value debe ser mayor que cero."
            )

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
