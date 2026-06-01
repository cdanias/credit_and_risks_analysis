import os
import sys

# Add the project root to sys.path
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from src.agents.news_reader.reader import CLONewsReader
from src.agents.analyst.analyst import CLOAnalyst
from src.agents.critic.critic import CLOCritic
from src.agents.news_reader.risk_analyzer import RiskAnalyzer

def run_interactive_pipeline():
    print("==================================================")
    print("   Interactive CLO Market Intelligence Pipeline  ")
    print("==================================================")
    
    # 1. Ask for news input
    print("\n[Step 1/2: News Input]")
    custom_news = input("Type latest news/headline on CLOs (or press Enter to fetch live news): ").strip()
    
    # 2. Ask for portfolio file
    print("\n[Step 2/2: Portfolio Upload]")
    default_path = "/Users/christos/Downloads/european_clo_bonds.xlsx"
    user_path = input(f"Enter the path to CLO portfolio Excel file (or press Enter to use '{default_path}'): ").strip()
    
    portfolio_path = user_path if user_path else default_path
    
    if not os.path.exists(portfolio_path):
        print(f"❌ Error: Portfolio file not found at: {portfolio_path}")
        return
        
    # Initialize agents
    analyst = CLOAnalyst(portfolio_path=portfolio_path)
    critic = CLOCritic()
    
    print(f"\n📊 Loaded {len(analyst.portfolio)} portfolio holdings from database.")
    for holding in analyst.portfolio:
        print(f"   - {holding['deal']} (Manager: {holding['manager']}, Rating: {holding['rating']}, Balance: €{holding['balance']}m)")
        
    # Process news
    news_items = []
    if custom_news:
        # Build item from custom user input
        risk_analyzer = RiskAnalyzer()
        item = {
            "title": custom_news,
            "summary": "",
            "date": "Today",
            "source": "User Input",
            "link": ""
        }
        item.update(risk_analyzer.analyze_item(custom_news, ""))
        news_items.append(item)
        print(f"\n📰 Using custom user news signal: {custom_news}")
    else:
        # Fetch live news
        print(f"\n📡 Fetching live CLO news signals...")
        reader = CLONewsReader()
        news_items = reader.fetch_news(limit=3)
        print(f"✅ Found {len(news_items)} live news articles.")

    recommendations_list = []
    
    # Process each news signal
    for i, item in enumerate(news_items):
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
        
    # Final Output Recommendation Report
    print("\n" + "═" * 50)
    print("      FINAL PORTFOLIO BUY / SELL RECOMMENDATION REPORT")
    print("═" * 50)
    
    if not recommendations_list:
        print("No active recommendations.")
    else:
        for idx, rec in enumerate(recommendations_list):
            print(f"\nRECOMMENDATION {idx+1}: {rec['recommendation'].upper()}")
            print(f"Target Deal/Manager/Signal: {rec['signal_summary']}")
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
    run_interactive_pipeline()
