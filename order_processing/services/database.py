# -*- coding: utf-8 -*-
"""
Concrete implementations of the DatabaseService interface.
Includes mock/demo implementations.
"""
import logging
from typing import Dict, List, Optional, Tuple

# Use relative imports
from ..interfaces import DatabaseService
from ..models import Order

log = logging.getLogger(__name__)


class InMemoryDbService(DatabaseService):
    """DEMO implementation of DatabaseService using in-memory data."""

    def __init__(self, initial_orders: Optional[Dict[int, List[Order]]] = None):
        self._orders_by_user = initial_orders or {}
        # Create a flat map for easier updates by ID
        self._all_orders_by_id = {
            order.id: order for user_orders in self._orders_by_user.values() for order in user_orders
        }
        log.info(f"InMemoryDbService initialized with {len(self._all_orders_by_id)} total orders.")

    def get_orders_by_user(self, user_id: int) -> List[Order]:
        log.info(f"DB: Getting orders for user {user_id}")
        return list(self._orders_by_user.get(user_id, []))

    def update_order_statuses(self, updates: List[Tuple[int, str, str]]) -> List[int]:
        log.info(f"DB: Attempting to update statuses for {len(updates)} orders.")
        failed_ids = []
        # In a real DB, this would be a single transaction/bulk operation

        for order_id, status, priority in updates:
            # Simulate partial failure
            if order_id % 10 == 0 and order_id != 110:  # Fail every 10th order ID for demo, except 110
                log.warning(f"DB: Simulated failure updating order {order_id}")
                failed_ids.append(order_id)
                continue

            if order_id == 110:  # Explicitly fail order 110 for demo consistency
                log.warning(f"DB: Simulated explicit failure updating order {order_id}")
                failed_ids.append(order_id)
                continue

            if order_id in self._all_orders_by_id:
                # Update the central order object
                self._all_orders_by_id[order_id].status = status
                self._all_orders_by_id[order_id].priority = priority
                log.debug(f"DB: Updated order {order_id} to status={status}, priority={priority}")
            else:
                log.warning(f"DB: Order {order_id} not found for update.")
                failed_ids.append(order_id)  # Treat not found as failure

        if not failed_ids:
            log.info(f"DB: Bulk update successful for {len(updates)} orders.")
        else:
            log.warning(f"DB: Bulk update completed with {len(failed_ids)} failures out of {len(updates)} attempts.")
        return failed_ids


# Add real database implementations here (e.g., PostgresDbService) if needed
