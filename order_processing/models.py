# -*- coding: utf-8 -*-
"""
Domain models and data structures used throughout the application.
"""
from dataclasses import dataclass, field
from typing import Any, List, Tuple


@dataclass
class Order:
    """
    Represents a customer order with its attributes.

    Attributes:
        id: Unique identifier for the order.
        order_type: The category or type of the order (e.g., 'A', 'B', 'C').
                    Renamed from 'type' to avoid shadowing built-in.
        amount: The monetary value or quantity associated with the order.
        flag: A boolean flag indicating a specific condition for the order.
        status: The current processing status of the order. Defaults to 'new'.
        priority: The processing priority of the order. Defaults to 'low'.
    """
    id: int
    order_type: str
    amount: float
    flag: bool
    status: str = 'new'
    priority: str = 'low'


@dataclass
class APIResponse:
    """
    Represents a standardized response from an external API call.

    Attributes:
        status: A string indicating the outcome ('success', 'error', etc.).
        data: The payload returned by the API. Can be of any type,
              requiring careful handling by the consumer.
    """
    status: str
    data: Any  # Kept as Any, but consumers MUST validate type before use


@dataclass
class ProcessingResult:
    """
    Summarizes the outcome of the order processing operation.

    Attributes:
        was_successful: Overall success status of the processing batch.
        processed_count: Number of orders successfully processed (status updated).
        failed_orders: List of tuples, each containing (order_id, error_message)
                       for orders that failed during processing or DB update.
    """
    was_successful: bool
    processed_count: int = 0
    failed_orders: List[Tuple[int, str]] = field(default_factory=list)
