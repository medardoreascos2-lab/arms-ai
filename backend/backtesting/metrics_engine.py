from dataclasses import dataclass, field


@dataclass
class BacktestMetrics:
    total_trades: int = 0
    winning_trades: int = 0
    losing_trades: int = 0

    net_profit: float = 0.0
    gross_profit: float = 0.0
    gross_loss: float = 0.0

    max_drawdown: float = 0.0

    trades: list = field(
        default_factory=list
    )

    @property
    def win_rate(self) -> float:
        if self.total_trades == 0:
            return 0.0

        return (
            self.winning_trades
            / self.total_trades
            * 100
        )

    @property
    def profit_factor(self) -> float:
        if self.gross_loss == 0:
            return 0.0

        return (
            self.gross_profit
            /
            abs(self.gross_loss)
        )


class MetricsEngine:

    def __init__(self):
        self.metrics = BacktestMetrics()


    def register_trade(
        self,
        profit_loss: float,
    ) -> None:

        self.metrics.total_trades += 1

        self.metrics.net_profit += profit_loss


        if profit_loss > 0:

            self.metrics.winning_trades += 1

            self.metrics.gross_profit += profit_loss

        else:

            self.metrics.losing_trades += 1

            self.metrics.gross_loss += profit_loss


        self.metrics.trades.append(
            profit_loss
        )


    def calculate_drawdown(self) -> None:

        equity = 0.0
        peak = 0.0
        drawdown = 0.0

        for trade in self.metrics.trades:

            equity += trade

            if equity > peak:
                peak = equity

            current_dd = peak - equity

            if current_dd > drawdown:
                drawdown = current_dd


        self.metrics.max_drawdown = drawdown


    def report(self):

        self.calculate_drawdown()

        return {
            "total_trades": self.metrics.total_trades,
            "win_rate": round(
                self.metrics.win_rate,
                2
            ),
            "profit_factor": round(
                self.metrics.profit_factor,
                2
            ),
            "net_profit": self.metrics.net_profit,
            "max_drawdown": self.metrics.max_drawdown,
        }
