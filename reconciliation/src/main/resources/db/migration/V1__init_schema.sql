CREATE TABLE transaction_reconciliations (
  id SERIAL PRIMARY KEY,
  payment_id UUID NOT NULL,
  merchant_id VARCHAR(255) NOT NULL,
  amount DECIMAL(12,2) NOT NULL,
  status VARCHAR(50) NOT NULL,
  expected_settlement_date TIMESTAMP,
  actual_settlement_date TIMESTAMP,
  discrepancy_reason TEXT
);

CREATE INDEX idx_reconciliation_merchant ON transaction_reconciliations(merchant_id);
CREATE INDEX idx_reconciliation_dates ON transaction_reconciliations(expected_settlement_date, actual_settlement_date);