import sys
import os
from fastapi import FastAPI, Query
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List

# Add the project root to the path so we can import the analyst and critic
project_path = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
sys.path.append(project_path)

# Add the skill directory to the path so we can import the reader
skill_path = os.path.abspath(os.path.join(project_path, ".agent", "skills", "clo-news-reader"))
sys.path.append(skill_path)

try:
    from src.agents.news_reader.reader import CLONewsReader
except ImportError:
    try:
        from reader import CLONewsReader
    except ImportError:
        # Try dynamic import loading fallback
        import importlib.util
        reader_file = os.path.join(skill_path, "reader.py")
        if os.path.exists(reader_file):
            spec = importlib.util.spec_from_file_location("reader", reader_file)
            reader_module = importlib.util.module_from_spec(spec)
            sys.modules["reader"] = reader_module
            spec.loader.exec_module(reader_module)
            from reader import CLONewsReader
        else:
            class CLONewsReader:
                def fetch_news(self, query=None, limit=5):
                    return []

try:
    from src.agents.analyst.analyst import CLOAnalyst
    from src.agents.critic.critic import CLOCritic
except ImportError:
    # Local fallback/mock classes if the source code directory structure changes
    class CLOAnalyst:
        def __init__(self, portfolio_path=None):
            self.portfolio = []
        def analyze_news_item(self, item):
            return {"recommendation": "HOLD", "conviction_pct": 70.0, "reasoning": "Fallback analyst: news processed.", "structural_insights": "Fallback structural insights."}
        def refine_analysis(self, val, critique):
            return val
    class CLOCritic:
        def analyze_assessment(self, val):
            return {"score": 8, "decision": "ESCALATE", "challenges": [], "framework_critique": "Fallback critique."}

app = FastAPI(title="CLO News & Surveillance API")

# Enable CORS for local file access and local servers
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

reader = CLONewsReader()

mock_portfolio = [
    {"deal": "CLO A", "manager": "Manager A", "rating": "Aaa", "balance": 1.0},
    {"deal": "CLO B", "manager": "Manager B", "rating": "Aaa", "balance": 1.0},
    {"deal": "CLO C", "manager": "Manager C", "rating": "Aaa", "balance": 1.0},
    {"deal": "CLO D", "manager": "Manager D", "rating": "Baa3", "balance": 1.0},
    {"deal": "CLO E", "manager": "Manager E", "rating": "Baa3", "balance": 1.0}
]

def get_portfolio_path():
    gsheet_path = "/Users/christos/Library/CloudStorage/GoogleDrive-cdanias@gmail.com/My Drive/CLO portfolio example sheet.gsheet"
    fallback_xlsx_path = "/Users/christos/Downloads/european_clo_bonds.xlsx"
    if os.path.exists(gsheet_path):
        return fallback_xlsx_path
    return fallback_xlsx_path

@app.get("/news")
async def get_news(q: Optional[str] = None, limit: int = 5):
    """
    Endpoint to fetch latest CLO news using the specialized skill.
    """
    news = reader.fetch_news(query=q, limit=limit)
    return {"status": "success", "count": len(news), "data": news}

@app.get("/api/portfolio")
async def get_portfolio():
    path = get_portfolio_path()
    try:
        analyst = CLOAnalyst(portfolio_path=path)
        portfolio = analyst.portfolio
    except Exception:
        analyst = CLOAnalyst()
        portfolio = []
        
    if not portfolio:
        portfolio = mock_portfolio
        
    # Generate recommendations for each holding
    enriched_portfolio = []
    for holding in portfolio:
        analysis = analyst.analyze_holding(holding)
        holding_copy = holding.copy()
        holding_copy["recommendation"] = analysis["recommendation"]
        holding_copy["reason"] = analysis["reason"]
        enriched_portfolio.append(holding_copy)
        
    strategy = analyst.generate_portfolio_strategy()
        
    return {
        "status": "success", 
        "data": enriched_portfolio,
        "strategy": strategy
    }

class AnalysisRequest(BaseModel):
    title: str
    summary: Optional[str] = ""
    date: Optional[str] = "Today"
    source: Optional[str] = "User Input"
    link: Optional[str] = ""
    # Analyst overrides: user-supplied stress assumptions
    expected_default_rate: Optional[float] = None   # e.g. 20.0 = 20%
    recovery_rate: Optional[float] = None            # e.g. 58.0 = 58%

@app.post("/api/analyze")
async def analyze_item(request: AnalysisRequest):
    path = get_portfolio_path()
    try:
        analyst = CLOAnalyst(portfolio_path=path)
    except Exception:
        analyst = CLOAnalyst()
    if not analyst.portfolio:
        analyst.portfolio = mock_portfolio
        
    try:
        critic = CLOCritic()
    except Exception:
        critic = None
        
    item = request.model_dump()
    logs = []
    
    # Reset Critic memory at the start of each new analysis session so
    # that pass-1 challenges are verified on pass-2 for THIS item only.
    if critic:
        critic.reset()
    
    # Run loop
    logs.append({"step": "Analyst Pass 1", "message": "Analyst running first pass analysis..."})
    analysis = analyst.analyze_news_item(item)
    logs.append({
        "step": "Analyst Pass 1 Output", 
        "message": f"Initial Recommendation: {analysis.get('recommendation', 'HOLD')} with {analysis.get('conviction_pct', 70.0)}% conviction."
    })
    
    if critic:
        # Loop 1
        logs.append({"step": "Critic Pass 1", "message": "Critic auditing Analyst's first pass..."})
        critique1 = critic.analyze_assessment(analysis)
        logs.append({
            "step": "Critic Pass 1 Output", 
            "message": f"Critic Score: {critique1.get('score', 7)}/10. Decision: {critique1.get('decision', 'LOOP BACK')}.",
            "challenges": critique1.get("challenges", []),
            "framework_critique": critique1.get("framework_critique", {}),
            "verification": []  # No prior pass to verify on pass 1
        })
        
        logs.append({"step": "Analyst Pass 2", "message": "Analyst refining assessment based on Critic feedback..."})
        analysis = analyst.refine_analysis(analysis, critique1)
        logs.append({
            "step": "Analyst Pass 2 Output", 
            "message": f"Refined Recommendation: {analysis.get('recommendation', 'HOLD')} with {analysis.get('conviction_pct', 75.0)}% conviction."
        })
        
        # Loop 2
        logs.append({"step": "Critic Pass 2", "message": "Critic auditing Analyst's second pass — verifying prior challenges were addressed..."})
        critique2 = critic.analyze_assessment(analysis)
        verification2 = critique2.get("verification", [])
        resolved   = [v for v in verification2 if v.get("resolved")]
        unresolved = [v for v in verification2 if not v.get("resolved")]
        verify_msg = (
            f"{len(resolved)}/{len(verification2)} prior challenge(s) addressed. "
            + (f"{len(unresolved)} unresolved — penalising score." if unresolved else "All challenges resolved.")
        )
        change_msg = critique2.get("recommendation_change_message", "")
        if change_msg:
            verify_msg += f" {change_msg}"
            
        logs.append({
            "step": "Critic Pass 2 Output", 
            "message": f"Critic Score: {critique2.get('score', 8)}/10. Decision: {critique2.get('decision', 'ESCALATE')}. {verify_msg}",
            "challenges": critique2.get("challenges", []),
            "framework_critique": critique2.get("framework_critique", {}),
            "verification": verification2
        })
        
        logs.append({"step": "Analyst Pass 3", "message": "Analyst finalizing assessment based on verified critic feedback..."})
        analysis = analyst.refine_analysis(analysis, critique2)
        final_conviction = analysis.get('conviction_pct', 80.0)
        final_rec        = analysis.get('recommendation', 'HOLD')
        gated = "[Conviction gate applied — downgraded to HOLD]" if "Conviction Gate" in analysis.get("reasoning", "") else ""
        logs.append({
            "step": "Analyst Pass 3 Output", 
            "message": f"Final Recommendation: {final_rec} with {final_conviction:.0f}% conviction. {gated}".strip()
        })
    else:
        logs.append({"step": "Critic Warning", "message": "Critic agent unavailable; skipping audit loop."})
        
    return {
        "status": "success",
        "data": analysis,
        "logs": logs
    }

@app.get("/api/pipeline")
async def run_full_pipeline(q: Optional[str] = None, limit: int = 3):
    news = reader.fetch_news(query=q, limit=limit)
    path = get_portfolio_path()
    try:
        analyst = CLOAnalyst(portfolio_path=path)
    except Exception:
        analyst = CLOAnalyst()
    if not analyst.portfolio:
        analyst.portfolio = mock_portfolio
        
    try:
        critic = CLOCritic()
    except Exception:
        critic = None
        
    results = []
    for item in news:
        analysis = analyst.analyze_news_item(item)
        if critic:
            for _ in range(2):
                critique = critic.analyze_assessment(analysis)
                analysis = analyst.refine_analysis(analysis, critique)
        results.append(analysis)
        
    return {"status": "success", "count": len(results), "data": results}

from fastapi.responses import HTMLResponse

@app.get("/", response_class=HTMLResponse)
async def get_dashboard():
    dashboard_path = os.path.join(project_path, "clo-analyst-dashboard.html")
    if os.path.exists(dashboard_path):
        with open(dashboard_path, "r") as f:
            return f.read()
    return "<h3>Dashboard HTML file not found</h3>"

@app.get("/health")
async def health_check():
    return {"status": "healthy"}

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
