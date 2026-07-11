class MarketConnector:
    def __init__(self):
        self.provider = "SIMULATED"
        self.connected = False

    def connect(self):
        self.connected = True
        print(f"Conectando a {self.provider}...")
        print("Conexión establecida correctamente.")
        return self.connected