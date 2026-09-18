import {
  getDashboardBundle, openDashboardWebSocket, runtimeKey, switchAccount,
  type JsonObject,
} from "./dashboardApi";

export type ConnectionStatus = "CONNECTING" | "CONNECTED" | "DISCONNECTED" | "ERROR";

/** Owns cancellation and publication, not account, financial or risk state. */
export class DashboardConnection {
  private epoch = 0;
  private request = 0;
  private socket: WebSocket | null = null;
  private timer: ReturnType<typeof setTimeout> | null = null;
  private poll: ReturnType<typeof setInterval> | null = null;
  private identity = "";
  constructor(private publish: (bundle: JsonObject | null) => void,
              private status: (status: ConnectionStatus) => void,
              private error: (message: string) => void) {}

  stop() {
    this.epoch++;
    this.request++;
    if (this.timer) clearTimeout(this.timer);
    if (this.poll) clearInterval(this.poll);
    this.timer = this.poll = null;
    const socket = this.socket;
    this.socket = null;
    socket?.close();
    this.identity = "";
    this.publish(null);
    this.status("DISCONNECTED");
  }

  start() {
    this.stop();
    const epoch = this.epoch;
    this.status("CONNECTING");
    this.error("");
    try {
      const socket = openDashboardWebSocket();
      this.socket = socket;
      socket.onmessage = (event) => {
        if (epoch !== this.epoch || socket !== this.socket) return;
        try {
          const message = JSON.parse(String(event.data));
          if (message.event_type === "dashboard_snapshot") {
            if (message.data.execution_mode !== "PAPER") throw new Error("Se requiere runtime PAPER.");
            const identity = runtimeKey(message.data.runtime);
            if (this.identity && identity !== this.identity) throw new Error("Runtime cambió.");
            this.identity = identity;
            this.status("CONNECTED");
            void this.refresh();
            if (!this.poll) this.poll = setInterval(() => void this.refresh(), 5000);
          } else if (message.event_type === "dashboard_updated") {
            // Re-read through a generation-checked bundle; never merge a partial
            // event into an account's financial projection.
            void this.refresh();
          }
        } catch {
          this.stop();
          this.status("ERROR");
          this.error("Snapshot PAPER inválido; vuelve a conectar.");
        }
      };
      socket.onerror = () => {
        if (epoch === this.epoch) this.status("ERROR");
      };
      socket.onclose = (event) => {
        if (epoch !== this.epoch) return;
        this.stop();
        if (event.code === 1008 || event.code === 1006) {
          this.error("Conexión rechazada o no disponible. Verifica la credencial y vuelve a conectar.");
        } else {
          this.timer = setTimeout(() => this.start(), 1000);
        }
      };
    } catch (error) {
      this.status("ERROR");
      this.error(error instanceof Error ? error.message : "Conexión no disponible.");
    }
  }

  async refresh() {
    if (!this.identity) return;
    const epoch = this.epoch, request = ++this.request;
    try {
      const bundle = await getDashboardBundle();
      if (epoch !== this.epoch || request !== this.request) return;
      if (runtimeKey(bundle.context as JsonObject) !== this.identity) {
        this.start();
        return;
      }
      this.publish(bundle);
      this.error("");
    } catch (error) {
      if (epoch !== this.epoch || request !== this.request) return;
      this.publish(null);
      this.error(error instanceof Error ? error.message : "Datos no disponibles.");
    }
  }

  async switch(profile: string, accountId: string) {
    this.stop();
    const epoch = this.epoch;
    try {
      await switchAccount(profile, accountId);
      if (epoch === this.epoch) this.start();
    } catch (error) {
      if (epoch !== this.epoch) return;
      this.error(error instanceof Error ? error.message : "Cambio rechazado.");
      this.status("ERROR");
    }
  }
}
