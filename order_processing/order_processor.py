# -*- coding: utf-8 -*-
"""
Contains the main OrderProcessingService logic for orchestrating order processing.
"""
import logging
import time
from typing import Dict, List, Optional, Tuple

from .constants import (
    API_DATA_THRESHOLD,
    API_RESPONSE_SUCCESS,
    ORDER_AMOUNT_THRESHOLD,
    ORDER_PRIORITY_HIGH,
    ORDER_PRIORITY_LOW,
    ORDER_PRIORITY_THRESHOLD,
    ORDER_STATUS_API_DATA_ERROR,
    ORDER_STATUS_API_ERROR,
    ORDER_STATUS_API_FAILURE,
    ORDER_STATUS_COMPLETED,
    ORDER_STATUS_IN_PROGRESS,
    ORDER_STATUS_PENDING,
    ORDER_STATUS_PROCESSED,
    ORDER_STATUS_PROCESSING_ERROR,
    ORDER_STATUS_REVIEW_REQUIRED,
    ORDER_STATUS_UNKNOWN_TYPE,
    ORDER_TYPE_A,
    ORDER_TYPE_B,
    ORDER_TYPE_C,
)
from .exceptions import APIException, CsvExportException, DatabaseException

# Use relative imports
from .interfaces import APIClient, DatabaseService
from .models import Order, ProcessingResult
from .services.exporters import CsvOrderExporter  # Import the concrete exporter

log = logging.getLogger(__name__)


class OrderProcessingService:
    """
    Orchestrates the processing of orders for a user.

    Uses dependency injection for database and API interactions,
    adhering to DIP and OCP.
    """

    def __init__(
        self,
        db_service: DatabaseService,
        api_client: APIClient,
        exporter: Optional[CsvOrderExporter] = None,
    ):
        """Initialize service with dependencies."""
        if not isinstance(db_service, DatabaseService):
            raise TypeError("db_service must be an instance of DatabaseService")
        if not isinstance(api_client, APIClient):
            raise TypeError("api_client must be an instance of APIClient")

        self.db_service = db_service
        self.api_client = api_client
        self.exporter = exporter or CsvOrderExporter()

    def process_orders_for_user(self, user_id: int) -> ProcessingResult:
        """
        Orchestrates fetching, processing, exporting, and persisting orders for a user.

        Args:
            user_id: The ID of the user whose orders need processing.

        Returns:
            A ProcessingResult object summarizing the outcome.
        """
        result = ProcessingResult(was_successful=False)  # Initialize result

        # Stage 0: Fetch orders
        orders = self._fetch_user_orders(user_id, result)
        # If fetching failed or no orders, result is already set, return early.
        if orders is None:
            # If fetch was successful but returned no orders, result.was_successful is True.
            # If fetch failed, result.was_successful is False.
            return result

        # Stage 1: Process all orders
        # orders_to_update collects orders needing DB persistence
        # orders_type_a collects orders for export
        orders_to_update, orders_type_a = self._process_orders(orders, result)

        # Stage 2: Handle Type A export operations
        # This modifies orders_type_a statuses and updates orders_to_update dict accordingly
        self._handle_type_a_exports(orders_type_a, user_id, result, orders_to_update)
        # Stage 3: Persist changes to database
        # This updates result.processed_count and result.was_successful based on DB outcome
        # Needs the original 'orders' list to correctly calculate processed_count if no DB updates are needed.
        self._persist_order_changes(orders_to_update, orders, result)

        # Final result reflects outcomes of all stages
        return result

    # --- Private Helper Methods (SRP, Clean Code) ---

    def _fetch_user_orders(self, user_id: int, result: ProcessingResult) -> Optional[List[Order]]:
        """Fetches orders for the user, handling initial DB errors."""
        try:
            orders = self.db_service.get_orders_by_user(user_id)
            if not orders:
                log.info(f"No orders found for user {user_id}. Processing considered successful.")
                result.was_successful = True  # No orders is not a failure state
                return None  # Indicate no orders to process
            return orders
        except DatabaseException as e:
            log.error(f"DB Error fetching orders for user {user_id}: {e}")
            result.failed_orders.append((-1, f"DB Error fetching orders: {e}"))
            result.was_successful = False  # Ensure failure state
            return None  # Cannot proceed

    def _process_orders(
        self, orders: List[Order], result: ProcessingResult
    ) -> Tuple[Dict[int, Tuple[int, str, str]], List[Order]]:
        """Processes each order, determines status/priority, handles exceptions."""
        orders_to_update_in_db: Dict[int, Tuple[int, str, str]] = {}
        orders_type_a: List[Order] = []

        for order in orders:
            original_status = order.status
            original_priority = order.priority
            try:
                self._process_single_order(order)

                # Determine Priority
                self._determine_priority(order)

                # Collect orders for specific actions
                if order.order_type == ORDER_TYPE_A:
                    orders_type_a.append(order)

                # Check if update needed for DB (status or priority changed)
                if order.status != original_status or order.priority != original_priority:
                    orders_to_update_in_db[order.id] = (
                        order.id,
                        order.status,
                        order.priority,
                    )
                else:
                    log.debug(f"Order {order.id}: No change in status/priority during initial processing.")

            except (APIException, CsvExportException) as e:
                log.warning(f"Failed to process order {order.id}: {e}")
                result.failed_orders.append((order.id, str(e)))
                # Ensure this failed state is persisted if it changed status/priority
                orders_to_update_in_db[order.id] = (
                    order.id,
                    order.status,
                    order.priority,
                )

            except Exception as e:  # Catch unexpected errors during single order processing
                log.exception(f"Unexpected error processing order {order.id}")
                result.failed_orders.append((order.id, f"Unexpected error: {e}"))
                # Mark with generic error status for DB update attempt
                order.status = ORDER_STATUS_PROCESSING_ERROR
                # Ensure this failed state is persisted (always different from original if this block is hit)
                orders_to_update_in_db[order.id] = (
                    order.id,
                    order.status,
                    order.priority,
                )

        return orders_to_update_in_db, orders_type_a

    def _handle_type_a_exports(
        self,
        orders_type_a: List[Order],
        user_id: int,
        result: ProcessingResult,
        orders_to_update: Dict[int, Tuple[int, str, str]],
    ) -> None:
        """Handles the export process for Type A orders."""
        if not orders_type_a:
            return  # Nothing to export

        # Use consistent timestamp for batch export
        timestamp = int(time.time())

        try:
            # Exporter modifies status of orders in orders_type_a list
            self.exporter.export_orders(orders_type_a, user_id, timestamp)

            # Update the DB update list with the final status from the exporter
            for order_a in orders_type_a:
                # Always update Type A orders in DB after export attempt
                orders_to_update[order_a.id] = (
                    order_a.id,
                    order_a.status,
                    order_a.priority,
                )

        except CsvExportException as e:
            # Error already logged by exporter. Exporter should have marked orders as 'export_failed'.
            log.error(f"CSV Export process failed for user {user_id}: {e}")
            # Update the DB update list for ALL orders intended for export, reflecting failure status
            for order_a in orders_type_a:
                # Assume exporter set status to failed on exception
                orders_to_update[order_a.id] = (
                    order_a.id,
                    order_a.status,
                    order_a.priority,
                )
                # Ensure failure is recorded
                if not any(f[0] == order_a.id for f in result.failed_orders):
                    result.failed_orders.append((order_a.id, f"CSV export failed: {e}"))

    def _persist_order_changes(
        self,
        orders_to_update: Dict[int, Tuple[int, str, str]],
        all_orders: List[Order],
        result: ProcessingResult,
    ) -> None:
        """Persists the collected order changes to the database."""
        final_updates_list = list(orders_to_update.values())

        if not final_updates_list:
            # If nothing needs updating, success depends only on whether processing errors occurred earlier.
            result.was_successful = not result.failed_orders
            # Processed count is total orders minus failed ones encountered during processing stage
            # (as nothing needed a DB update, successful or not).
            result.processed_count = len(all_orders) - len(result.failed_orders)
            log.info(
                f"No orders required database update. "
                f"Processed count: {result.processed_count}, "
                f"Successful: {result.was_successful}"
            )
            return  # Nothing more to do

        try:
            failed_update_ids = self.db_service.update_order_statuses(final_updates_list)

            processed_in_db = len(final_updates_list) - len(failed_update_ids)
            # Count reflects successful DB updates
            result.processed_count = processed_in_db

            if not failed_update_ids:
                # DB update succeeded for all intended orders.
                # Overall success still depends on whether any *processing* errors occurred earlier.
                result.was_successful = not result.failed_orders
                log.info(
                    f"Successfully updated {processed_in_db} orders in DB. Overall success: {result.was_successful}"
                )
            else:
                log.warning(f"Failed to update {len(failed_update_ids)} out of {len(final_updates_list)} orders in DB.")
                result.was_successful = False  # Mark overall as failure due to DB issues
                # Add DB update failures to the result list, avoiding duplicates
                for order_id in failed_update_ids:
                    if not any(f[0] == order_id for f in result.failed_orders):
                        result.failed_orders.append((order_id, "DB update failed"))

        except DatabaseException as e:
            log.exception("Critical database error during bulk update.")
            result.was_successful = False
            result.processed_count = 0  # No updates confirmed successful
            # Add all orders intended for update as failed due to DB error, avoiding duplicates
            for order_id, _, _ in final_updates_list:
                if not any(f[0] == order_id for f in result.failed_orders):
                    result.failed_orders.append((order_id, f"DB Error during bulk update: {e}"))

    def _process_single_order(self, order: Order) -> None:
        """Determines the status of a single order based on its type. Modifies order status."""

        if order.order_type == ORDER_TYPE_A:
            self._handle_order_type_a(order)
        elif order.order_type == ORDER_TYPE_B:
            self._handle_order_type_b(order)
        elif order.order_type == ORDER_TYPE_C:
            self._handle_order_type_c(order)
        else:
            log.warning(f"Order {order.id}: Unknown order type '{order.order_type}'.")
            order.status = ORDER_STATUS_UNKNOWN_TYPE

    def _handle_order_type_a(self, order: Order) -> None:
        """Handles logic specific to Type A orders (marks for export)."""
        log.debug(f"Order {order.id}: Type A identified. Status will be set by exporter.")
        # Status remains 'new' or current state until exporter runs.
        # Exporter will set it to 'exported' or 'export_failed'.
        pass

    def _handle_order_type_b(self, order: Order) -> None:
        """Handles logic specific to Type B orders (API call). Modifies order status."""
        log.debug(f"Order {order.id}: Type B - Calling API.")
        try:
            api_response = self.api_client.call_api(order.id)

            if api_response.status == API_RESPONSE_SUCCESS:
                api_data = api_response.data
                try:
                    # Attempt conversion/check if data is numeric-like
                    if isinstance(api_data, (int, float)):
                        numeric_api_data = api_data
                    else:
                        # Try converting if it looks like a number string, else fail
                        numeric_api_data = float(api_data)

                    # --- Apply Business Logic ---
                    if numeric_api_data >= API_DATA_THRESHOLD and order.amount < ORDER_AMOUNT_THRESHOLD:
                        order.status = ORDER_STATUS_PROCESSED
                    elif numeric_api_data < API_DATA_THRESHOLD:
                        order.status = ORDER_STATUS_PENDING
                    else:  # Case: numeric_api_data >= API_DATA_THRESHOLD AND order.amount >= ORDER_AMOUNT_THRESHOLD
                        order.status = ORDER_STATUS_REVIEW_REQUIRED

                except (ValueError, TypeError):
                    order.status = ORDER_STATUS_API_DATA_ERROR

            else:  # API call was made, but reported a non-success status
                order.status = ORDER_STATUS_API_ERROR

        except APIException:
            # Logged by caller loop, just set status
            # Debug level sufficient here
            order.status = ORDER_STATUS_API_FAILURE
            raise  # Re-raise for the main loop's error handling/result tracking

    def _handle_order_type_c(self, order: Order) -> None:
        """Handles logic specific to Type C orders. Modifies order status."""
        if order.flag:
            order.status = ORDER_STATUS_COMPLETED
        else:
            order.status = ORDER_STATUS_IN_PROGRESS

    def _determine_priority(self, order: Order) -> None:
        """Sets the order priority based on its amount. Modifies order priority."""
        # We should define this constant in the constants module

        # Then use it here
        new_priority = ORDER_PRIORITY_HIGH if order.amount > ORDER_PRIORITY_THRESHOLD else ORDER_PRIORITY_LOW
        order.priority = new_priority
