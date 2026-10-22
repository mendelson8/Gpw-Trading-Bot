"""
News sentiment analysis for GPW trading signals.

Each article is scored from -5 (strong sell) to +5 (strong buy).
The model also extracts the primary GPW ticker when a single company is the main subject.
Returns structured JSON so downstream code can act on results without further parsing.
"""

import json
from google import genai
import config


class SentimentAnalyzer:
    """Analyze market sentiment from news text."""

    def __init__(self):
        self.client = None
        self.total_cost = 0
        self.total_tokens = 0
        self._init_vertex_ai()

    def _init_vertex_ai(self):
        """Initialize the model client."""
        try:
            if config.VERTEX_AI_API_KEY:
                self.client = genai.Client(vertexai=True, api_key=config.VERTEX_AI_API_KEY)
                if config.VERBOSE_LOGGING:
                    print(f"[OK] Model client initialized")
            else:
                print("[ERROR] Missing API key in .env")
        except Exception as e:
            print(f"[ERROR] Failed to initialize model client: {e}")

    def analyze(self, title, description):
        """
        Analyze sentiment for a news item.

        Returns:
            tuple: (sentiment, score, ticker, justification)
        """
        if not self.client:
            return 'NEUTRAL', 0, None, "Model client unavailable"

        try:
            prompt = f'''ROLE: Expert Algorithmic Trader for GPW (Warsaw Stock Exchange).
OBJECTIVE: Analyze news for IMMEDIATE market reaction (0-48h holding period). Focus on volatility spikes.

INPUT DATA:
Title: {title}
Description: {description}

INSTRUCTIONS:

1. TICKER EXTRACTION
Target: Identify the single company directly affected by the news.
Rules:
- RETURN NULL if news is: Macro (inflation, rates, politics), Market Summary (WIG20, "Banki rosną"), Commodities/FX (Gold, USDPLN).
- RETURN NULL if company is just mentioned in a list (e.g., "Leaders: PKO, XTB").
- RETURN TICKER (e.g., CDR, PKO, XTB) ONLY if the company is the MAIN SUBJECT (>80% focus).

2. SCORING (-5 to +5)
Assess the probability of an immediate price jump/drop.

POSITIVE (BUY SIGNAL):
+5 (GAME CHANGER - "MUST BUY NOW"):
   - Event that fundamentally changes the company's future.
   - HUGE SURPRISE: Something the market did not expect at all.
   - Examples: Tender offer at premium (Wezwanie), Huge strategic M&A (Przejęcie), Discovery of major resources, Patent approval (Biotech), Signing a contract that doubles the backlog.

+4 (HIGH MOMENTUM / HYPE):
   - News that triggers "Fear Of Missing Out" (FOMO).
   - "RECORD" results: Using words like "Historyczny zysk", "Rekordowe przychody".
   - HIGH YIELD: Dividend proposal significantly higher than market average.
   - ANALYST UPGRADE: "Buy" recommendation with Target Price >20% above current price.
   - SECTOR HYPE: Company entering a hot trend (e.g., AI, Defense, Energy transition) with a concrete deal.

+3 (SOLID CATALYST):
   - Beat and Raise: Good results + Raised guidance for next year.
   - Buyback announcement.
   - Winning a public tender (Przetarg) important for the specific company scale.
+2 (Mild Positive):
   - Neutral-positive news, sustainment of good trends.
+1 (Noise):
   - PR fluff, events without financial impact.

NEGATIVE (SELL SIGNAL):
-5 (Crash / Panic):
   - Insolvency, Bankruptcy protection, Fraud.
   - Auditor refuses to sign report (Odmowa opinii).
   - KNF suspends trading or huge penalty.
-4 (Strong Sell / Dilution):
   - Share dilution (Emisja akcji bez prawa poboru).
   - ABB (Accelerated Book Building) at discount.
   - Results CLEARLY below consensus/expectations.
   - Loss of a key strategic client.
-3 (Sell):
   - Profit warning / Guidance downgrade.
   - Significant Asset Write-offs (Odpisy aktualizujące).
   - Unexpected resignation of CEO/CFO.
-2 (Mild Negative):
   - Weak data but priced in.
-1 (Noise):
   - Minor issues.

3. OUTPUT FORMAT
Return one raw JSON object with no markdown. Use a score from -5 to +5.
The sentiment must be POSITIVE, NEGATIVE, or NEUTRAL. The ticker must be a string or null.
{{
  "ticker": null,
  "sentiment": "NEUTRAL",
  "score": 0,
  "justification": "No company-specific catalyst."
}}'''

            response = self.client.models.generate_content(
                model=config.VERTEX_AI_MODEL,
                contents=prompt,
                config={
                    "response_mime_type": "application/json",
                    "temperature": 0.3
                }
            )

            response_text = response.text

            if hasattr(response, 'usage_metadata'):
                input_tokens = response.usage_metadata.prompt_token_count
                output_tokens = response.usage_metadata.candidates_token_count

                if 'flash' in config.VERTEX_AI_MODEL.lower():
                    input_price_per_1m = 0.075
                    output_price_per_1m = 0.30
                elif 'pro' in config.VERTEX_AI_MODEL.lower():
                    input_price_per_1m = 1.25
                    output_price_per_1m = 5.00
                else:
                    input_price_per_1m = 0.075
                    output_price_per_1m = 0.30

                cost = (input_tokens * input_price_per_1m + output_tokens * output_price_per_1m) / 1_000_000

                self.total_cost += cost
                self.total_tokens += input_tokens + output_tokens

                if config.VERBOSE_LOGGING:
                    print(f"  [AI] Tokens: {input_tokens} in + {output_tokens} out = {input_tokens + output_tokens}")
                    print(f"  [AI] Cost: ${cost:.6f} | Total: ${self.total_cost:.4f} ({self.total_tokens} tokens)")
                    print(f"  [AI] Model: {config.VERTEX_AI_MODEL}")

            result = json.loads(response_text)

            sentiment = result.get('sentiment', 'NEUTRAL')
            score = float(result.get('score', 0))
            ticker = result.get('ticker')
            justification = result.get('justification', '')

            if sentiment not in {'POSITIVE', 'NEGATIVE', 'NEUTRAL'}:
                raise ValueError(f"Unexpected sentiment: {sentiment}")
            if not -5 <= score <= 5:
                raise ValueError(f"Sentiment score out of range: {score}")

            return sentiment, score, ticker, justification

        except Exception as e:
            print(f"[ERROR] Sentiment analysis failed: {e}")
            return 'NEUTRAL', 0, None, None

    def analyze_news(self, title, description, link=""):
        """Analyze an article and return a result dictionary, or None for neutral items without a ticker."""
        sentiment, score, ticker, justification = self.analyze(title, description)

        if sentiment == 'NEUTRAL' and score == 0 and not ticker:
            return None

        return {
            'sentiment': sentiment,
            'score': score,
            'ticker': ticker,
            'justification': justification,
            'link': link
        }
