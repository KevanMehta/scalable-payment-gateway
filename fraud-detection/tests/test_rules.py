# fraud-detection/tests/test_rules.py
from rule_engine import RuleEngine

def test_high_amount_rule():
    engine = RuleEngine()
    result = engine.evaluate({
        "amount": 6000,
        "is_new_recipient": True,
        "location_changes": 0
    })
    assert result["risk_score"] == 0.7
    assert "high_amount_new_recipient" in result["triggered_rules"]