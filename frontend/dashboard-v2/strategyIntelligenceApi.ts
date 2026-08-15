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

    const response = await fetch(
        "http://localhost:8000/api/v2/strategy/intelligence"
    );


    if (!response.ok) {

        throw new Error(
            "Failed to fetch strategy intelligence"
        );

    }


    return response.json();

}
