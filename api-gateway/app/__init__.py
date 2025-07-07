# Initialize FastAPI app and shared utilities
from fastapi import FastAPI
from .services.payment_processor import PaymentProcessor

app = FastAPI()
payment_processor = PaymentProcessor()