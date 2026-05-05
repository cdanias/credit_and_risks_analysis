from typing import Dict

class RiskAnalyzer:
    def __init__(self):
        self.risk_keywords = {
            "volatile": 20,
            "sell-off": 40,
            "downgrade": 50,
            "widening": 15,
            "distressed": 45,
            "default": 60,
            "unease": 10,
            "recession": 30,
            "liquidity": 25
        }

    def analyze_item(self, title: str, summary: str) -> Dict:
        """
        Analyzes a news item and returns a risk report.
        """
        score = 0
        text = (title + " " + summary).lower()
        matched_keywords = []
        
        for kw, val in self.risk_keywords.items():
            if kw in text:
                score += val
                matched_keywords.append(kw)
        
        score = min(score, 100)
        
        recommendation = "HOLD"
        if score > 60:
            recommendation = "SELL / REDUCE"
        elif score > 30:
            recommendation = "MONITOR CLOSELY"
            
        return {
            "risk_score": score,
            "recommendation": recommendation,
            "signals": matched_keywords
        }
