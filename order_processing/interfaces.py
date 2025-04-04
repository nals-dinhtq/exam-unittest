# -*- coding: utf-8 -*-
"""
Abstract Base Classes defining service contracts (interfaces).
Follows the Dependency Inversion Principle.
"""
from abc import ABC, abstractmethod
from typing import List, Tuple

# Use relative imports within the package
from .models import APIResponse, Order


class DatabaseService(ABC):
    """
    Abstract Base Class defining the contract for database interactions
    related to orders.
    """

    @abstractmethod
    def get_orders_by_user(self, user_id: int) -> List[Order]:
        """
        Retrieves all orders for a given user ID.

        Args:
            user_id: The ID of the user whose orders are to be retrieved.

        Returns:
            A list of Order objects.

        Raises:
            DatabaseException: If there's an error querying the database.
        """
        pass

    @abstractmethod
    def update_order_statuses(self, updates: List[Tuple[int, str, str]]) -> List[int]:
        """
        Updates the status and priority for multiple orders in a single operation.

        Args:
            updates: A list of tuples, where each tuple contains
                     (order_id, new_status, new_priority).

        Returns:
            A list of order IDs that failed to update. An empty list
            indicates all updates were successful.

        Raises:
            DatabaseException: If there's a critical error during the bulk update.
                               Partial failures should be indicated by the return list.
        """
        pass


class APIClient(ABC):
    """
    Abstract Base Class defining the contract for interacting with an external API.
    """

    @abstractmethod
    def call_api(self, order_id: int) -> APIResponse:
        """
        Calls an external API related to a specific order.

        Args:
            order_id: The ID of the order to pass to the API.

        Returns:
            An APIResponse object containing the status and data from the API.

        Raises:
            APIException: If the API call fails.
        """
        pass
