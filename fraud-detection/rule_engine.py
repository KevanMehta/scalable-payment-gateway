import numpy as np
from typing import Dict

class RuleEngine:
    RULES = [
        {
            "name": "high_amount_new_recipient",
            "condition": lambda t: t['amount'] > 5000 and t['is_new_recipient'],
            "risk_score": 0.7
        },
        {
            "name": "geo_velocity",
            "condition": lambda t: t['location_changes'] > 3,
            "risk_score": 0.5
        }
    ]

    def evaluate(self, transaction: Dict) -> Dict:
        triggered_rules = []
        total_risk = 0.0
        
        for rule in self.RULES:
            if rule["condition"](transaction):
                triggered_rules.append(rule["name"])
                total_risk += rule["risk_score"]
        
        return {
            "risk_score": min(total_risk, 1.0),
            "triggered_rules": triggered_rules
        }