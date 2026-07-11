class RiskManager:
    def __init__(self, account_balance=10000, risk_percent=0.5):
        self.account_balance = account_balance
        self.risk_percent = risk_percent

    def calculate_risk_amount(self):
        return self.account_balance * (self.risk_percent / 100)

    def show_risk(self):
        risk_amount = self.calculate_risk_amount()
        print(f"Capital de cuenta: ${self.account_balance}")
        print(f"Riesgo por operación: {self.risk_percent}%")
        print(f"Monto máximo a arriesgar: ${risk_amount}")