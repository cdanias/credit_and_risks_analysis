import pytest
from src.agents.critic.critic import CLOCritic

def test_critic_identifies_logical_gap():
    critic = CLOCritic()
    analysis = {
        "recommendation": "BUY",
        "reasoning": "Spreads are wide, so credit quality must be fine.",
        "key_facts": {"AAA": 150}
    }
    review = critic.analyze_assessment(analysis)
    assert any(gap["category"] == "Logical Gap" for gap in review["challenges"])
    assert review["score"] < 10

def test_critic_framework_check():
    critic = CLOCritic()
    analysis = {
        "reasoning": "Stable according to our historical benchmark.",
        "structural_insights": "No issues."
    }
    review = critic.analyze_assessment(analysis)
    assert len(review["framework_critique"]["traps_identified"]) > 0

def test_critic_iteration_limit():
    critic = CLOCritic()
    analysis = {"recommendation": "HOLD", "reasoning": "test"}
    # Manually trigger 3 iterations
    critic.analyze_assessment(analysis)
    critic.analyze_assessment(analysis)
    review = critic.analyze_assessment(analysis)
    assert review["decision"] == "ESCALATE"
    assert review["iteration"] == 3

def test_critic_recommendation_memory():
    critic = CLOCritic()
    
    # Pass 1: Analyst has a gap and recommends "BUY"
    analysis1 = {
        "recommendation": "BUY",
        "reasoning": "Spreads are wide, so credit quality is stable. This is a very long reasoning string to get the substantive reasoning bonus of 1 point. We also perform portfolio exposure checks and include structural insights.",
        "structural_insights": "Direct BSL exposure is mapped.",
        "exposure": [{"deal": "CLO A"}],
        "key_facts": {"AAA": 150} # Has Gap 2 (Single data-point anchoring)
    }
    review1 = critic.analyze_assessment(analysis1)
    assert len(review1["challenges"]) > 0
    assert review1["recommendation_history"] == ["BUY"]
    
    # Pass 2 (Stubborn): Analyst keeps "BUY" and does not resolve the gap
    analysis2 = {
        "recommendation": "BUY",
        "reasoning": "Spreads are wide, so credit quality is stable. This is a very long reasoning string to get the substantive reasoning bonus of 1 point. We also perform portfolio exposure checks and include structural insights.",
        "structural_insights": "Direct BSL exposure is mapped.",
        "exposure": [{"deal": "CLO A"}],
        "key_facts": {"AAA": 150}
    }
    review2 = critic.analyze_assessment(analysis2)
    assert "maintained recommendation" in review2["recommendation_change_message"]
    # The score should be penalized for stubbornness
    assert review2["score"] < review1["score"]
    
    # Reset and test Adaptability
    critic.reset()
    critic.analyze_assessment(analysis1)
    
    # Pass 2 (Adapted): Analyst changes to "HOLD"
    analysis3 = {
        "recommendation": "HOLD",
        "reasoning": "Spreads are wide, so credit quality is stable. This is a very long reasoning string to get the substantive reasoning bonus of 1 point. We also perform portfolio exposure checks and include structural insights.",
        "structural_insights": "Direct BSL exposure is mapped.",
        "exposure": [{"deal": "CLO A"}],
        "key_facts": {"AAA": 150}
    }
    review3 = critic.analyze_assessment(analysis3)
    assert "adapted recommendation" in review3["recommendation_change_message"]

