from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Optional


@dataclass
class LineItemSpec:
    name: str
    value: str


@dataclass
class LineItem:
    description: str
    quantity: Optional[float] = None
    unit: Optional[str] = None
    specifications: List[LineItemSpec] = field(default_factory=list)
    category: Optional[str] = None


@dataclass
class TenderLineItems:
    items: List[LineItem] = field(default_factory=list)
