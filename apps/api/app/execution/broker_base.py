"""
Broker adapter interface — see AGENTS.md section 2 and
docs/ARCHITECTURE.md "Provider Adapter Pattern". Execution logic must
depend only on this interface, never on a concrete broker.

Only one implementation exists in this codebase: PaperBrokerAdapter
(paper_broker.py). Adding a REAL broker adapter is explicitly out of scope
for this build stage — see that module's docstring for why.
"""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime


@dataclass
class FillResult:
    filled_price: float
    filled_at: datetime
    broker_order_id: str


class BrokerAdapter(ABC):
    @abstractmethod
    def place_market_order(self, symbol: str, direction: str, units: float) -> FillResult:
        """Place a market order and return how it filled."""
