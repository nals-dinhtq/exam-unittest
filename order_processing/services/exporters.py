# -*- coding: utf-8 -*-
"""
Utility classes/functions for exporting data, e.g., to CSV.
"""
import csv
import logging
import time
from typing import List

# Use relative imports
from ..models import Order
from ..exceptions import CsvExportException

log = logging.getLogger(__name__)


class CsvOrderExporter:
    """Handles exporting orders to a CSV file. Adheres to SRP."""

    @staticmethod
    def export_orders(
        orders: List[Order], user_id: int, timestamp: int
    ) -> str:
        """
        Exports a list of orders to a uniquely named CSV file.
        Updates the status of successfully exported orders *in memory*.

        Args:
            orders: The list of Order objects to export.
            user_id: The user ID, used for naming the file.
            timestamp: A Unix timestamp, used for naming the file.

        Returns:
            The filename of the generated CSV file if successful.

        Raises:
            CsvExportException: If an IOError occurs during file writing.
                                Orders will be marked as 'export_failed' in memory.
        """
        if not orders:
            log.info("No orders of type A provided to export.")
            return ""  # Or handle as appropriate, maybe return None

        csv_file = f'orders_type_A_{user_id}_{timestamp}.csv'
        log.info(f"Exporting {len(orders)} orders to {csv_file}")

        successfully_exported_ids = set()
        try:
            with open(csv_file, 'w', newline='', encoding='utf-8') as file_handle:
                writer = csv.writer(file_handle)
                # Write Header
                writer.writerow(
                    ['ID', 'Type', 'Amount', 'Flag', 'Status', 'Priority', 'Notes']
                )

                # Write Order Rows
                for order in orders:
                    # Use the already determined priority
                    priority_to_write = order.priority
                    notes = 'High value order' if order.amount > 150 else ''
                    status_to_write = 'exported'  # Intended status on success

                    writer.writerow([
                        order.id,
                        order.order_type,
                        order.amount,
                        str(order.flag).lower(),
                        status_to_write,
                        priority_to_write,
                        notes
                    ])
                    successfully_exported_ids.add(order.id)

            log.info(
                f"Successfully exported {len(successfully_exported_ids)} orders to {csv_file}")

            # Update status IN MEMORY for successfully exported orders
            for order in orders:
                if order.id in successfully_exported_ids:
                    order.status = 'exported'
            return csv_file

        except IOError as e:
            log.exception(f"Failed to write CSV file {csv_file}")
            # Mark relevant orders as failed IN MEMORY. DB update handles persistence.
            for order in orders:
                # Only mark those that weren't successfully written before the error
                # (though with 'w' mode, usually it's all or nothing unless interrupted)
                if order.id not in successfully_exported_ids:
                    order.status = 'export_failed'
            raise CsvExportException(
                f"IOError exporting to {csv_file}: {e}") from e
