# -*- coding: utf-8 -*-
"""
Unit tests for the CsvOrderExporter static methods.
"""

import logging
from typing import List
from unittest.mock import ANY, MagicMock, call, mock_open, patch

import pytest

from order_processing.constants import (
    HIGH_PRIORITY_THRESHOLD,
    HIGH_VALUE_ORDERS,
    ORDER_PRIORITY_HIGH,
    ORDER_PRIORITY_LOW,
    ORDER_STATUS_EXPORT_FAILED,
    ORDER_STATUS_EXPORTED,
    ORDER_STATUS_NEW,
)
from order_processing.models import Order
from order_processing.services.exporters import CsvExportException, CsvOrderExporter

# --- Test Data ---
TEST_USER_ID_EXPORTER = 987
TEST_TIMESTAMP_EXPORTER = 1743811300
# --- Helper ---


def create_exporter_order(id: int, amount: float, flag: bool, priority: str = ORDER_PRIORITY_LOW) -> Order:
    """Helper to create orders specifically for exporter tests."""
    # Exporter expects Type A, status might be 'new' initially
    return Order(
        id=id,
        order_type="A",  # Assuming exporter only handles type A as per filename
        amount=amount,
        flag=flag,
        status=ORDER_STATUS_NEW,  # Start with a non-exported status
        priority=priority,
    )


class TestCsvOrderExporter:
    """Tests for the CsvOrderExporter.export_orders static method."""

    def test_should_return_empty_string_and_log_info_when_orders_list_is_empty(self, caplog) -> None:  # type: ignore[no-untyped-def]
        # Arrange
        empty_orders: List[Order] = []
        caplog.set_level(logging.INFO)  # Ensure INFO logs are captured

        # Act
        result = CsvOrderExporter.export_orders(empty_orders, TEST_USER_ID_EXPORTER, TEST_TIMESTAMP_EXPORTER)

        # Assert
        assert result == ""
        assert "No orders of type A provided to export." in caplog.text

    @patch("order_processing.services.exporters.open", new_callable=mock_open)
    @patch("order_processing.services.exporters.csv.writer")
    def test_should_create_csv_write_header_and_one_row_and_update_status_when_single_order_provided(
        self, mock_csv_writer: MagicMock, mock_file_open: MagicMock, caplog
    ) -> None:  # type: ignore[no-untyped-def]
        """Test successful export with a single, standard order."""
        # Arrange
        order = create_exporter_order(id=1, amount=100.0, flag=False)
        orders = [order]
        expected_filename = f"orders_type_A_{TEST_USER_ID_EXPORTER}_{TEST_TIMESTAMP_EXPORTER}.csv"
        mock_writer_instance = mock_csv_writer.return_value
        caplog.set_level(logging.INFO)

        # Act

        result = CsvOrderExporter.export_orders(orders, TEST_USER_ID_EXPORTER, TEST_TIMESTAMP_EXPORTER)

        # Assert
        assert result == expected_filename
        mock_file_open.assert_called_once_with(expected_filename, "w", newline="", encoding="utf-8")
        mock_csv_writer.assert_called_once_with(mock_file_open.return_value)

        # Check header and row calls
        expected_header = ["ID", "Type", "Amount", "Flag", "Status", "Priority", "Notes"]
        expected_row_data = [1, "A", 100.0, "false", ORDER_STATUS_EXPORTED, ORDER_PRIORITY_LOW, ""]
        assert mock_writer_instance.writerow.call_count == 2
        mock_writer_instance.writerow.assert_has_calls([call(expected_header), call(expected_row_data)])

        # Check order status updated in memory
        assert order.status == ORDER_STATUS_EXPORTED
        assert f"Exporting 1 orders to {expected_filename}" in caplog.text
        assert f"Successfully exported 1 orders to {expected_filename}" in caplog.text

    @patch("order_processing.services.exporters.open", new_callable=mock_open)
    @patch("order_processing.services.exporters.csv.writer")
    def test_should_create_csv_write_header_and_multiple_rows_and_update_statuses_when_multiple_orders_provided(
        self, mock_csv_writer: MagicMock, mock_file_open: MagicMock
    ) -> None:
        """Test successful export with multiple orders."""
        # Arrange
        order1 = create_exporter_order(id=10, amount=50.0, flag=True)
        order2 = create_exporter_order(
            id=20, amount=200.0, flag=False, priority=ORDER_PRIORITY_HIGH
        )  # Priority already high
        orders = [order1, order2]
        expected_filename = f"orders_type_A_{TEST_USER_ID_EXPORTER}_{TEST_TIMESTAMP_EXPORTER}.csv"
        mock_writer_instance = mock_csv_writer.return_value

        # Act
        result = CsvOrderExporter.export_orders(orders, TEST_USER_ID_EXPORTER, TEST_TIMESTAMP_EXPORTER)

        # Assert
        assert result == expected_filename
        mock_file_open.assert_called_once_with(expected_filename, "w", newline="", encoding="utf-8")

        # Check header and row calls
        expected_header = ["ID", "Type", "Amount", "Flag", "Status", "Priority", "Notes"]
        expected_row1_data = [10, "A", 50.0, "true", ORDER_STATUS_EXPORTED, ORDER_PRIORITY_LOW, ""]
        expected_row2_data = [20, "A", 200.0, "false", ORDER_STATUS_EXPORTED, ORDER_PRIORITY_HIGH, HIGH_VALUE_ORDERS]
        assert mock_writer_instance.writerow.call_count == 3
        mock_writer_instance.writerow.assert_has_calls(
            [call(expected_header), call(expected_row1_data), call(expected_row2_data)], any_order=False
        )

        # Check order statuses updated in memory
        assert order1.status == ORDER_STATUS_EXPORTED
        assert order2.status == ORDER_STATUS_EXPORTED

    @patch("order_processing.services.exporters.open", new_callable=mock_open)
    @patch("order_processing.services.exporters.csv.writer")
    def test_should_include_high_value_note_when_amount_exceeds_threshold(
        self, mock_csv_writer: MagicMock, mock_file_open: MagicMock
    ) -> None:
        # Arrange
        order_high_value = create_exporter_order(id=30, amount=HIGH_PRIORITY_THRESHOLD + 0.01, flag=False)
        orders = [order_high_value]
        mock_writer_instance = mock_csv_writer.return_value

        # Act
        CsvOrderExporter.export_orders(orders, TEST_USER_ID_EXPORTER, TEST_TIMESTAMP_EXPORTER)

        # Assert
        expected_row_data = [
            30,
            "A",
            HIGH_PRIORITY_THRESHOLD + 0.01,
            "false",
            ORDER_STATUS_EXPORTED,
            ORDER_PRIORITY_LOW,
            HIGH_VALUE_ORDERS,
        ]  # Note added
        # Check the second call to writerow (the data row)
        mock_writer_instance.writerow.assert_called_with(expected_row_data)
        assert order_high_value.status == ORDER_STATUS_EXPORTED

    @patch("order_processing.services.exporters.open", new_callable=mock_open)
    @patch("order_processing.services.exporters.csv.writer")
    def test_should_not_include_high_value_note_when_amount_at_or_below_threshold(
        self, mock_csv_writer: MagicMock, mock_file_open: MagicMock
    ) -> None:
        # Arrange
        order_at_threshold = create_exporter_order(id=40, amount=HIGH_PRIORITY_THRESHOLD, flag=False)
        order_below_threshold = create_exporter_order(id=41, amount=HIGH_PRIORITY_THRESHOLD - 1, flag=True)
        orders = [order_at_threshold, order_below_threshold]
        mock_writer_instance = mock_csv_writer.return_value

        # Act
        CsvOrderExporter.export_orders(orders, TEST_USER_ID_EXPORTER, TEST_TIMESTAMP_EXPORTER)

        # Assert
        expected_row1_data = [
            40,
            "A",
            HIGH_PRIORITY_THRESHOLD,
            "false",
            ORDER_STATUS_EXPORTED,
            ORDER_PRIORITY_LOW,
            "",
        ]  # Note empty
        expected_row2_data = [
            41,
            "A",
            HIGH_PRIORITY_THRESHOLD - 1,
            "true",
            ORDER_STATUS_EXPORTED,
            ORDER_PRIORITY_LOW,
            "",
        ]  # Note empty

        assert mock_writer_instance.writerow.call_count == 3  # Header + 2 rows
        mock_writer_instance.writerow.assert_has_calls(
            [call(ANY), call(expected_row1_data), call(expected_row2_data)]  # Header
        )
        assert order_at_threshold.status == ORDER_STATUS_EXPORTED
        assert order_below_threshold.status == ORDER_STATUS_EXPORTED

    @patch("order_processing.services.exporters.open", new_callable=mock_open)
    @patch("order_processing.services.exporters.csv.writer")
    def test_should_write_flag_as_lowercase_string(self, mock_csv_writer: MagicMock, mock_file_open: MagicMock) -> None:
        # Arrange
        order_flag_true = create_exporter_order(id=50, amount=10, flag=True)
        order_flag_false = create_exporter_order(id=51, amount=10, flag=False)
        orders = [order_flag_true, order_flag_false]
        mock_writer_instance = mock_csv_writer.return_value

        # Act
        CsvOrderExporter.export_orders(orders, TEST_USER_ID_EXPORTER, TEST_TIMESTAMP_EXPORTER)

        # Assert
        expected_row1_data = [50, "A", 10, "true", ORDER_STATUS_EXPORTED, ORDER_PRIORITY_LOW, ""]  # 'true'
        expected_row2_data = [51, "A", 10, "false", ORDER_STATUS_EXPORTED, ORDER_PRIORITY_LOW, ""]  # 'false'

        # Check the data row calls
        mock_writer_instance.writerow.assert_has_calls(
            [call(ANY), call(expected_row1_data), call(expected_row2_data)]  # Header
        )

    @patch("order_processing.services.exporters.open")
    def test_should_raise_csv_export_exception_log_exception_and_set_status_failed_when_ioerror_on_open(
        self, mock_file_open: MagicMock, caplog
    ) -> None:  # type: ignore[no-untyped-def]
        # Arrange
        order = create_exporter_order(id=60, amount=100.0, flag=False)
        orders = [order]
        io_error_message = "Permission denied"
        mock_file_open.side_effect = IOError(io_error_message)
        expected_filename = f"orders_type_A_{TEST_USER_ID_EXPORTER}_{TEST_TIMESTAMP_EXPORTER}.csv"
        # Capture ERROR level and above (exception logs)
        caplog.set_level(logging.ERROR)

        # Act & Assert
        with pytest.raises(CsvExportException) as exc_info:
            CsvOrderExporter.export_orders(orders, TEST_USER_ID_EXPORTER, TEST_TIMESTAMP_EXPORTER)

        # Check exception details
        assert f"IOError exporting to {expected_filename}: {io_error_message}" in str(exc_info.value)
        # Check that the original IOError is chained
        assert isinstance(exc_info.value.__cause__, IOError)

        # Check log message
        assert f"Failed to write CSV file {expected_filename}" in caplog.text
        # Check that exception info was logged
        assert io_error_message in caplog.text
        # Check if traceback was included by log.exception
        assert "Traceback" in caplog.text

        # Check order status updated in memory (should be marked failed in this case)
        # The logic checks 'if order.id not in successfully_exported_ids' - set is empty here
        assert order.status == ORDER_STATUS_EXPORT_FAILED

    @patch("order_processing.services.exporters.open", new_callable=mock_open)
    @patch("order_processing.services.exporters.csv.writer")
    def test_should_raise_csv_export_exception_log_exception_and_set_status_failed_when_ioerror_on_write(
        self, mock_csv_writer: MagicMock, mock_file_open: MagicMock, caplog
    ) -> None:
        # Arrange
        order1 = create_exporter_order(id=70, amount=50.0, flag=False)
        # Error occurs writing this one
        order2 = create_exporter_order(id=71, amount=60.0, flag=True)
        order3 = create_exporter_order(id=72, amount=70.0, flag=False)  # This won't be written
        orders = [order1, order2, order3]

        io_error_message = "Disk full during write"
        mock_writer_instance = mock_csv_writer.return_value

        # Simulate IOError on the *third* call to writerow (Header, Row1 OK, Row2 fails)
        write_call_count = 0

        def write_side_effect(*args) -> None:
            nonlocal write_call_count
            write_call_count += 1
            if write_call_count == 3:  # Fail on writing order2's row
                # Simulate adding order1 ID before error
                # This relies on accessing successfully_exported_ids, which isn't directly possible here.
                # Instead, we will check the final status based on the code logic.
                raise IOError(io_error_message)
            # Default behavior (no return needed for writerow)

        mock_writer_instance.writerow.side_effect = write_side_effect

        expected_filename = f"orders_type_A_{TEST_USER_ID_EXPORTER}_{TEST_TIMESTAMP_EXPORTER}.csv"
        caplog.set_level(logging.ERROR)

        # Act & Assert
        with pytest.raises(CsvExportException) as exc_info:
            CsvOrderExporter.export_orders(orders, TEST_USER_ID_EXPORTER, TEST_TIMESTAMP_EXPORTER)

        # Check exception details
        assert f"IOError exporting to {expected_filename}: {io_error_message}" in str(exc_info.value)
        assert isinstance(exc_info.value.__cause__, IOError)

        # Check log message
        assert f"Failed to write CSV file {expected_filename}" in caplog.text
        assert io_error_message in caplog.text
        assert "Traceback" in caplog.text

        # Check order statuses updated in memory
        # The loop adds IDs to successfully_exported_ids *after* writerow succeeds.
        # When writerow fails for order2(id=71), successfully_exported_ids only contains 70.
        # The except block then iterates:
        # - order1(id=70): 70 IS in successfully_exported_ids (implicitly, if write succeeded), status not changed.
        # - order2(id=71): 71 is NOT in successfully_exported_ids, status set to export_failed.
        # - order3(id=72): 72 is NOT in successfully_exported_ids, status set to export_failed.
        # Status remains NEW as it was "successful" but error occurred after
        assert order1.status == ORDER_STATUS_NEW
        # Failed during its write attempt
        assert order2.status == ORDER_STATUS_EXPORT_FAILED
        assert order3.status == ORDER_STATUS_EXPORT_FAILED
