# -*- coding: utf-8 -*-
"""
Domain models and data structures used throughout the application.
"""
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, List, Tuple

from .constants import ORDER_PRIORITY_LOW, ORDER_STATUS_NEW

# Don't use enum to reduce complexity


class OrderType(Enum):
    """Defines the valid types of orders in the system."""

    TYPE_A = "A"  # Export to CSV
    TYPE_B = "B"  # API processing
    TYPE_C = "C"  # Flag-based processing
    TYPE_UNKNOWN = "UNKNOWN"  # Unknown type


# Don't use enum to reduce complexity
class OrderStatus(Enum):
    """Defines the possible statuses for an order."""

    NEW = "new"
    COMPLETED = "completed"
    IN_PROGRESS = "in_progress"
    PROCESSED = "processed"
    PENDING = "pending"
    API_DATA_ERROR = "api_data_error"
    API_FAILURE = "api_failure"
    API_ERROR = "api_error"
    REVIEW_REQUIRED = "review_required"
    PROCESSING_ERROR = "processing_error"
    UNKNOWN_TYPE = "unknown_type"


# Don't use enum to reduce complexity
class OrderPriority(Enum):
    """Defines the priority levels for order processing."""

    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


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
    status: str = ORDER_STATUS_NEW
    priority: str = ORDER_PRIORITY_LOW


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
