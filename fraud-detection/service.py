import pickle
from sklearn.ensemble import IsolationForest

class FraudDetector:
    def __init__(self):
        # Load pre-trained ML model
        with open('model.pkl', 'rb') as f:
            self.ml_model = pickle.load(f)  
        
        self.rules = [
            {"name": "high_amount_new_recipient", "threshold": 5000},
            {"name": "geo_velocity", "max_hours": 2}
        ]

    def evaluate(self, transaction):
        # Rule Engine
        risk_score = 0
        for rule in self.rules:
            if self._matches_rule(transaction, rule):
                risk_score += 0.4
        
        # ML Anomaly Detection
        ml_features = self._extract_features(transaction)
        anomaly_score = self.ml_model.predict([ml_features])[0]
        
        return {
            "risk_score": min(risk_score + (anomaly_score * 0.6), 1.0),
            "rules_triggered": [r["name"] for r in self.rules if self._matches_rule(transaction, r)]
        }