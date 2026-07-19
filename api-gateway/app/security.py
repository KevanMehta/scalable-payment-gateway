import hmac
import json
import os

from fastapi import Header, HTTPException


def verify_api_key(merchant_id: str, api_key: str, configured_keys: dict[str, str]) -> bool:
    expected = configured_keys.get(merchant_id)
    return isinstance(expected, str) and hmac.compare_digest(expected, api_key)


def authenticate_merchant(
    merchant_id: str = Header(min_length=1, max_length=100, alias="X-Merchant-Id"),
    api_key: str = Header(min_length=8, max_length=512, alias="X-API-Key"),
) -> str:
    raw_keys = os.getenv("PAYMENT_API_KEYS")
    if not raw_keys:
        raise HTTPException(status_code=503, detail="merchant authentication is not configured")
    try:
        configured_keys = json.loads(raw_keys)
    except json.JSONDecodeError as exc:
        raise HTTPException(status_code=503, detail="merchant authentication is invalid") from exc
    if not isinstance(configured_keys, dict) or not verify_api_key(
        merchant_id, api_key, configured_keys
    ):
        raise HTTPException(status_code=401, detail="invalid merchant credentials")
    return merchant_id
