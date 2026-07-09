class ArmsCore:
    def __init__(self):
        self.name = "ARMS AI"
        self.version = "0.0.1"
        self.status = "ONLINE"

    def start(self):
        print(f"{self.name} v{self.version}")
        print(f"Estado del sistema: {self.status}")
        print("ARMS Core iniciado correctamente.")