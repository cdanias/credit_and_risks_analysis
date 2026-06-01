import os
import sys
import json

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.news_reader.reader import CLONewsReader
from src.agents.analyst.analyst import CLOAnalyst
from src.agents.critic.critic import CLOCritic

def run_buy_sell_pipeline(query=None, limit=3):
    print("🚀 Starting CLO Buy/Sell Recommendation Pipeline...")
    
    # 1. Look in My Drive for the 'CLO portfolio example sheet'
    gsheet_path = "/Users/christos/Library/CloudStorage/GoogleDrive-cdanias@gmail.com/My Drive/CLO portfolio example sheet.gsheet"
    fallback_xlsx_path = "/Users/christos/Downloads/european_clo_bonds.xlsx"
    
    print(f"📂 Searching for Google Drive portfolio sheet...")
    if os.path.exists(gsheet_path):
        print(f"✅ Located Google Sheet pointer: {gsheet_path}")
        print(f"ℹ️ Google Drive .gsheet files are cloud pointers. Resolving to Excel export database: {fallback_xlsx_path}")
        portfolio_path = fallback_xlsx_path
    else:
        print(f"⚠️ Google Sheet pointer not found at: {gsheet_path}")
        print(f"ℹ️ Falling back directly to local Excel database: {fallback_xlsx_path}")
        portfolio_path = fallback_xlsx_path
        
    if not os.path.exists(portfolio_path):
        print(f"❌ Error: Portfolio database file not found at {portfolio_path}!")
        return
        
    # Initialize agents
    reader = CLONewsReader()
    analyst = CLOAnalyst(portfolio_path=portfolio_path)
    critic = CLOCritic()
    
    print(f"📊 Loaded {len(analyst.portfolio)} portfolio holdings from database.")
    for holding in analyst.portfolio:
        print(f"   - Holding: {holding['deal']} (Manager: {holding['manager']}, Rating: {holding['rating']}, Balance: €{holding['balance']}m)")
        
    # 2. Fetch live news
    print(f"\n📡 Fetching CLO news signals...")
    news = reader.fetch_news(query=query, limit=limit)
    
    recommendations_list = []
    
    # 3. Process each news signal
    for i, item in enumerate(news):
        print(f"\n──────────────────────────────────────────────────")
        print(f"📰 Processing Signal {i+1}: {item['title']}")
        print(f"──────────────────────────────────────────────────")
        
        # Step 2: Analyst First Pass
        print("🧑‍💻 [Analyst] Running first pass analysis...")
        analysis = analyst.analyze_news_item(item)
        print(f"   Initial Rec: {analysis['recommendation']} (Conviction: {analysis['conviction_pct']}%)")
        
        # Step 3: Critic Double-Loop Refinement (Loop happens twice)
        for loop in range(1, 3):
            print(f"⚖️ [Critic] Loop {loop}/2: Auditing analyst's assessment...")
            critique = critic.analyze_assessment(analysis)
            print(f"   Critic Score: {critique['score']}/10 (Decision: {critique['decision']})")
            
            print("🧑‍💻 [Analyst] Refining analysis based on critic feedback...")
            analysis = analyst.refine_analysis(analysis, critique)
            print(f"   Refined Rec: {analysis['recommendation']} (Conviction: {analysis['conviction_pct']}%)")
            
        recommendations_list.append(analysis)
        
    # 4. Final Output Recommendation Report
    print("\n" + "═" * 50)
    print("      FINAL PORTFOLIO BUY / SELL RECOMMENDATION REPORT")
    print("═" * 50)
    
    if not recommendations_list:
        print("No active recommendations. Market spreads are stable.")
    else:
        for idx, rec in enumerate(recommendations_list):
            print(f"\nRECOMMENDATION {idx+1}: {rec['recommendation'].upper()}")
            print(f"Target Deal/Manager: {rec['signal_summary']}")
            print(f"Conviction Level: {rec['conviction_pct']:.1f}%")
            print(f"Pricing Impact: {rec['pricing_impact']}")
            print(f"Reasoning: {rec['reasoning']}")
            print(f"Structural Insights: {rec['structural_insights']}")
            if rec.get("exposure"):
                print(f"Portfolio Exposure Alert:")
                for exp in rec["exposure"]:
                    print(f"  * Hold {exp['deal']} ({exp['rating']}) - Balance: €{exp['balance']}m")
            print("-" * 50)
            
if __name__ == "__main__":
    run_buy_sell_pipeline()
