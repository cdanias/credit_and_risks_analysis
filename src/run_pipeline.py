import sys
import os
import json

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.news_reader.reader import CLONewsReader
from src.agents.analyst.analyst import CLOAnalyst
from src.agents.critic.critic import CLOCritic

def run_pipeline(query=None, limit=3):
    print("🚀 Initializing CLO Intelligence Pipeline...")
    
    portfolio_path = "/Users/christos/Downloads/european_clo_bonds.xlsx"
    reader = CLONewsReader()
    analyst = CLOAnalyst(portfolio_path=portfolio_path)
    critic = CLOCritic()
    
    # 1. READ
    print(f"📡 Fetching live news for: {query if query else 'Latest Market'}")
    news = reader.fetch_news(query=query, limit=limit)
    
    for i, item in enumerate(news):
        print(f"\n--- PROCESSING ARTICLE {i+1}: {item['title']} ---")
        
        # 2. ANALYZE
        analysis = analyst.analyze_news_item(item)
        print(f"📊 Analyst Recommendation: {analysis['recommendation']}")
        
        # 3. CRITIQUE
        critique = critic.analyze_assessment(analysis)
        print(f"⚖️ Critic Score: {critique['score']}/10")
        print(f"🔍 Critical Gap: {critique['challenges'][0]['problem'] if critique['challenges'] else 'None'}")
        
        # 4. FINAL OUTPUT (SIMULATED)
        print(f"\n✅ FINAL ASSESSMENT FOR {item['title'][:50]}...")
        print(f"   Recommendation: {analysis['recommendation']}")
        print(f"   Structural Insight: {analysis['structural_insights']}")
        print(f"   Critic's Alternative View: {critique['alternative_view']}")

if __name__ == "__main__":
    run_pipeline()
