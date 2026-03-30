"""Transaction domain model."""

from datetime import datetime
from typing import Optional
from pydantic import BaseModel, Field


class Transaction(BaseModel):
    """Represents a payment transaction for fraud analysis."""

    transaction_id: str = Field(..., description="Unique transaction identifier")
    merchant_id: str = Field(..., description="Merchant identifier")
    merchant_name: str = Field(default="", description="Merchant display name")
    merchant_category_code: str = Field(default="", description="MCC code")
    amount_cents: int = Field(..., description="Transaction amount in smallest currency unit (cents)")
    currency: str = Field(default="USD", description="ISO 4217 currency code")
    card_brand: str = Field(default="", description="Card brand (visa, mastercard, etc.)")
    card_last_four: str = Field(default="", description="Last 4 digits of card number")
    card_bin: str = Field(default="", description="Bank Identification Number (first 6-8 digits)")
    is_card_present: bool = Field(default=False, description="Whether card was physically present")
    entry_mode: str = Field(default="", description="How card data was captured")
    ip_address: Optional[str] = Field(default=None, description="Customer IP address")
    billing_country: str = Field(default="", description="Billing address country code")
    shipping_country: Optional[str] = Field(default=None, description="Shipping address country code")
    customer_id: Optional[str] = Field(default=None, description="Customer identifier")
    timestamp: datetime = Field(default_factory=datetime.utcnow, description="Transaction timestamp")
    is_recurring: bool = Field(default=False, description="Whether this is a recurring payment")
    authorization_code: Optional[str] = Field(default=None, description="Auth code from issuer")
    response_code: Optional[str] = Field(default=None, description="Issuer response code")

    @property
    def amount_dollars(self) -> float:
        """Amount in dollars for display purposes."""
        return self.amount_cents / 100.0

    def to_analysis_text(self) -> str:
        """Convert to natural language for embedding and LLM analysis."""
        return (
            f"Transaction {self.transaction_id}: "
            f"Merchant '{self.merchant_name}' (ID: {self.merchant_id}, MCC: {self.merchant_category_code}), "
            f"Amount: ${self.amount_dollars:.2f} {self.currency}, "
            f"Card: {self.card_brand} ending {self.card_last_four} (BIN: {self.card_bin}), "
            f"{'Card-present' if self.is_card_present else 'Card-not-present'}, "
            f"Entry mode: {self.entry_mode}, "
            f"Billing country: {self.billing_country}, "
            f"Shipping country: {self.shipping_country or 'N/A'}, "
            f"IP address: {self.ip_address or 'N/A'}, "
            f"Customer ID: {self.customer_id or 'N/A'}, "
            f"{'Recurring' if self.is_recurring else 'One-time'}, "
            f"Time: {self.timestamp.isoformat()}"
        )
