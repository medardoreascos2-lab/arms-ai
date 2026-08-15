from dataclasses import dataclass


@dataclass
class ExecutionSimulation:

    status: str

    symbol: str

    direction: str

    entry: float

    stop_loss: float

    take_profit: float

    risk_points: float

    reward_points: float

    risk_reward: float

    contracts: int

    max_loss: float

    expected_profit: float



class ExecutionSimulatorEngine:


    def __init__(self):
        pass



    def simulate_execution(

        self,

        symbol: str,

        direction: str,

        entry: float,

        stop_loss: float,

        take_profit: float,

        point_value: float = 20,

        risk_amount: float = 500,

    ) -> ExecutionSimulation:


        risk_points = abs(
            entry - stop_loss
        )


        reward_points = abs(
            take_profit - entry
        )


        risk_reward = round(
            reward_points / risk_points,
            2
        )


        contracts = int(
            risk_amount /
            (risk_points * point_value)
        )


        if contracts < 1:

            contracts = 1



        max_loss = round(
            risk_points *
            point_value *
            contracts,
            2
        )


        expected_profit = round(
            reward_points *
            point_value *
            contracts,
            2
        )



        return ExecutionSimulation(

            status="SIMULATED",

            symbol=symbol,

            direction=direction,

            entry=entry,

            stop_loss=stop_loss,

            take_profit=take_profit,

            risk_points=risk_points,

            reward_points=reward_points,

            risk_reward=risk_reward,

            contracts=contracts,

            max_loss=max_loss,

            expected_profit=expected_profit,

        )
