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
        if query:
            search_query = f"{query} (\"collateralized loan obligations\" OR \"collateralized debt obligations\" OR \"CLO market\") when:7d"
        else:
            search_query = "(\"collateralized loan obligations\" OR \"collateralized debt obligations\" OR \"CLO issuance\" OR \"CLO market\") when:7d"
        
        encoded_query = urllib.parse.quote(search_query)
        rss_url = f"https://news.google.com/rss/search?q={encoded_query}&hl=en-US&gl=US&ceid=US:en"
        
        feed = feedparser.parse(rss_url)
        live_news = []
        
        for entry in feed.entries[:limit * 2]: # Fetch extra to account for filtering
            import re
            import html
            source_name = entry.source.title if 'source' in entry else "Unknown"
            raw_summary = entry.summary if 'summary' in entry else entry.title
            
            # Clean HTML tags and unescape entities
            clean_summary = re.sub(r'<[^>]*>', '', raw_summary)
            clean_summary = html.unescape(clean_summary).strip()
            
            # Remove trailing source from summary if present
            if source_name != "Unknown" and clean_summary.endswith(source_name):
                clean_summary = clean_summary[:-len(source_name)].strip()
                
            # Fallback if empty or repeats title
            if not clean_summary or clean_summary.lower() == entry.title.lower():
                clean_summary = "Select this news event to run a credit risk audit."

            item = {
                "title": entry.title,
                "date": entry.published,
                "summary": clean_summary,
                "source": source_name,
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
