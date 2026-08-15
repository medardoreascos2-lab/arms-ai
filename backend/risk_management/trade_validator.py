class TradeValidator:
    def __init__(self):
        self.is_valid = False
        self.reasons: list[str] = []

    def validate(
        self,
        decision: str,
        confidence: str,
        contracts: int,
        rsi_status: str,
        atr_status: str,
        confluence_score: float = 0.0,
        bos_confirmed: bool = False,
        liquidity_confirmed: bool = False,
    ) -> bool:
        self.is_valid = True
        self.reasons = []

        if decision == "ESPERAR":
            self.is_valid = False
            self.reasons.append(
                "La decisión final es ESPERAR."
            )

        if confidence == "BAJA":
            self.is_valid = False
            self.reasons.append(
                "La confianza del análisis es baja."
            )

        if contracts < 1:
            self.is_valid = False
            self.reasons.append(
                "El riesgo disponible no permite abrir contratos."
            )

        if (
            decision == "BUSCAR COMPRAS"
            and rsi_status == "SOBRECOMPRA"
        ):
            strong_setup = (
                bos_confirmed
                and liquidity_confirmed
                and confluence_score >= 80
            )

            if not strong_setup:
                self.is_valid = False
                self.reasons.append(
                    "Compra bloqueada porque el RSI está en sobrecompra."
                )
            else:
                self.reasons.append(
                    "RSI alto permitido por setup A+ confirmado."
                )

        if (
            decision == "BUSCAR VENTAS"
            and rsi_status == "SOBREVENTA"
        ):
            strong_setup = (
                bos_confirmed
                and liquidity_confirmed
                and confluence_score >= 80
            )

            if not strong_setup:
                self.is_valid = False
                self.reasons.append(
                    "Venta bloqueada porque el RSI está en sobreventa."
                )
            else:
                self.reasons.append(
                    "RSI bajo permitido por setup A+ confirmado."
                )

        if atr_status == "VOLATILIDAD BAJA":
            self.is_valid = False
            self.reasons.append(
                "La volatilidad es demasiado baja."
            )

        return self.is_valid

    def show(self) -> None:
        print("------ TRADE VALIDATOR ------")
        print(
            f"Operación autorizada: "
            f"{'SÍ' if self.is_valid else 'NO'}"
        )

        if not self.reasons:
            print("La operación cumple todas las reglas.")
            return

        print("Motivos:")
        for reason in self.reasons:
            print(f"- {reason}")