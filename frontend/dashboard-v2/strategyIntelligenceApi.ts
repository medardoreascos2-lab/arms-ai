import { requestJson } from "../src/lib/dashboardApi";

export interface StrategyIntelligence {

    strategy: string;

    final_decision: string;

    confidence: string;

    reason: string[];

    scores: {
        backtest: number;
        learning: number;
        final: number;
    };

    market: {
        regime: string;
        volatility: string;
        compatibility: string;
    };

    history: {
        trades: number;
        win_rate: number;
    };
}



export async function getStrategyIntelligence()
: Promise<StrategyIntelligence> {

    return requestJson("/api/v2/strategy/intelligence") as unknown as Promise<StrategyIntelligence>;
}
