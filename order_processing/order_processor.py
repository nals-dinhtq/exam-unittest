
# -*- coding: utf-8 -*-
"""
Contains the main OrderProcessingService logic for orchestrating order processing.
"""
import logging
import time
from typing import List, Tuple, Dict

# Use relative imports
from .interfaces import DatabaseService, APIClient
from .models import Order, ProcessingResult
from .exceptions import (
    OrderProcessingException, DatabaseException, APIException, CsvExportException
)
from .services.exporters import CsvOrderExporter  # Import the concrete exporter

log = logging.getLogger(__name__)


class OrderProcessingService:
    """
    Orchestrates the processing of orders for a user.

    Uses dependency injection for database and API interactions,
    adhering to DIP and OCP.
    """

    def __init__(self, db_service: DatabaseService, api_client: APIClient):
        """
        Initializes the service with necessary dependencies.

        Args:
            db_service: An instance of a DatabaseService implementation.
            api_client: An instance of an APIClient implementation.
        """
        if not isinstance(db_service, DatabaseService):
            raise TypeError(
                "db_service must be an instance of DatabaseService")
        if not isinstance(api_client, APIClient):
            raise TypeError("api_client must be an instance of APIClient")

        self.db_service = db_service
        self.api_client = api_client
        # Exporter could also be injected if more flexibility is needed
        self.exporter = CsvOrderExporter()

    def process_orders_for_user(self, user_id: int) -> ProcessingResult:
        """
        Fetches and processes all orders for a given user.

        Handles different order types, updates status/priority,
        exports type 'A' orders, and persists changes to the database.

        Args:
            user_id: The ID of the user whose orders need processing.

        Returns:
            A ProcessingResult object summarizing the outcome.
        """
        log.info(f"Starting order processing for user_id: {user_id}")
        result = ProcessingResult(was_successful=False)  # Default to failure
        # Use dict to easily update status later
        orders_to_update_in_db: Dict[int, Tuple[int, str, str]] = {}
        orders_type_a: List[Order] = []

        try:
            # Fetch original orders
            orders = self.db_service.get_orders_by_user(user_id)
        except DatabaseException as e:
            log.exception(f"Failed to retrieve orders for user {user_id}")
            result.failed_orders.append((-1, f"DB Error fetching orders: {e}"))
            return result  # Cannot proceed without orders

        if not orders:
            log.info(
                f"No orders found for user {user_id}. Processing finished.")
            result.was_successful = True  # No orders is not a failure state
            return result

        timestamp = int(time.time())  # Use consistent timestamp for batch

        # --- Stage 1: Process each order and determine initial target state ---
        for order in orders:
            original_status = order.status
            original_priority = order.priority
            try:
                # Determine Status based on Type
                # Modifies order status in memory
                self._process_single_order(order)

                # Determine Priority (runs for all types after status is set)
                # Modifies order priority in memory
                self._determine_priority(order)

                # Collect orders for specific actions
                if order.order_type == 'A':
                    # Mark Type A orders for export; exporter will set final status
                    orders_type_a.append(order)
                    # Initially mark for update with current state, exporter corrects later
                    if order.status != original_status or order.priority != original_priority:
                        orders_to_update_in_db[order.id] = (
                            order.id, order.status, order.priority)

                # Add to update list ONLY if status or priority changed from original DB state
                # Or if it failed processing (status changed to an error state)
                elif order.status != original_status or order.priority != original_priority:
                    orders_to_update_in_db[order.id] = (
                        order.id, order.status, order.priority)
                else:
                    log.debug(
                        f"Order {order.id}: No change in status/priority during initial processing.")

            # Catch expected processing errors per order
            except (APIException, CsvExportException) as e:
                log.warning(f"Failed to process order {order.id}: {e}")
                result.failed_orders.append((order.id, str(e)))
                # The status (e.g., 'api_failure') was set inside the handler
                # Ensure this failed state is persisted if it changed
                if order.status != original_status or order.priority != original_priority:
                    orders_to_update_in_db[order.id] = (
                        order.id, order.status, order.priority)

            except Exception as e:  # Catch unexpected errors during single order processing
                log.exception(f"Unexpected error processing order {order.id}")
                result.failed_orders.append(
                    (order.id, f"Unexpected error: {e}"))
                # Mark with generic error status for DB update attempt
                order.status = 'processing_error'
                # Ensure this failed state is persisted if it changed
                if order.status != original_status or order.priority != original_priority:
                    orders_to_update_in_db[order.id] = (
                        order.id, order.status, order.priority)

        # --- Stage 2: Perform side effects (CSV Export for Type A) ---
        if orders_type_a:
            try:
                # Exporter modifies status of orders in orders_type_a list
                # to 'exported' or 'export_failed'
                self.exporter.export_orders(orders_type_a, user_id, timestamp)

                # Update the DB update list with the final status from the exporter
                for order_a in orders_type_a:
                    log.debug(
                        f"Order {order_a.id} (Type A): Final status after export attempt: {order_a.status}")
                    # Always update Type A orders in DB after export attempt, regardless of status change
                    orders_to_update_in_db[order_a.id] = (
                        order_a.id, order_a.status, order_a.priority)
                    # If export failed, record it in results
                    if order_a.status == 'export_failed':
                        # Avoid duplicating if already failed for another reason
                        if not any(f[0] == order_a.id for f in result.failed_orders):
                            result.failed_orders.append(
                                (order_a.id, "CSV export failed"))

            except CsvExportException as e:
                # Error already logged by exporter. Exporter marked orders as 'export_failed'.
                log.error(f"CSV Export process failed for user {user_id}: {e}")
                # Update the DB update list for ALL orders intended for export
                for order_a in orders_type_a:
                    orders_to_update_in_db[order_a.id] = (
                        order_a.id, order_a.status, order_a.priority)
                    # Ensure failure is recorded
                    if not any(f[0] == order_a.id for f in result.failed_orders):
                        result.failed_orders.append(
                            (order_a.id, f"CSV export failed: {e}"))

        # --- Stage 3: Persist changes to Database ---
        final_updates_list = list(orders_to_update_in_db.values())
        if not final_updates_list:
            log.info("No order statuses or priorities needed updating in DB.")
            # Success if no processing errors occurred
            result.was_successful = not result.failed_orders
            # Processed count is total orders minus failed ones (as nothing needed DB update)
            result.processed_count = len(orders) - len(result.failed_orders)
            return result

        try:
            failed_update_ids = self.db_service.update_order_statuses(
                final_updates_list)

            processed_in_db = len(final_updates_list) - len(failed_update_ids)
            result.processed_count = processed_in_db

            if not failed_update_ids:
                log.info(
                    f"Successfully updated {processed_in_db} orders in DB.")
                # Overall success depends on whether *any* processing/DB errors occurred
                result.was_successful = not result.failed_orders
            else:
                log.warning(
                    f"Failed to update {len(failed_update_ids)} orders in DB.")
                result.was_successful = False  # Mark overall as failure due to DB issues
                # Add DB update failures to the result list, avoiding duplicates
                for order_id in failed_update_ids:
                    if not any(f[0] == order_id for f in result.failed_orders):
                        result.failed_orders.append(
                            (order_id, "DB update failed"))

        except DatabaseException as e:
            log.exception("Critical database error during bulk update.")
            result.was_successful = False
            result.processed_count = 0  # No updates confirmed
            # Add all orders intended for update as failed due to DB error, avoiding duplicates
            for order_id, _, _ in final_updates_list:
                if not any(f[0] == order_id for f in result.failed_orders):
                    result.failed_orders.append(
                        (order_id, f"DB Error during bulk update: {e}"))

        log.info(
            f"Order processing finished for user {user_id}. Result: {result}")
        return result

    # --- Private Helper Methods (SRP, Clean Code) ---

    def _process_single_order(self, order: Order) -> None:
        """Determines the status of a single order based on its type. Modifies order status."""
        if order.order_type == 'A':
            self._handle_order_type_a(order)
        elif order.order_type == 'B':
            self._handle_order_type_b(order)
        elif order.order_type == 'C':
            self._handle_order_type_c(order)
        else:
            log.warning(
                f"Order {order.id}: Unknown order type '{order.order_type}'.")
            order.status = 'unknown_type'

    def _handle_order_type_a(self, order: Order) -> None:
        """Handles logic specific to Type A orders (marks for export)."""
        log.debug(
            f"Order {order.id}: Type A identified. Status will be set by exporter.")
        # Status remains 'new' or current state until exporter runs.
        # Exporter will set it to 'exported' or 'export_failed'.
        pass

    def _handle_order_type_b(self, order: Order) -> None:
        """Handles logic specific to Type B orders (API call). Modifies order status."""
        log.debug(f"Order {order.id}: Type B - Calling API.")
        try:
            api_response = self.api_client.call_api(order.id)

            if api_response.status == 'success':
                api_data = api_response.data
                try:
                    # Attempt conversion/check if data is numeric-like
                    if isinstance(api_data, (int, float)):
                        numeric_api_data = api_data
                    else:
                        # Try converting if it looks like a number string, else fail
                        numeric_api_data = float(api_data)

                    # --- Apply Business Logic ---
                    if numeric_api_data >= 50 and order.amount < 100:
                        order.status = 'processed'
                        log.debug(
                            f"Order {order.id}: Type B - Set to 'processed'.")
                    elif numeric_api_data < 50:
                        order.status = 'pending'
                        log.debug(
                            f"Order {order.id}: Type B - Set to 'pending'.")
                    else:  # Case: numeric_api_data >= 50 AND order.amount >= 100
                        order.status = 'review_required'
                        log.info(
                            f"Order {order.id}: Type B - Requires review (data>=50, amount>=100). Set to 'review_required'.")

                except (ValueError, TypeError):
                    log.warning(
                        f"Order {order.id}: API success response data ('{api_data}') is not numeric or convertible.")
                    order.status = 'api_data_error'

            else:  # API call was made, but reported a non-success status
                log.warning(
                    f"Order {order.id}: API returned status '{api_response.status}'.")
                order.status = 'api_error'

        except APIException as e:
            # Logged by caller loop, just set status
            # Debug level sufficient here
            log.debug(f"Order {order.id}: API call failed: {e}")
            order.status = 'api_failure'
            raise  # Re-raise for the main loop's error handling/result tracking

    def _handle_order_type_c(self, order: Order) -> None:
        """Handles logic specific to Type C orders. Modifies order status."""
        log.debug(f"Order {order.id}: Type C - Setting status based on flag.")
        if order.flag:
            order.status = 'completed'
        else:
            order.status = 'in_progress'

    def _determine_priority(self, order: Order) -> None:
        """Sets the order priority based on its amount. Modifies order priority."""
        new_priority = 'high' if order.amount > 200 else 'low'
        if order.priority != new_priority:
            log.debug(
                f"Order {order.id}: Setting priority to {new_priority} (amount={order.amount}).")
            order.priority = new_priority
