from typing import List, Dict, Optional
try:
    from risk_analyzer import RiskAnalyzer
except ImportError:
    from .risk_analyzer import RiskAnalyzer

class CLONewsReader:
    def __init__(self):
        self.analyzer = RiskAnalyzer()
        # Mock sources - in a real implementation, these would be RSS feeds or API endpoints
        self.sources = [
            "GlobalCapital",
            "Structured Credit Investor (SCI)",
            "Creditflux",
            "9fin"
        ]

    def fetch_news(self, query: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """
        Fetches the latest CLO news. Currently uses mock data for demonstration.
        """
    def fetch_news(self, query: Optional[str] = None, limit: int = 5) -> List[Dict]:
        """
        Fetches the latest CLO news and applies risk scoring.
        """
        # Simulated news database (Updated April 28, 2026)
        mock_news = [
            {
                "title": "Permira Credit Prices Providus CLO XV",
                "date": "2026-04-27",
                "summary": "Permira Credit priced its fifth CLO of the year, Providus CLO XV, a new issue vehicle valued at approximately €403 million.",
                "source": "GlobalCapital",
                "link": "https://www.globalcapital.com/structured-finance"
            },
            {
                "title": "CVC Credit Resets Cordatus Loan Fund 19",
                "date": "2026-04-26",
                "summary": "CVC Credit priced a €439.5 million reset of its Cordatus 19 vehicle, extending its reinvestment period by 4.5 years.",
                "source": "Structured Credit Investor",
                "link": "https://www.structuredcreditinvestor.com/"
            },
            {
                "title": "HPS Investment Partners Upsizes Aqueduct European CLO 17",
                "date": "2026-04-24",
                "summary": "Following strong investor demand, HPS has upsized its latest European new issue, Aqueduct 17.",
                "source": "9fin",
                "link": "https://9fin.com/"
            },
            {
                "title": "Ares Management Issuance Highlights Market Growth",
                "date": "2026-04-18",
                "summary": "Ares Management successfully issued its fourth private credit CLO in Europe, signaling market maturation.",
                "source": "GlobalCapital",
                "link": "https://www.globalcapital.com/article/ares-prices-fourth-european-private-credit-clo"
            },
            {
                "title": "Dual-Currency Structures Gaining Traction",
                "date": "2026-04-17",
                "summary": "Managers are adopting multi-currency CLO structures to manage cross-border complexities.",
                "source": "Structured Credit Investor",
                "link": "https://www.structuredcreditinvestor.com/"
            }
        ]

        # Apply risk scoring using the specialized analyzer
        for item in mock_news:
            report = self.analyzer.analyze_item(item["title"], item["summary"])
            item.update(report)

        # Filter by query if provided
        if query:
            filtered_news = [
                item for item in mock_news 
                if query.lower() in item["title"].lower() or query.lower() in item["summary"].lower()
            ]
        else:
            filtered_news = mock_news

        # Return limited results
        return filtered_news[:limit]

if __name__ == "__main__":
    reader = CLONewsReader()
    news = reader.fetch_news(query="Ares")
    for item in news:
        print(f"[{item['date']}] {item['title']} - Source: {item['source']}")
