import pytest
from src.agents.analyst.analyst import CLOAnalyst
from src.agents.critic.critic import CLOCritic

def test_load_portfolio_fallback():
    # Verify that the analyst can load the portfolio from the Excel file
    portfolio_path = "/Users/christos/Downloads/european_clo_bonds.xlsx"
    analyst = CLOAnalyst(portfolio_path=portfolio_path)
    assert len(analyst.portfolio) > 0
    assert "deal" in analyst.portfolio[0]
    assert "manager" in analyst.portfolio[0]

def test_double_loop_refinement():
    analyst = CLOAnalyst()
    critic = CLOCritic()
    
    # Mock news item
    item = {
        "title": "Barings prices new deal at S+145",
        "summary": "Barings priced its latest BSL CLO with AAA tranches at S+145bp."
    }
    
    # First Pass Analyst
    analysis = analyst.analyze_news_item(item)
    assert analysis["recommendation"] == "BUY"
    initial_conviction = analysis["conviction_pct"]
    assert initial_conviction == 80.0
    
    # Loop 1
    critique1 = critic.analyze_assessment(analysis)
    assert critique1["score"] < 10 # Gaps should reduce score
    
    analysis = analyst.refine_analysis(analysis, critique1)
    assert analysis["conviction_pct"] != initial_conviction
    assert "Critic Challenge Addressed" in analysis["reasoning"]
    
    # Loop 2
    critique2 = critic.analyze_assessment(analysis)
    analysis = analyst.refine_analysis(analysis, critique2)
    
    # Double check that the conviction remains bounded and logical
    assert 10.0 <= analysis["conviction_pct"] <= 100.0

def test_interactive_pipeline_logic(monkeypatch):
    # Verify that the interactive script works using mock inputs
    from src.interactive_pipeline import run_interactive_pipeline
    
    # Mock inputs: first empty for news (will fetch live), then empty for portfolio (default)
    inputs = iter(["", ""])
    monkeypatch.setattr('builtins.input', lambda prompt: next(inputs))
    
    # Just run it to make sure it executes without throwing errors
    try:
        run_interactive_pipeline()
    except Exception as e:
        pytest.fail(f"run_interactive_pipeline raised an exception with defaults: {e}")

