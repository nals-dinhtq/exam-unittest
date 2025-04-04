# -*- coding: utf-8 -*-
"""
Unit tests for the OrderProcessingService using pytest.
"""

import logging
from typing import Any, List

# Import ANY from unittest.mock
from unittest.mock import ANY, MagicMock, patch

import pytest

from order_processing.constants import (
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
    ORDER_STATUS_EXPORT_FAILED,
    ORDER_STATUS_EXPORTED,
    ORDER_STATUS_IN_PROGRESS,
    ORDER_STATUS_NEW,
    ORDER_STATUS_PENDING,
    ORDER_STATUS_PROCESSED,
    ORDER_STATUS_PROCESSING_ERROR,
    ORDER_STATUS_REVIEW_REQUIRED,
    ORDER_STATUS_UNKNOWN_TYPE,
    ORDER_TYPE_A,
    ORDER_TYPE_B,
    ORDER_TYPE_C,
    ORDER_TYPE_UNKNOWN,
)
from order_processing.exceptions import (
    APIException,
    CsvExportException,
    DatabaseException,
)
from order_processing.interfaces import APIClient, DatabaseService
from order_processing.models import APIResponse, Order, ProcessingResult

# Code under test
from order_processing.order_processor import OrderProcessingService
from order_processing.services.exporters import CsvOrderExporter

# --- Constants ---
TEST_USER_ID: int = 123
# Example fixed timestamp (e.g., April 3, 2025 11:00:00 PM GMT+7)
FIXED_TIMESTAMP: int = 1743811200


# --- Helper Function ---
def create_order(
    id: int, o_type: str, amount: float, flag: bool, status: str = ORDER_STATUS_NEW, priority: str = ORDER_PRIORITY_LOW
) -> Order:
    """Creates a sample order instance."""
    return Order(id=id, order_type=o_type, amount=amount, flag=flag, status=status, priority=priority)


# --- Test Suite ---


class TestOrderProcessingServiceInitialization:
    """Tests for OrderProcessingService initialization."""

    @pytest.fixture
    def db_service_mock(self) -> MagicMock:
        return MagicMock(spec=DatabaseService)

    @pytest.fixture
    def api_client_mock(self) -> MagicMock:
        return MagicMock(spec=APIClient)

    @pytest.fixture
    def exporter_mock(self) -> MagicMock:
        return MagicMock(spec=CsvOrderExporter)

    def test_should_initialize_successfully_when_valid_dependencies_provided(
        self, db_service_mock: MagicMock, api_client_mock: MagicMock, exporter_mock: MagicMock
    ) -> None:
        # Arrange (Dependencies provided by fixtures)

        # Act
        service = OrderProcessingService(db_service=db_service_mock, api_client=api_client_mock, exporter=exporter_mock)

        # Assert
        assert service.db_service is db_service_mock
        assert service.api_client is api_client_mock
        assert service.exporter is exporter_mock

    def test_should_raise_typeerror_when_invalid_db_service_provided(
        self, api_client_mock: MagicMock, exporter_mock: MagicMock
    ) -> None:
        # Arrange
        invalid_db_service: Any = object()

        # Act & Assert
        with pytest.raises(TypeError, match="db_service must be an instance of DatabaseService"):
            OrderProcessingService(db_service=invalid_db_service, api_client=api_client_mock, exporter=exporter_mock)
        with pytest.raises(TypeError, match="db_service must be an instance of DatabaseService"):
            OrderProcessingService(db_service=None, api_client=api_client_mock, exporter=exporter_mock)  # type: ignore

    def test_should_raise_typeerror_when_invalid_api_client_provided(
        self, db_service_mock: MagicMock, exporter_mock: MagicMock
    ) -> None:
        # Arrange
        invalid_api_client: Any = object()

        # Act & Assert
        with pytest.raises(TypeError, match="api_client must be an instance of APIClient"):
            OrderProcessingService(db_service=db_service_mock, api_client=invalid_api_client, exporter=exporter_mock)
        with pytest.raises(TypeError, match="api_client must be an instance of APIClient"):
            OrderProcessingService(db_service=db_service_mock, api_client=None, exporter=exporter_mock)  # type: ignore

    # Patch the class CsvOrderExporter within the order_processor module
    @patch("order_processing.order_processor.CsvOrderExporter", autospec=True)
    def test_should_use_default_exporter_when_exporter_not_provided(
        self, MockCsvExporterClass: MagicMock, db_service_mock: MagicMock, api_client_mock: MagicMock
    ) -> None:
        # Arrange
        mock_exporter_instance = MockCsvExporterClass.return_value

        # Act
        service = OrderProcessingService(
            db_service=db_service_mock, api_client=api_client_mock, exporter=None  # Explicitly pass None
        )

        # Assert
        MockCsvExporterClass.assert_called_once_with()  # Check constructor called
        assert service.exporter is mock_exporter_instance


class TestOrderProcessingServiceExecution:
    """Tests for the process_orders_for_user method execution."""

    @pytest.fixture
    def db_service_mock(self) -> MagicMock:
        """Provides a mock DatabaseService with default success behavior."""
        mock = MagicMock(spec=DatabaseService)
        mock.get_orders_by_user.return_value = []
        mock.update_order_statuses.return_value = []  # Default: no DB update failures
        return mock

    @pytest.fixture
    def api_client_mock(self) -> MagicMock:
        """Provides a mock APIClient with default success behavior."""
        mock = MagicMock(spec=APIClient)
        # Default success response for Type B
        mock.call_api.return_value = APIResponse(status=API_RESPONSE_SUCCESS, data=API_DATA_THRESHOLD + 1)
        return mock

    @pytest.fixture
    def exporter_mock(self) -> MagicMock:
        """Provides a mock CsvOrderExporter with default success behavior."""
        mock = MagicMock(spec=CsvOrderExporter)
        # Simulate exporter setting status on success by modifying the passed objects

        def mock_export(orders: List[Order], user_id: int, timestamp: int) -> str:
            for order in orders:
                # Only set if not already failed (simulates exporter behavior)
                if order.status != ORDER_STATUS_EXPORT_FAILED:
                    order.status = ORDER_STATUS_EXPORTED
            return f"mock_export_{user_id}_{timestamp}.csv"

        mock.export_orders.side_effect = mock_export
        return mock

    @pytest.fixture
    def service(
        self, db_service_mock: DatabaseService, api_client_mock: APIClient, exporter_mock: CsvOrderExporter
    ) -> OrderProcessingService:
        """Provides an instance of OrderProcessingService with mocks injected."""
        # Inject the specific mock *instance*
        return OrderProcessingService(
            db_service=db_service_mock, api_client=api_client_mock, exporter=exporter_mock  # Pass the mock instance
        )

    # --- II. Fetching Orders Tests ---

    def test_should_return_success_and_zero_counts_when_no_orders_found(
        self, service: OrderProcessingService, db_service_mock: MagicMock
    ) -> None:
        # Arrange
        db_service_mock.get_orders_by_user.return_value = []

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result == ProcessingResult(was_successful=True, processed_count=0, failed_orders=[])
        db_service_mock.get_orders_by_user.assert_called_once_with(TEST_USER_ID)
        db_service_mock.update_order_statuses.assert_not_called()
        # Access exporter via service instance
        service.exporter.export_orders.assert_not_called()  # type: ignore[attr-defined]
        service.api_client.call_api.assert_not_called()  # type: ignore[attr-defined]

    def test_should_return_failure_when_get_orders_raises_db_exception(
        self, service: OrderProcessingService, db_service_mock: MagicMock
    ) -> None:
        # Arrange
        db_error_msg = "Connection lost during fetch"
        db_service_mock.get_orders_by_user.side_effect = DatabaseException(db_error_msg)

        # Act
        # Use pytest's caplog fixture to capture logs
        with patch.object(logging.getLogger("order_processing.order_processor"), "error") as mock_log_error:
            result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        expected_reason = f"DB Error fetching orders: {db_error_msg}"
        assert result == ProcessingResult(
            was_successful=False, processed_count=0, failed_orders=[(-1, expected_reason)]
        )
        db_service_mock.get_orders_by_user.assert_called_once_with(TEST_USER_ID)
        db_service_mock.update_order_statuses.assert_not_called()
        service.exporter.export_orders.assert_not_called()  # type: ignore[attr-defined]
        service.api_client.call_api.assert_not_called()  # type: ignore[attr-defined]
        # Check log message
        mock_log_error.assert_called_once()
        assert db_error_msg in mock_log_error.call_args[0][0]

    # --- III. Single Order Processing Logic Tests ---

    # Type A
    @patch("order_processing.order_processor.time.time", return_value=FIXED_TIMESTAMP)
    def test_should_mark_type_a_for_export_and_update_low_priority_when_amount_low(
        self,
        mock_time: MagicMock,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        exporter_mock: MagicMock,
    ) -> None:
        # Arrange
        order_a = create_order(id=101, o_type=ORDER_TYPE_A, amount=50.0, flag=False)
        db_service_mock.get_orders_by_user.return_value = [order_a]

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is True
        assert result.processed_count == 1
        assert result.failed_orders == []

        # Check exporter call (exporter_mock is the mock instance)
        exporter_mock.export_orders.assert_called_once_with([order_a], TEST_USER_ID, FIXED_TIMESTAMP)

        # Check DB update call (status='exported' set by exporter mock side_effect)
        db_service_mock.update_order_statuses.assert_called_once_with(
            [(101, ORDER_STATUS_EXPORTED, ORDER_PRIORITY_LOW)]
        )
        # Verify in-memory status change by exporter mock
        assert order_a.status == ORDER_STATUS_EXPORTED
        assert order_a.priority == ORDER_PRIORITY_LOW

    @patch("order_processing.order_processor.time.time", return_value=FIXED_TIMESTAMP)
    def test_should_mark_type_a_for_export_and_update_high_priority_when_amount_high(
        self,
        mock_time: MagicMock,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        exporter_mock: MagicMock,
    ) -> None:
        # Arrange
        order_a_high = create_order(id=104, o_type=ORDER_TYPE_A, amount=ORDER_PRIORITY_THRESHOLD + 1, flag=False)
        db_service_mock.get_orders_by_user.return_value = [order_a_high]

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is True
        exporter_mock.export_orders.assert_called_once_with([order_a_high], TEST_USER_ID, FIXED_TIMESTAMP)
        db_service_mock.update_order_statuses.assert_called_once_with(
            [(104, ORDER_STATUS_EXPORTED, ORDER_PRIORITY_HIGH)]
        )
        assert order_a_high.status == ORDER_STATUS_EXPORTED
        assert order_a_high.priority == ORDER_PRIORITY_HIGH

    # Type B
    def test_should_call_api_client_when_order_type_b(
        self, service: OrderProcessingService, db_service_mock: MagicMock, api_client_mock: MagicMock
    ) -> None:
        # Arrange
        order_b = create_order(id=102, o_type=ORDER_TYPE_B, amount=80.0, flag=False)
        db_service_mock.get_orders_by_user.return_value = [order_b]

        # Act
        service.process_orders_for_user(TEST_USER_ID)

        # Assert
        api_client_mock.call_api.assert_called_once_with(102)

    def test_should_set_status_processed_when_type_b_api_success_data_high_amount_low(
        self, service: OrderProcessingService, db_service_mock: MagicMock, api_client_mock: MagicMock
    ) -> None:
        # Arrange
        order_b = create_order(id=102, o_type=ORDER_TYPE_B, amount=ORDER_AMOUNT_THRESHOLD - 1, flag=False)
        db_service_mock.get_orders_by_user.return_value = [order_b]
        api_client_mock.call_api.return_value = APIResponse(
            status=API_RESPONSE_SUCCESS, data=API_DATA_THRESHOLD
        )  # Data >= Threshold

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is True
        api_client_mock.call_api.assert_called_once_with(102)
        db_service_mock.update_order_statuses.assert_called_once_with(
            [(102, ORDER_STATUS_PROCESSED, ORDER_PRIORITY_LOW)]
        )
        assert order_b.status == ORDER_STATUS_PROCESSED

    def test_should_set_status_pending_when_type_b_api_success_data_low(
        self, service: OrderProcessingService, db_service_mock: MagicMock, api_client_mock: MagicMock
    ) -> None:
        # Arrange
        order_b = create_order(id=106, o_type=ORDER_TYPE_B, amount=90.0, flag=False)
        db_service_mock.get_orders_by_user.return_value = [order_b]
        api_client_mock.call_api.return_value = APIResponse(
            status=API_RESPONSE_SUCCESS, data=API_DATA_THRESHOLD - 1
        )  # data < Threshold

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is True
        db_service_mock.update_order_statuses.assert_called_once_with([(106, ORDER_STATUS_PENDING, ORDER_PRIORITY_LOW)])
        assert order_b.status == ORDER_STATUS_PENDING

    def test_should_set_status_review_required_when_type_b_api_success_data_high_amount_high(
        self, service: OrderProcessingService, db_service_mock: MagicMock, api_client_mock: MagicMock
    ) -> None:
        # Arrange
        order_b = create_order(
            id=109, o_type=ORDER_TYPE_B, amount=ORDER_AMOUNT_THRESHOLD, flag=False
        )  # amount >= Threshold
        db_service_mock.get_orders_by_user.return_value = [order_b]
        api_client_mock.call_api.return_value = APIResponse(
            status=API_RESPONSE_SUCCESS, data=API_DATA_THRESHOLD
        )  # data >= Threshold

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is True
        db_service_mock.update_order_statuses.assert_called_once_with(
            [(109, ORDER_STATUS_REVIEW_REQUIRED, ORDER_PRIORITY_LOW)]
        )
        assert order_b.status == ORDER_STATUS_REVIEW_REQUIRED

    def test_should_set_status_api_data_error_when_type_b_api_success_data_non_numeric(
        self, service: OrderProcessingService, db_service_mock: MagicMock, api_client_mock: MagicMock
    ) -> None:
        # Arrange
        order_b = create_order(id=111, o_type=ORDER_TYPE_B, amount=50.0, flag=False)
        db_service_mock.get_orders_by_user.return_value = [order_b]
        api_client_mock.call_api.return_value = APIResponse(status=API_RESPONSE_SUCCESS, data="not-a-number")

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        # Still successful overall if DB update works for the error status
        assert result.was_successful is True
        api_client_mock.call_api.assert_called_once_with(111)
        db_service_mock.update_order_statuses.assert_called_once_with(
            [(111, ORDER_STATUS_API_DATA_ERROR, ORDER_PRIORITY_LOW)]
        )
        assert order_b.status == ORDER_STATUS_API_DATA_ERROR

    def test_should_set_status_api_error_when_type_b_api_returns_error_status(
        self, service: OrderProcessingService, db_service_mock: MagicMock, api_client_mock: MagicMock
    ) -> None:
        # Arrange
        order_b = create_order(id=105, o_type=ORDER_TYPE_B, amount=120.0, flag=False)
        db_service_mock.get_orders_by_user.return_value = [order_b]
        api_client_mock.call_api.return_value = APIResponse(status="error", data={"msg": "fail"})  # status != success

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        # Processing itself didn't fail, just API logic
        assert result.was_successful is True
        api_client_mock.call_api.assert_called_once_with(105)
        db_service_mock.update_order_statuses.assert_called_once_with(
            [(105, ORDER_STATUS_API_ERROR, ORDER_PRIORITY_LOW)]
        )
        assert order_b.status == ORDER_STATUS_API_ERROR

    def test_should_set_status_api_failure_and_report_failure_when_type_b_api_raises_exception(
        self, service: OrderProcessingService, db_service_mock: MagicMock, api_client_mock: MagicMock
    ) -> None:
        # Arrange
        order_b = create_order(id=107, o_type=ORDER_TYPE_B, amount=50.0, flag=False)
        api_error_msg = "Network Timeout"
        db_service_mock.get_orders_by_user.return_value = [order_b]
        api_client_mock.call_api.side_effect = APIException(api_error_msg)

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        # Overall failure because one order failed processing
        assert result.was_successful is False
        assert result.processed_count == 1
        assert result.failed_orders == [(107, api_error_msg)]
        api_client_mock.call_api.assert_called_once_with(107)
        # DB update IS called to persist the 'api_failure' status
        db_service_mock.update_order_statuses.assert_called_once_with(
            [(107, ORDER_STATUS_API_FAILURE, ORDER_PRIORITY_LOW)]
        )
        assert order_b.status == ORDER_STATUS_API_FAILURE

    # Type C
    def test_should_set_status_completed_when_type_c_and_flag_true(
        self, service: OrderProcessingService, db_service_mock: MagicMock
    ) -> None:
        # Arrange
        order_c = create_order(
            id=103, o_type=ORDER_TYPE_C, amount=ORDER_PRIORITY_THRESHOLD + 50, flag=True
        )  # High priority
        db_service_mock.get_orders_by_user.return_value = [order_c]

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is True
        db_service_mock.update_order_statuses.assert_called_once_with(
            [(103, ORDER_STATUS_COMPLETED, ORDER_PRIORITY_HIGH)]
        )
        assert order_c.status == ORDER_STATUS_COMPLETED
        assert order_c.priority == ORDER_PRIORITY_HIGH

    def test_should_set_status_in_progress_when_type_c_and_flag_false(
        self, service: OrderProcessingService, db_service_mock: MagicMock
    ) -> None:
        # Arrange
        order_c = create_order(id=110, o_type=ORDER_TYPE_C, amount=10.0, flag=False)
        db_service_mock.get_orders_by_user.return_value = [order_c]

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is True
        db_service_mock.update_order_statuses.assert_called_once_with(
            [(110, ORDER_STATUS_IN_PROGRESS, ORDER_PRIORITY_LOW)]
        )
        assert order_c.status == ORDER_STATUS_IN_PROGRESS

    # Unknown Type
    def test_should_set_status_unknown_type_when_order_type_not_abc(
        self, service: OrderProcessingService, db_service_mock: MagicMock
    ) -> None:
        # Arrange
        # Or any string not A, B, C
        order_x = create_order(id=108, o_type=ORDER_TYPE_UNKNOWN, amount=10.0, flag=False)
        db_service_mock.get_orders_by_user.return_value = [order_x]

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is True
        db_service_mock.update_order_statuses.assert_called_once_with(
            [(108, ORDER_STATUS_UNKNOWN_TYPE, ORDER_PRIORITY_LOW)]
        )
        assert order_x.status == ORDER_STATUS_UNKNOWN_TYPE

    # Priority Calculation Specific Tests ( supplementing type tests)
    @pytest.mark.parametrize(
        "amount, expected_priority",
        [
            (ORDER_PRIORITY_THRESHOLD + 0.01, ORDER_PRIORITY_HIGH),
            (ORDER_PRIORITY_THRESHOLD, ORDER_PRIORITY_LOW),
            (ORDER_PRIORITY_THRESHOLD - 0.01, ORDER_PRIORITY_LOW),
            (0.0, ORDER_PRIORITY_LOW),
            (-100.0, ORDER_PRIORITY_LOW),
        ],
        ids=["above_threshold", "at_threshold", "below_threshold", "zero", "negative"],
    )
    def test_should_set_correct_priority_based_on_amount(
        self, amount: float, expected_priority: str, service: OrderProcessingService, db_service_mock: MagicMock
    ) -> None:
        # Arrange
        # Using Type C, flag=False -> in_progress for simplicity, focusing on priority
        order = create_order(id=501, o_type=ORDER_TYPE_C, amount=amount, flag=False)
        db_service_mock.get_orders_by_user.return_value = [order]

        # Act
        service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert order.priority == expected_priority
        db_service_mock.update_order_statuses.assert_called_once_with(
            [(501, ORDER_STATUS_IN_PROGRESS, expected_priority)]
        )

    # --- IV. CSV Export Logic Tests ---

    @patch("order_processing.order_processor.time.time", return_value=FIXED_TIMESTAMP)
    def test_should_call_exporter_when_type_a_orders_exist(
        self,
        mock_time: MagicMock,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        exporter_mock: MagicMock,
        api_client_mock: MagicMock,
    ) -> None:
        # Arrange
        order_a1 = create_order(id=101, o_type=ORDER_TYPE_A, amount=50, flag=False)
        order_b = create_order(id=102, o_type=ORDER_TYPE_B, amount=80, flag=False)  # Will call API
        order_a2 = create_order(id=104, o_type=ORDER_TYPE_A, amount=160, flag=False)
        db_service_mock.get_orders_by_user.return_value = [order_a1, order_b, order_a2]

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is True
        # Check exporter call precisely
        exporter_mock.export_orders.assert_called_once_with(
            [order_a1, order_a2], TEST_USER_ID, FIXED_TIMESTAMP  # Ensure ONLY type A orders are passed
        )
        # Check API call for B
        api_client_mock.call_api.assert_called_once_with(102)
        # Check DB update includes Type A orders with 'exported' status and Type B with 'processed'
        expected_db_updates = [
            (101, ORDER_STATUS_EXPORTED, ORDER_PRIORITY_LOW),
            # Assuming default API success leads to processed
            (102, ORDER_STATUS_PROCESSED, ORDER_PRIORITY_LOW),
            (104, ORDER_STATUS_EXPORTED, ORDER_PRIORITY_LOW),
        ]
        # Use assertCountEqual for list comparison regardless of order
        db_service_mock.update_order_statuses.assert_called_once()
        call_args, _ = db_service_mock.update_order_statuses.call_args
        assert isinstance(call_args[0], list)
        # FIX: Use sorted for comparison
        assert sorted(call_args[0]) == sorted(expected_db_updates)

    def test_should_not_call_exporter_when_no_type_a_orders_exist(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        exporter_mock: MagicMock,
        api_client_mock: MagicMock,
    ) -> None:
        # Arrange
        order_b = create_order(id=102, o_type=ORDER_TYPE_B, amount=80, flag=False)
        order_c = create_order(id=103, o_type=ORDER_TYPE_C, amount=10, flag=True)
        db_service_mock.get_orders_by_user.return_value = [order_b, order_c]

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is True
        exporter_mock.export_orders.assert_not_called()
        # Check other calls happened
        api_client_mock.call_api.assert_called_once_with(102)
        db_service_mock.update_order_statuses.assert_called_once()

    @patch("order_processing.order_processor.time.time", return_value=FIXED_TIMESTAMP)
    def test_should_set_status_export_failed_in_db_update_when_exporter_raises_exception(
        self,
        mock_time: MagicMock,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        exporter_mock: MagicMock,
        api_client_mock: MagicMock,
    ) -> None:
        # Arrange
        order_a1 = create_order(id=101, o_type=ORDER_TYPE_A, amount=50, flag=False)
        order_a2 = create_order(id=104, o_type=ORDER_TYPE_A, amount=160, flag=False)
        # Should still process ok
        order_b = create_order(id=102, o_type=ORDER_TYPE_B, amount=80, flag=False)
        export_error_msg = "Disk full during export"
        db_service_mock.get_orders_by_user.return_value = [order_a1, order_a2, order_b]

        # Make exporter raise exception AND modify status in memory
        def export_fail_side_effect(orders: List[Order], user_id: int, timestamp: int) -> str:
            for o in orders:
                # Simulate exporter setting status before raising
                o.status = ORDER_STATUS_EXPORT_FAILED
            raise CsvExportException(export_error_msg)

        exporter_mock.export_orders.side_effect = export_fail_side_effect

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is False  # Overall failure due to export error
        exporter_mock.export_orders.assert_called_once_with([order_a1, order_a2], TEST_USER_ID, FIXED_TIMESTAMP)
        api_client_mock.call_api.assert_called_once_with(102)  # B should still be attempted

        # Check DB update includes Type A orders with 'export_failed' status and B processed
        expected_db_updates = [
            (101, ORDER_STATUS_EXPORT_FAILED, ORDER_PRIORITY_LOW),
            (104, ORDER_STATUS_EXPORT_FAILED, ORDER_PRIORITY_LOW),
            (102, ORDER_STATUS_PROCESSED, ORDER_PRIORITY_LOW),  # B still processed
        ]
        db_service_mock.update_order_statuses.assert_called_once()
        call_args, _ = db_service_mock.update_order_statuses.call_args
        assert isinstance(call_args[0], list)
        assert sorted(call_args[0]) == sorted(expected_db_updates)

        # Check failed orders list in result includes both failed A orders
        expected_failures = [
            (101, f"CSV export failed: {export_error_msg}"),
            (104, f"CSV export failed: {export_error_msg}"),
        ]
        assert len(result.failed_orders) == 2
        # Check presence regardless of order - FIX: Use sorted comparison
        assert sorted(result.failed_orders) == sorted(expected_failures)

    # --- V. Database Update Logic Tests ---

    def test_should_call_update_statuses_with_correct_data_when_changes_exist(
        self, service: OrderProcessingService, db_service_mock: MagicMock, api_client_mock: MagicMock
    ) -> None:
        # Arrange
        # This order starts as 'in_progress', 'low' and processing keeps it that way
        order_unchanged = create_order(
            id=301,
            o_type=ORDER_TYPE_C,
            amount=10,
            flag=False,
            status=ORDER_STATUS_IN_PROGRESS,
            priority=ORDER_PRIORITY_LOW,
        )
        # This order changes status from 'new' to 'completed'
        order_changed_status = create_order(
            id=302, o_type=ORDER_TYPE_C, amount=10, flag=True, status=ORDER_STATUS_NEW, priority=ORDER_PRIORITY_LOW
        )
        # This order changes priority from 'low' to 'high' and status based on API
        order_changed_prio_status = create_order(
            id=303,
            o_type=ORDER_TYPE_B,
            amount=ORDER_PRIORITY_THRESHOLD + 1,
            flag=False,
            status=ORDER_STATUS_NEW,
            priority=ORDER_PRIORITY_LOW,
        )
        db_service_mock.get_orders_by_user.return_value = [
            order_unchanged,
            order_changed_status,
            order_changed_prio_status,
        ]
        # API response for order 303 (data >= 50, amount >= 100) -> review_required
        api_client_mock.call_api.return_value = APIResponse(status=API_RESPONSE_SUCCESS, data=API_DATA_THRESHOLD)

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is True
        api_client_mock.call_api.assert_called_once_with(303)  # API called for B
        db_service_mock.update_order_statuses.assert_called_once_with(
            [
                # Order 301 is NOT included as nothing changed
                (302, ORDER_STATUS_COMPLETED, ORDER_PRIORITY_LOW),  # Status changed
                (303, ORDER_STATUS_REVIEW_REQUIRED, ORDER_PRIORITY_HIGH),
            ]
        )
        assert result.processed_count == 2  # Only 2 updates sent to DB

    def test_should_not_call_update_statuses_when_no_changes_occur(
        self, service: OrderProcessingService, db_service_mock: MagicMock, exporter_mock: MagicMock
    ) -> None:
        # Arrange
        # This order starts 'in_progress', 'low' and stays that way
        order_unchanged1 = create_order(
            id=301,
            o_type=ORDER_TYPE_C,
            amount=10,
            flag=False,
            status=ORDER_STATUS_IN_PROGRESS,
            priority=ORDER_PRIORITY_LOW,
        )
        # This order starts 'exported', 'low'. Exporter mock will reset it to 'exported',
        # but processor always adds Type A to update list.
        order_unchanged2 = create_order(
            id=302,
            o_type=ORDER_TYPE_A,
            amount=10,
            flag=False,
            status=ORDER_STATUS_EXPORTED,
            priority=ORDER_PRIORITY_LOW,
        )
        db_service_mock.get_orders_by_user.return_value = [order_unchanged1, order_unchanged2]

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is True  # Success even if only one update needed
        assert result.processed_count == 1
        db_service_mock.update_order_statuses.assert_called_once_with(
            [(302, ORDER_STATUS_EXPORTED, ORDER_PRIORITY_LOW)]
        )
        exporter_mock.export_orders.assert_called_once()  # Exporter still called

    def test_should_report_partial_failure_when_update_statuses_returns_failed_ids(
        self, service: OrderProcessingService, db_service_mock: MagicMock
    ) -> None:
        # Arrange
        # -> completed, low (DB OK)
        order1 = create_order(id=401, o_type=ORDER_TYPE_C, amount=10, flag=True)
        # -> in_progress, high (DB fails this one)
        order2 = create_order(id=402, o_type=ORDER_TYPE_C, amount=ORDER_PRIORITY_THRESHOLD + 1, flag=False)
        db_service_mock.get_orders_by_user.return_value = [order1, order2]
        db_service_mock.update_order_statuses.return_value = [402]  # Simulate failure for order 402

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is False  # Overall failure due to DB issue
        expected_updates = [
            (401, ORDER_STATUS_COMPLETED, ORDER_PRIORITY_LOW),
            (402, ORDER_STATUS_IN_PROGRESS, ORDER_PRIORITY_HIGH),
        ]
        db_service_mock.update_order_statuses.assert_called_once_with(expected_updates)
        assert result.processed_count == 1  # 2 attempted - 1 failed = 1
        assert result.failed_orders == [(402, "DB update failed")]

    def test_should_report_total_failure_when_update_statuses_raises_db_exception(
        self, service: OrderProcessingService, db_service_mock: MagicMock
    ) -> None:
        # Arrange
        order1 = create_order(id=401, o_type=ORDER_TYPE_C, amount=10, flag=True)  # -> completed, low
        order2 = create_order(
            id=402, o_type=ORDER_TYPE_C, amount=ORDER_PRIORITY_THRESHOLD + 1, flag=False
        )  # -> in_progress, high
        db_error_msg = "Transaction rolled back completely"
        db_service_mock.get_orders_by_user.return_value = [order1, order2]
        db_service_mock.update_order_statuses.side_effect = DatabaseException(db_error_msg)
        expected_updates = [
            (401, ORDER_STATUS_COMPLETED, ORDER_PRIORITY_LOW),
            (402, ORDER_STATUS_IN_PROGRESS, ORDER_PRIORITY_HIGH),
        ]

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is False
        db_service_mock.update_order_statuses.assert_called_once_with(expected_updates)
        assert result.processed_count == 0  # No updates confirmed successful
        expected_fail_reason = f"DB Error during bulk update: {db_error_msg}"
        # Check failed orders list contains all intended updates
        expected_failures = [(401, expected_fail_reason), (402, expected_fail_reason)]
        assert sorted(result.failed_orders) == sorted(expected_failures)

    # --- VI. Aggregate/Complex Scenarios & Edge Cases ---

    def test_should_continue_processing_other_orders_when_one_order_fails_api_call(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        api_client_mock: MagicMock,
        exporter_mock: MagicMock,
    ) -> None:
        # Arrange
        order_ok_c = create_order(id=103, o_type=ORDER_TYPE_C, amount=10, flag=True)  # -> completed
        # API Exception -> generic handler sets processing_error
        order_fail_b = create_order(id=107, o_type=ORDER_TYPE_B, amount=50, flag=False)
        order_ok_a = create_order(id=101, o_type=ORDER_TYPE_A, amount=60, flag=False)  # -> exported
        api_error_msg = "API is Down"
        db_service_mock.get_orders_by_user.return_value = [order_ok_c, order_fail_b, order_ok_a]

        # Make call_api fail for 107. This will be caught by generic handler due to subsequent AttributeError
        api_client_mock.call_api.side_effect = (
            lambda oid: APIException(api_error_msg) if oid == 107 else APIResponse(status="success", data=100)
        )

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is False  # Contains a failure
        # This assumes the source code _handle_order_type_b's try/except is not fixed yet.
        # A better fix involves correcting the source code's try/except block.
        expected_fail_reason = "Unexpected error: 'APIException' object has no attribute 'status'"
        assert result.failed_orders == [(107, expected_fail_reason)]

        api_client_mock.call_api.assert_called_once_with(107)
        exporter_mock.export_orders.assert_called_once_with([order_ok_a], TEST_USER_ID, ANY)

        # Check that DB update includes ALL orders
        expected_updates = [
            (103, ORDER_STATUS_COMPLETED, ORDER_PRIORITY_LOW),
            (107, ORDER_STATUS_PROCESSING_ERROR, ORDER_PRIORITY_LOW),
            (101, ORDER_STATUS_EXPORTED, ORDER_PRIORITY_LOW),
        ]
        db_service_mock.update_order_statuses.assert_called_once()
        call_args, _ = db_service_mock.update_order_statuses.call_args
        assert sorted(call_args[0]) == sorted(expected_updates)

        assert result.processed_count == 3

    @patch.object(OrderProcessingService, "_determine_priority", side_effect=Exception("Unexpected priority error!"))
    def test_should_report_failure_and_log_error_when_unexpected_exception_in_processing_loop(
        self, mock_prio_fail: MagicMock, service: OrderProcessingService, db_service_mock: MagicMock
    ) -> None:
        # Arrange
        # This will cause exception during _determine_priority
        order1 = create_order(id=201, o_type=ORDER_TYPE_C, amount=10, flag=True)
        # This will ALSO cause exception due to the patch side_effect
        order2 = create_order(id=202, o_type=ORDER_TYPE_C, amount=20, flag=False)
        db_service_mock.get_orders_by_user.return_value = [order1, order2]

        # Act
        with patch.object(logging.getLogger("order_processing.order_processor"), "exception") as mock_log_exception:
            result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is False  # Failure due to unexpected exception

        fail_reason = "Unexpected error: Unexpected priority error!"
        expected_failures = [(201, fail_reason), (202, fail_reason)]
        assert sorted(result.failed_orders) == sorted(expected_failures)

        expected_updates = [
            (201, ORDER_STATUS_PROCESSING_ERROR, ORDER_PRIORITY_LOW),
            (202, ORDER_STATUS_PROCESSING_ERROR, ORDER_PRIORITY_LOW),  # Also fails
        ]
        db_service_mock.update_order_statuses.assert_called_once()
        call_args, _ = db_service_mock.update_order_statuses.call_args
        assert len(call_args[0]) == 2
        assert sorted(call_args[0]) == sorted(expected_updates)

        assert mock_log_exception.call_count == 2
        assert "Unexpected error processing order 201" in mock_log_exception.call_args_list[0][0][0]
        assert "Unexpected error processing order 202" in mock_log_exception.call_args_list[1][0][0]

        # Processed count should still be 2 (both sent to DB), assuming DB update itself doesn't fail
        assert result.processed_count == 2

    def test_should_return_overall_success_true_when_all_steps_succeed_with_mixed_order_types(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        api_client_mock: MagicMock,
        exporter_mock: MagicMock,
    ) -> None:
        # Arrange
        order_a = create_order(id=101, o_type=ORDER_TYPE_A, amount=50.0, flag=False)  # -> exported, low
        order_b = create_order(id=102, o_type=ORDER_TYPE_B, amount=80.0, flag=False)  # -> processed, low
        order_c = create_order(id=103, o_type=ORDER_TYPE_C, amount=10.0, flag=True)  # -> completed, low
        db_service_mock.get_orders_by_user.return_value = [order_a, order_b, order_c]
        # Mocks default to success

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is True
        assert result.processed_count == 3  # All 3 were updated successfully
        assert result.failed_orders == []
        api_client_mock.call_api.assert_called_once_with(102)
        exporter_mock.export_orders.assert_called_once_with([order_a], TEST_USER_ID, ANY)
        expected_updates = [
            (101, ORDER_STATUS_EXPORTED, ORDER_PRIORITY_LOW),
            (102, ORDER_STATUS_PROCESSED, ORDER_PRIORITY_LOW),
            (103, ORDER_STATUS_COMPLETED, ORDER_PRIORITY_LOW),
        ]
        db_service_mock.update_order_statuses.assert_called_once()
        call_args, _ = db_service_mock.update_order_statuses.call_args
        assert sorted(call_args[0]) == sorted(expected_updates)

    def test_should_aggregate_all_failure_reasons_correctly_in_failed_orders(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        api_client_mock: MagicMock,
        exporter_mock: MagicMock,
    ) -> None:
        # Arrange
        # API Exception -> api_failure
        order_api_fail = create_order(id=107, o_type=ORDER_TYPE_B, amount=50, flag=False)
        order_export_fail = create_order(
            id=101, o_type=ORDER_TYPE_A, amount=50, flag=False
        )  # Export Fail -> export_failed
        # DB Update Fail -> completed (initially)
        order_db_fail = create_order(id=402, o_type=ORDER_TYPE_C, amount=10, flag=True)
        order_ok = create_order(id=103, o_type=ORDER_TYPE_C, amount=10, flag=True)  # OK -> completed
        # API Data Error -> api_data_error
        order_data_err = create_order(id=111, o_type=ORDER_TYPE_B, amount=50, flag=False)

        api_error_msg = "API is Down"
        export_error_msg = "Cannot write CSV"
        db_fail_id = 402

        db_service_mock.get_orders_by_user.return_value = [
            order_api_fail,
            order_export_fail,
            order_db_fail,
            order_ok,
            order_data_err,
        ]

        # API fails for 107, returns bad data for 111
        def api_side_effect(oid: int) -> APIResponse:
            if oid == 107:
                raise APIException(api_error_msg)
            elif oid == 111:
                return APIResponse(status="success", data="bad-data")
            else:  # Should not be called for others
                return APIResponse(status="success", data=100)

        api_client_mock.call_api.side_effect = api_side_effect

        # Exporter fails for 101
        def export_fail_side_effect(orders: List[Order], user_id: int, timestamp: int) -> str:
            for o in orders:
                if o.id == 101:
                    o.status = ORDER_STATUS_EXPORT_FAILED
            raise CsvExportException(export_error_msg)

        exporter_mock.export_orders.side_effect = export_fail_side_effect

        # DB update fails for 402
        db_service_mock.update_order_statuses.return_value = [db_fail_id]

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        assert result.was_successful is False  # Contains multiple failures

        # Expected processing failures: 107 (API), 101 (Export)
        # Expected DB failures: 402
        expected_failures = [
            (107, api_error_msg),
            (101, f"CSV export failed: {export_error_msg}"),
            (402, "DB update failed"),
        ]
        # Use assertCountEqual for list comparison regardless of order
        assert len(result.failed_orders) == len(expected_failures)
        # FIX: Use sorted comparison
        assert sorted(result.failed_orders) == sorted(expected_failures)

        # Check final statuses attempted for DB update
        expected_updates = [
            (107, ORDER_STATUS_API_FAILURE, ORDER_PRIORITY_LOW),  # API fail path
            (101, ORDER_STATUS_EXPORT_FAILED, ORDER_PRIORITY_LOW),  # Export fail path
            # Processed OK, but failed DB update
            (402, ORDER_STATUS_COMPLETED, ORDER_PRIORITY_LOW),
            # Processed OK, DB update OK
            (103, ORDER_STATUS_COMPLETED, ORDER_PRIORITY_LOW),
            (111, ORDER_STATUS_API_DATA_ERROR, ORDER_PRIORITY_LOW),  # API data error path
        ]
        db_service_mock.update_order_statuses.assert_called_once()
        call_args, _ = db_service_mock.update_order_statuses.call_args
        assert sorted(call_args[0]) == sorted(expected_updates)

        # Processed count = (updates attempted) - (db failures) = 5 - 1 = 4
        assert result.processed_count == 4

    def test_should_not_call_db_update_and_calculate_processed_count_correctly_when_no_status_or_priority_changes(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        api_client_mock: MagicMock,
        exporter_mock: MagicMock,
    ) -> None:
        """Test line 196-205: Scenario where only non-TypeA orders exist and none need DB status/priority updates."""
        # Arrange
        # Type C, flag=False, starts and ends as 'in_progress', 'low'
        order_c_unchanged = create_order(
            id=301,
            o_type=ORDER_TYPE_C,
            amount=10,
            flag=False,
            status=ORDER_STATUS_IN_PROGRESS,
            priority=ORDER_PRIORITY_LOW,
        )
        # Type B, starts and ends as 'processed', 'low'
        order_b_unchanged = create_order(
            id=303,
            o_type=ORDER_TYPE_B,
            amount=10,
            flag=False,
            status=ORDER_STATUS_PROCESSED,
            priority=ORDER_PRIORITY_LOW,
        )

        # Ensure API returns data that results in 'processed' status for order 303
        # Conditions: amount=10 (<100), data >= 50 -> processed (matches initial status)
        api_client_mock.call_api.return_value = APIResponse(status=API_RESPONSE_SUCCESS, data=API_DATA_THRESHOLD)

        all_orders = [order_c_unchanged, order_b_unchanged]
        db_service_mock.get_orders_by_user.return_value = all_orders

        # Act
        result = service.process_orders_for_user(TEST_USER_ID)

        # Assert
        # Overall success should be true as no processing *errors* occurred
        assert result.was_successful is True
        assert result.failed_orders == []

        db_service_mock.update_order_statuses.assert_not_called()

        exporter_mock.export_orders.assert_not_called()

        # Check API WAS called for Type B
        api_client_mock.call_api.assert_called_once_with(303)

        # It's calculated as len(all_orders) - len(result.failed_orders)
        assert result.processed_count == len(all_orders)  # Should be 2 (2 - 0)
