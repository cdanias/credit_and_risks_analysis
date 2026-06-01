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
        Fetches the latest CLO news using Google News RSS.
        """
        import feedparser
        import urllib.parse

        # Base search query for CLO news
        search_query = "CLO issuance OR CLO pricing OR CLO market"
        if query:
            search_query = f"{query} ({search_query})"
        
        encoded_query = urllib.parse.quote(search_query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        
        feed = feedparser.parse(rss_url)
        live_news = []
        
        for entry in feed.entries[:limit * 2]: # Fetch extra to account for filtering
            item = {
                "title": entry.title,
                "date": entry.published,
                "summary": entry.summary if 'summary' in entry else entry.title,
                "source": entry.source.title if 'source' in entry else "Unknown",
                "link": entry.link
            }
            
            # Apply risk scoring
            report = self.analyzer.analyze_item(item["title"], item["summary"])
            item.update(report)
            live_news.append(item)
            
        return live_news[:limit]

if __name__ == "__main__":
    reader = CLONewsReader()
    news = reader.fetch_news(query="Ares")
    for item in news:
        print(f"[{item['date']}] {item['title']} - Source: {item['source']}")
