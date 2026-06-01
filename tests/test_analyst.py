import pytest
from src.agents.analyst.analyst import CLOAnalyst

def test_analyze_bsl_pricing_buy():
    analyst = CLOAnalyst()
    item = {
        "title": "New Issue Pricing",
        "summary": "Manager X priced a BSL CLO with AAA tranches at S+145bp."
    }
    analysis = analyst.analyze_news_item(item)
    assert analysis["recommendation"] == "BUY"
    assert "wide of BSL benchmark" in analysis["reasoning"]

def test_analyze_bsl_pricing_sell():
    analyst = CLOAnalyst()
    item = {
        "title": "Tight Pricing Alert",
        "summary": "Manager Y priced at S+120bp for AAA tranches."
    }
    analysis = analyst.analyze_news_item(item)
    assert analysis["recommendation"] == "SELL"
    assert "tight of benchmark" in analysis["reasoning"]

def test_middle_market_benchmark():
    analyst = CLOAnalyst()
    item = {
        "title": "Middle Market Deal",
        "summary": "Direct Lending CLO priced AAA at S+165bp."
    }
    analysis = analyst.analyze_news_item(item)
    assert analysis["recommendation"] == "HOLD"
    assert "165bp" in analysis["reasoning"]

def test_structural_insights():
    analyst = CLOAnalyst()
    item = {
        "title": "Volatility in Software Loans",
        "summary": "Selloff in tech loans causing concern."
    }
    analysis = analyst.analyze_news_item(item)
    assert "behavioral synchronization" in analysis["structural_insights"]
