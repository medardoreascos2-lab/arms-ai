const API_URL = "http://127.0.0.1:8000";

export async function analyzePortfolio(payload: unknown) {
  const response = await fetch(
    `${API_URL}/portfolio/analyze`,
    {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    }
  );

  if (!response.ok) {
    throw new Error("API Error");
  }

  return response.json();
}