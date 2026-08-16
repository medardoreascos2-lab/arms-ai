from dataclasses import dataclass


@dataclass
class AccountProfile:

    name: str

    account_balance: float

    daily_loss_limit: float

    max_drawdown: float

    risk_percent: float



class AccountProfileFactory:


    @staticmethod
    def topstep_50k():

        return AccountProfile(
            name="TOPSTEP_50K",
            account_balance=50000,
            daily_loss_limit=1000,
            max_drawdown=2000,
            risk_percent=0.5,
        )



    @staticmethod
    def topstep_150k():

        return AccountProfile(
            name="TOPSTEP_150K",
            account_balance=150000,
            daily_loss_limit=3000,
            max_drawdown=4500,
            risk_percent=0.5,
        )



    @staticmethod
    def personal(
        balance: float,
        risk: float = 0.5,
    ):

        return AccountProfile(
            name="PERSONAL",
            account_balance=balance,
            daily_loss_limit=balance * 0.03,
            max_drawdown=balance * 0.05,
            risk_percent=risk,
        )
