from dataclasses import dataclass


@dataclass
class PerformanceResultV1:

    total_trades: int

    winning_trades: int

    losing_trades: int

    win_rate: float

    net_profit: float

    average_win: float

    average_loss: float

    expectancy: float

    profit_factor: float

    max_win_streak: int

    max_loss_streak: int



class PerformanceAnalyzerV1:
    """
    Analizador profesional ARMS AI.

    Evalúa resultados de trading.
    """


    def analyze(
        self,
        pnls,
    ) -> PerformanceResultV1:


        total = len(pnls)


        if total == 0:

            return PerformanceResultV1(
                0,0,0,0,0,0,0,0,0,0,0
            )


        wins = [
            p for p in pnls
            if p > 0
        ]


        losses = [
            p for p in pnls
            if p < 0
        ]


        winning = len(wins)

        losing = len(losses)


        win_rate = (
            winning / total
        ) * 100


        net = sum(pnls)


        avg_win = (
            sum(wins) / len(wins)
            if wins else 0
        )


        avg_loss = (
            sum(losses) / len(losses)
            if losses else 0
        )


        expectancy = (
            (win_rate / 100) * avg_win
            +
            ((100 - win_rate) / 100)
            * avg_loss
        )


        gross_profit = sum(wins)

        gross_loss = abs(
            sum(losses)
        )


        profit_factor = (
            gross_profit / gross_loss
            if gross_loss > 0
            else 0
        )


        win_streak = 0
        loss_streak = 0

        max_win = 0
        max_loss = 0


        for pnl in pnls:

            if pnl > 0:

                win_streak += 1
                loss_streak = 0

            elif pnl < 0:

                loss_streak += 1
                win_streak = 0


            max_win = max(
                max_win,
                win_streak,
            )

            max_loss = max(
                max_loss,
                loss_streak,
            )


        return PerformanceResultV1(

            total_trades=total,

            winning_trades=winning,

            losing_trades=losing,

            win_rate=win_rate,

            net_profit=net,

            average_win=avg_win,

            average_loss=avg_loss,

            expectancy=expectancy,

            profit_factor=profit_factor,

            max_win_streak=max_win,

            max_loss_streak=max_loss,

        )
