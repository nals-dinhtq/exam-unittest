# # -*- coding: utf-8 -*-
# """
# Unit tests for the OrderProcessingService.
# """

# import logging
# import time
# import unittest
# from typing import Any, Dict, List, Tuple
# from unittest.mock import Mock, MagicMock, patch, call, ANY

# # Assume the classes are in a module named 'order_processor'
# # Adjust the import path as necessary
# from order_processing.order_processor import (
#     Order,
#     ProcessingResult,
#     DatabaseService,
#     APIClient,
#     CsvOrderExporter,  # Need to patch this class
#     OrderProcessingService,
#     DatabaseException,
#     APIException,
#     CsvExportException,
# )
# from order_processing.models import APIResponse

# # Disable logging noise from the module during tests,
# # except when specifically testing log output.
# logging.disable(logging.CRITICAL)
# # Re-enable logging if needed for specific tests using @patch or assertLogs
# # logging.disable(logging.NOTSET)

# # --- Constants ---
# TEST_USER_ID = 123
# # Example fixed timestamp (e.g., March 15, 2023 12:00:00 PM GMT)
# FIXED_TIMESTAMP = 1678886400


# class TestOrderProcessingService(unittest.TestCase):
#     """Test suite for the OrderProcessingService."""

#     mock_db_service: Mock
#     mock_api_client: Mock
#     mock_csv_exporter_instance: Mock
#     processor: OrderProcessingService

#     # Using patch decorators requires careful handling if setUp needs the patched object
#     # Patching within setUp or test methods is often clearer.

#     def setUp(self) -> None:
#         """Set up test fixtures, including mocks and the service instance."""
#         self.mock_db_service = MagicMock(spec=DatabaseService)
#         self.mock_api_client = MagicMock(spec=APIClient)

#         # Patch CsvOrderExporter *before* OrderProcessingService is instantiated
#         # so it uses the mocked class/instance. We patch the *class* and then
#         # can control the instance returned by its constructor.
#         patcher = patch('order_processor.CsvOrderExporter', autospec=True)
#         self.MockCsvExporterClass = patcher.start()
#         self.addCleanup(patcher.stop)  # Ensure patch stops after test

#         # Get the instance that would be created inside OrderProcessingService.__init__
#         self.mock_csv_exporter_instance = self.MockCsvExporterClass.return_value
#         # Default success
#         self.mock_csv_exporter_instance.export_orders.return_value = "fake_export.csv"

#         # Instantiate the service AFTER patching dependencies
#         self.processor = OrderProcessingService(
#             db_service=self.mock_db_service,
#             api_client=self.mock_api_client
#         )

#         # Default successful return values for mocks unless overridden in tests
#         self.mock_db_service.get_orders_by_user.return_value = []
#         self.mock_db_service.update_order_statuses.return_value = []  # No failures
#         self.mock_api_client.call_api.return_value = APIResponse(
#             status='success', data=100)

#     # --- Helper to create orders ---

#     def _create_order(self, id: int, o_type: str, amount: float, flag: bool,
#                       status: str = 'new', priority: str = 'low') -> Order:
#         """Creates a sample order instance."""
#         return Order(id=id, order_type=o_type, amount=amount, flag=flag,
#                      status=status, priority=priority)

#     # --- I. Initialization Tests ---

#     def test_should_initialize_successfully_when_valid_dependencies_provided(self) -> None:
#         """Verify successful instantiation with proper mock objects."""
#         # Arrange: Handled by setUp

#         # Act: Instantiation in setUp

#         # Assert: Check if dependencies are set (optional, setUp confirms this works)
#         self.assertIs(self.processor.db_service, self.mock_db_service)
#         self.assertIs(self.processor.api_client, self.mock_api_client)
#         self.assertIs(self.processor.exporter, self.mock_csv_exporter_instance)

#     def test_should_raise_typeerror_when_invalid_db_service_provided(self) -> None:
#         """Pass None or an object of the wrong type for db_service."""
#         with self.assertRaisesRegex(TypeError, "db_service must be an instance of DatabaseService"):
#             OrderProcessingService(
#                 db_service=None, api_client=self.mock_api_client)  # type: ignore
#         with self.assertRaisesRegex(TypeError, "db_service must be an instance of DatabaseService"):
#             OrderProcessingService(
#                 db_service=object(), api_client=self.mock_api_client)  # type: ignore

#     def test_should_raise_typeerror_when_invalid_api_client_provided(self) -> None:
#         """Pass None or an object of the wrong type for api_client."""
#         with self.assertRaisesRegex(TypeError, "api_client must be an instance of APIClient"):
#             OrderProcessingService(
#                 db_service=self.mock_db_service, api_client=None)  # type: ignore
#         with self.assertRaisesRegex(TypeError, "api_client must be an instance of APIClient"):
#             OrderProcessingService(
#                 db_service=self.mock_db_service, api_client=object())  # type: ignore

#     # --- II. Fetching Orders Tests ---

#     def test_should_return_success_with_zero_counts_when_no_orders_found(self) -> None:
#         """Test processing when get_orders_by_user returns an empty list."""
#         # Arrange
#         self.mock_db_service.get_orders_by_user.return_value = []

#         # Act
#         result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertEqual(result, ProcessingResult(
#             was_successful=True, processed_count=0, failed_orders=[]))
#         self.mock_db_service.get_orders_by_user.assert_called_once_with(
#             TEST_USER_ID)
#         self.mock_db_service.update_order_statuses.assert_not_called()
#         self.mock_csv_exporter_instance.export_orders.assert_not_called()
#         self.mock_api_client.call_api.assert_not_called()

#     def test_should_return_failure_when_get_orders_raises_db_exception(self) -> None:
#         """Test processing failure when database fetch fails."""
#         # Arrange
#         db_error_msg = "Connection lost"
#         self.mock_db_service.get_orders_by_user.side_effect = DatabaseException(
#             db_error_msg)

#         # Act
#         # Use assertLogs to check logging (optional but good)
#         with self.assertLogs(level='ERROR') as log_cm:
#             result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         expected_reason = f"DB Error fetching orders: {db_error_msg}"
#         self.assertEqual(result, ProcessingResult(
#             was_successful=False, processed_count=0, failed_orders=[(-1, expected_reason)]))
#         self.mock_db_service.get_orders_by_user.assert_called_once_with(
#             TEST_USER_ID)
#         self.mock_db_service.update_order_statuses.assert_not_called()
#         self.mock_csv_exporter_instance.export_orders.assert_not_called()
#         self.mock_api_client.call_api.assert_not_called()
#         # Check log message
#         self.assertIn(
#             f"Failed to retrieve orders for user {TEST_USER_ID}", log_cm.output[0])

#     # --- III. Single Order Processing Logic Tests ---

#     # Type A

#     # Patch time for deterministic filename check
#     @patch('time.time', return_value=FIXED_TIMESTAMP)
#     def test_should_mark_type_a_for_export_and_update_low_priority_when_amount_low(self, mock_time: Mock) -> None:
#         """Test Type A order with amount <= 200."""
#         # Arrange
#         order_a = self._create_order(
#             id=101, o_type='A', amount=50.0, flag=False)
#         self.mock_db_service.get_orders_by_user.return_value = [order_a]

#         # Act
#         result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertTrue(result.was_successful)
#         self.assertEqual(result.processed_count, 1)
#         self.assertEqual(result.failed_orders, [])

#         # Check exporter call
#         self.mock_csv_exporter_instance.export_orders.assert_called_once_with(
#             [order_a],  # Check if the correct order object was passed
#             TEST_USER_ID,
#             FIXED_TIMESTAMP
#         )

#         # Check DB update call (status='exported' set by exporter mock via object mutation)
#         self.mock_db_service.update_order_statuses.assert_called_once_with(
#             # Status set by exporter, priority by processor
#             [(101, 'exported', 'low')]
#         )

#     @patch('time.time', return_value=FIXED_TIMESTAMP)
#     def test_should_mark_type_a_for_export_and_update_high_priority_when_amount_high(self, mock_time: Mock) -> None:
#         """Test Type A order with amount > 200."""
#         # Arrange
#         order_a_high = self._create_order(
#             id=104, o_type='A', amount=250.0, flag=False)
#         self.mock_db_service.get_orders_by_user.return_value = [order_a_high]

#         # Act
#         result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertTrue(result.was_successful)
#         self.mock_csv_exporter_instance.export_orders.assert_called_once_with(
#             [order_a_high], TEST_USER_ID, FIXED_TIMESTAMP
#         )
#         self.mock_db_service.update_order_statuses.assert_called_once_with(
#             [(104, 'exported', 'high')]  # Priority updated
#         )

#     # Type B

#     def test_should_set_status_processed_when_type_b_api_success_data_high_amount_low(self) -> None:
#         """Test Type B -> processed status."""
#         # Arrange
#         order_b = self._create_order(
#             id=102, o_type='B', amount=80.0, flag=False)  # amount < 100
#         self.mock_db_service.get_orders_by_user.return_value = [order_b]
#         self.mock_api_client.call_api.return_value = APIResponse(
#             status='success', data=75)  # data >= 50

#         # Act
#         result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertTrue(result.was_successful)
#         self.mock_api_client.call_api.assert_called_once_with(102)
#         self.mock_db_service.update_order_statuses.assert_called_once_with(
#             [(102, 'processed', 'low')]
#         )

#     def test_should_set_status_pending_when_type_b_api_success_data_low(self) -> None:
#         """Test Type B -> pending status."""
#         # Arrange
#         order_b = self._create_order(
#             id=106, o_type='B', amount=90.0, flag=False)
#         self.mock_db_service.get_orders_by_user.return_value = [order_b]
#         self.mock_api_client.call_api.return_value = APIResponse(
#             status='success', data=30)  # data < 50

#         # Act
#         result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertTrue(result.was_successful)
#         self.mock_api_client.call_api.assert_called_once_with(106)
#         self.mock_db_service.update_order_statuses.assert_called_once_with(
#             [(106, 'pending', 'low')]
#         )

#     def test_should_set_status_review_required_when_type_b_api_success_data_high_amount_high(self) -> None:
#         """Test Type B -> review_required status."""
#         # Arrange
#         order_b = self._create_order(
#             id=109, o_type='B', amount=150.0, flag=False)  # amount >= 100
#         self.mock_db_service.get_orders_by_user.return_value = [order_b]
#         self.mock_api_client.call_api.return_value = APIResponse(
#             status='success', data=75)  # data >= 50

#         # Act
#         result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertTrue(result.was_successful)
#         self.mock_api_client.call_api.assert_called_once_with(109)
#         self.mock_db_service.update_order_statuses.assert_called_once_with(
#             [(109, 'review_required', 'low')]
#         )

#     def test_should_set_status_api_data_error_when_type_b_api_success_data_non_numeric(self) -> None:
#         """Test Type B -> api_data_error status."""
#         # Arrange
#         order_b = self._create_order(
#             id=111, o_type='B', amount=50.0, flag=False)
#         self.mock_db_service.get_orders_by_user.return_value = [order_b]
#         self.mock_api_client.call_api.return_value = APIResponse(
#             status='success', data='not-a-number')

#         # Act
#         with self.assertLogs(level='WARNING') as log_cm:
#             result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         # Still successful overall if DB update works
#         self.assertTrue(result.was_successful)
#         self.mock_api_client.call_api.assert_called_once_with(111)
#         self.mock_db_service.update_order_statuses.assert_called_once_with(
#             [(111, 'api_data_error', 'low')]
#         )
#         self.assertIn("is not numeric or convertible", log_cm.output[0])

#     def test_should_set_status_api_error_when_type_b_api_returns_error_status(self) -> None:
#         """Test Type B -> api_error status."""
#         # Arrange
#         order_b = self._create_order(
#             id=105, o_type='B', amount=120.0, flag=False)
#         self.mock_db_service.get_orders_by_user.return_value = [order_b]
#         self.mock_api_client.call_api.return_value = APIResponse(
#             status='failed', data={'msg': 'fail'})

#         # Act
#         with self.assertLogs(level='WARNING') as log_cm:
#             result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertTrue(result.was_successful)
#         self.mock_api_client.call_api.assert_called_once_with(105)
#         self.mock_db_service.update_order_statuses.assert_called_once_with(
#             [(105, 'api_error', 'low')]
#         )
#         self.assertIn("API returned status 'failed'", log_cm.output[0])

#     def test_should_set_status_api_failure_and_report_failure_when_type_b_api_raises_exception(self) -> None:
#         """Test Type B -> api_failure status and failed_orders report."""
#         # Arrange
#         order_b = self._create_order(
#             id=107, o_type='B', amount=50.0, flag=False)
#         api_error_msg = "Network Timeout"
#         self.mock_db_service.get_orders_by_user.return_value = [order_b]
#         self.mock_api_client.call_api.side_effect = APIException(api_error_msg)

#         # Act
#         with self.assertLogs(level='WARNING') as log_cm:
#             result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         # Overall failure because one order failed
#         self.assertFalse(result.was_successful)
#         # No successful updates attempted for this order
#         self.assertEqual(result.processed_count, 0)
#         self.assertEqual(result.failed_orders, [(107, api_error_msg)])
#         self.mock_api_client.call_api.assert_called_once_with(107)
#         # DB update IS called to persist the 'api_failure' status
#         self.mock_db_service.update_order_statuses.assert_called_once_with(
#             [(107, 'api_failure', 'low')]
#         )
#         self.assertIn(f"Failed to process order {107}", log_cm.output[0])

#     # Type C

#     def test_should_set_status_completed_when_type_c_and_flag_true(self) -> None:
#         """Test Type C -> completed status."""
#         # Arrange
#         order_c = self._create_order(
#             id=103, o_type='C', amount=250.0, flag=True)  # High priority
#         self.mock_db_service.get_orders_by_user.return_value = [order_c]

#         # Act
#         result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertTrue(result.was_successful)
#         self.mock_db_service.update_order_statuses.assert_called_once_with(
#             [(103, 'completed', 'high')]  # Priority updated too
#         )

#     def test_should_set_status_in_progress_when_type_c_and_flag_false(self) -> None:
#         """Test Type C -> in_progress status."""
#         # Arrange
#         order_c = self._create_order(
#             id=110, o_type='C', amount=10.0, flag=False)
#         self.mock_db_service.get_orders_by_user.return_value = [order_c]

#         # Act
#         result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertTrue(result.was_successful)
#         self.mock_db_service.update_order_statuses.assert_called_once_with(
#             [(110, 'in_progress', 'low')]
#         )

#     # Unknown Type

#     def test_should_set_status_unknown_type_when_order_type_not_abc(self) -> None:
#         """Test unknown order type handling."""
#         # Arrange
#         order_x = self._create_order(
#             id=108, o_type='X', amount=10.0, flag=False)
#         self.mock_db_service.get_orders_by_user.return_value = [order_x]

#         # Act
#         with self.assertLogs(level='WARNING') as log_cm:
#             result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertTrue(result.was_successful)
#         self.mock_db_service.update_order_statuses.assert_called_once_with(
#             [(108, 'unknown_type', 'low')]
#         )
#         self.assertIn(f"Unknown order type 'X'", log_cm.output[0])

#     # General Processing

#     def test_should_continue_processing_other_orders_when_one_order_fails_api_call(self) -> None:
#         """Test processing resilience when one order fails."""
#         # Arrange
#         order_ok = self._create_order(
#             id=103, o_type='C', amount=10, flag=True)  # Completed
#         order_fail = self._create_order(
#             id=107, o_type='B', amount=50, flag=False)  # API Exception
#         api_error_msg = "API Down"
#         self.mock_db_service.get_orders_by_user.return_value = [
#             order_ok, order_fail]
#         # Make call_api succeed for 103 (default mock) and fail for 107
#         self.mock_api_client.call_api.side_effect = lambda oid: \
#             APIException(api_error_msg) if oid == 107 else APIResponse(
#                 status='success', data=100)

#         # Act
#         result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertFalse(result.was_successful)
#         self.assertEqual(result.failed_orders, [(107, api_error_msg)])
#         # Check that DB update includes BOTH orders (one with success, one with failure status)
#         self.mock_db_service.update_order_statuses.assert_called_once_with(
#             [
#                 (103, 'completed', 'low'),
#                 (107, 'api_failure', 'low')
#             ]
#         )
#         # Only 1 successfully updated if DB works
#         self.assertEqual(result.processed_count, 1)

#     @patch.object(OrderProcessingService, '_determine_priority', side_effect=Exception("Unexpected error!"))
#     def test_should_report_failure_and_log_error_when_unexpected_exception_in_loop(self, mock_prio_fail: Mock) -> None:
#         """Test handling of unexpected errors during single order processing."""
#         # Arrange
#         # This one will cause exception
#         order1 = self._create_order(id=201, o_type='C', amount=10, flag=True)
#         # This should still process
#         order2 = self._create_order(id=202, o_type='C', amount=20, flag=False)
#         self.mock_db_service.get_orders_by_user.return_value = [order1, order2]

#         # Act
#         with self.assertLogs(level='ERROR') as log_cm:
#             result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertFalse(result.was_successful)
#         # Verify order1 failure is recorded
#         failed = [item for item in result.failed_orders if item[0] == 201]
#         self.assertEqual(len(failed), 1)
#         self.assertIn("Unexpected error: Unexpected error!", failed[0][1])
#         # Verify order2 was processed
#         updates = self.mock_db_service.update_order_statuses.call_args[0][0]
#         order1_update = next(
#             (item for item in updates if item[0] == 201), None)
#         order2_update = next(
#             (item for item in updates if item[0] == 202), None)

#         self.assertIsNotNone(order1_update)
#         # Status set on unexpected error
#         self.assertEqual(order1_update[1], 'processing_error')
#         self.assertIsNotNone(order2_update)
#         # Order 2 processed normally
#         self.assertEqual(order2_update[1], 'in_progress')

#         self.assertIn("Unexpected error processing order 201",
#                       log_cm.output[0])

#     def test_should_not_update_db_for_order_if_status_and_priority_unchanged(self) -> None:
#         """Test that unchanged orders are not sent to DB update."""
#         # Arrange
#         # This order starts as 'in_progress', 'low' and processing Type C, flag=False, amount=10 keeps it that way
#         order_unchanged = self._create_order(
#             id=301, o_type='C', amount=10, flag=False, status='in_progress', priority='low')
#         order_changed = self._create_order(
#             # -> completed, high
#             id=302, o_type='C', amount=250, flag=True, status='new', priority='low')
#         self.mock_db_service.get_orders_by_user.return_value = [
#             order_unchanged, order_changed]

#         # Act
#         result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertTrue(result.was_successful)
#         self.mock_db_service.update_order_statuses.assert_called_once_with(
#             [(302, 'completed', 'high')]  # Only the changed order is included
#         )

#     # --- IV. CSV Export Logic Tests ---

#     @patch('time.time', return_value=FIXED_TIMESTAMP)
#     def test_should_call_exporter_when_type_a_orders_exist(self, mock_time: Mock) -> None:
#         """Test exporter is called correctly when Type A orders are present."""
#         # Arrange
#         order_a1 = self._create_order(
#             id=101, o_type='A', amount=50, flag=False)
#         order_b = self._create_order(id=102, o_type='B', amount=80, flag=False)
#         order_a2 = self._create_order(
#             id=104, o_type='A', amount=160, flag=False)
#         self.mock_db_service.get_orders_by_user.return_value = [
#             order_a1, order_b, order_a2]

#         # Act
#         result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertTrue(result.was_successful)
#         # Check exporter call precisely
#         self.mock_csv_exporter_instance.export_orders.assert_called_once_with(
#             [order_a1, order_a2],  # Ensure ONLY type A orders are passed
#             TEST_USER_ID,
#             FIXED_TIMESTAMP
#         )
#         # Check DB update includes Type A orders with 'exported' status
#         updates = self.mock_db_service.update_order_statuses.call_args[0][0]
#         update_a1 = next((item for item in updates if item[0] == 101), None)
#         update_a2 = next((item for item in updates if item[0] == 104), None)
#         self.assertIsNotNone(update_a1)
#         self.assertEqual(update_a1[1], 'exported')
#         self.assertIsNotNone(update_a2)
#         self.assertEqual(update_a2[1], 'exported')

#     def test_should_not_call_exporter_when_no_type_a_orders_exist(self) -> None:
#         """Test exporter is not called if no Type A orders are present."""
#         # Arrange
#         order_b = self._create_order(id=102, o_type='B', amount=80, flag=False)
#         order_c = self._create_order(id=103, o_type='C', amount=10, flag=True)
#         self.mock_db_service.get_orders_by_user.return_value = [
#             order_b, order_c]

#         # Act
#         result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertTrue(result.was_successful)
#         self.mock_csv_exporter_instance.export_orders.assert_not_called()

#     @patch('time.time', return_value=FIXED_TIMESTAMP)
#     def test_should_set_status_export_failed_in_db_update_when_exporter_raises_exception(self, mock_time: Mock) -> None:
#         """Test handling when CSV exporter fails."""
#         # Arrange
#         order_a1 = self._create_order(
#             id=101, o_type='A', amount=50, flag=False)
#         order_a2 = self._create_order(
#             id=104, o_type='A', amount=160, flag=False)
#         order_b = self._create_order(
#             id=102, o_type='B', amount=80, flag=False)  # Should still process ok
#         export_error_msg = "Disk full"
#         self.mock_db_service.get_orders_by_user.return_value = [
#             order_a1, order_a2, order_b]
#         self.mock_csv_exporter_instance.export_orders.side_effect = CsvExportException(
#             export_error_msg)

#         # Act
#         with self.assertLogs(level='WARNING'):  # Exporter logs exception
#             result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         # Overall failure due to export error
#         self.assertFalse(result.was_successful)
#         self.mock_csv_exporter_instance.export_orders.assert_called_once()
#         # Check DB update includes Type A orders with 'export_failed' status
#         updates = self.mock_db_service.update_order_statuses.call_args[0][0]
#         update_a1 = next((item for item in updates if item[0] == 101), None)
#         update_a2 = next((item for item in updates if item[0] == 104), None)
#         # Check B processed
#         update_b = next((item for item in updates if item[0] == 102), None)

#         self.assertIsNotNone(update_a1)
#         self.assertEqual(update_a1[1], 'export_failed')
#         self.assertIsNotNone(update_a2)
#         self.assertEqual(update_a2[1], 'export_failed')
#         self.assertIsNotNone(update_b)
#         # B should still be processed
#         self.assertEqual(update_b[1], 'processed')

#         # Check failed orders list in result (the CsvExportException might not add to failed_orders list directly,
#         # but the was_successful=False indicates the problem. Let's check if the failed status is saved)
#         # If the design requires exporter errors to be in failed_orders, adjust processor logic.
#         # Current logic primarily logs and sets status. Asserting was_successful=False is key here.
#         # self.assertIn((101, export_error_msg), result.failed_orders) # Optional: if processor adds export errors

#     # --- V. Database Update Logic Tests ---

#     def test_should_call_update_statuses_with_correct_data_when_changes_exist(self) -> None:
#         """Test update_statuses is called with only changed orders."""
#         # Arrange
#         order_unchanged = self._create_order(
#             id=301, o_type='C', amount=10, flag=False, status='in_progress', priority='low')
#         order_changed_status = self._create_order(
#             id=302, o_type='C', amount=10, flag=True, status='new', priority='low')  # -> completed
#         order_changed_prio = self._create_order(
#             id=303, o_type='B', amount=250, flag=False, status='processed', priority='low')  # -> high
#         self.mock_db_service.get_orders_by_user.return_value = [
#             order_unchanged, order_changed_status, order_changed_prio]
#         # Assume API call for 303 is success, data high
#         self.mock_api_client.call_api.return_value = APIResponse(
#             status='success', data=100)

#         # Act
#         result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertTrue(result.was_successful)
#         self.mock_db_service.update_order_statuses.assert_called_once_with(
#             [
#                 (302, 'completed', 'low'),  # Status changed
#                 (303, 'review_required', 'high')  # Status and Priority changed
#             ]
#         )

#     def test_should_not_call_update_statuses_when_no_changes_occur(self) -> None:
#         """Test update_statuses not called if no orders change state."""
#         # Arrange
#         order_unchanged1 = self._create_order(
#             id=301, o_type='C', amount=10, flag=False, status='in_progress', priority='low')
#         order_unchanged2 = self._create_order(
#             id=302, o_type='A', amount=10, flag=False, status='exported', priority='low')
#         self.mock_db_service.get_orders_by_user.return_value = [
#             order_unchanged1, order_unchanged2]
#         # Mock exporter to "succeed" without changing status if needed (depends on exporter logic)
#         self.mock_csv_exporter_instance.export_orders.side_effect = lambda orders, uid, ts: [
#             setattr(o, 'status', 'exported') for o in orders]

#         # Act
#         result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         # Success even if nothing to update
#         self.assertTrue(result.was_successful)
#         # Processed, just no *change*
#         self.assertEqual(result.processed_count, 2)
#         self.mock_db_service.update_order_statuses.assert_not_called()

#     def test_should_report_partial_failure_when_update_statuses_returns_failed_ids(self) -> None:
#         """Test handling of partial DB update failures."""
#         # Arrange
#         order1 = self._create_order(
#             id=401, o_type='C', amount=10, flag=True)  # -> completed, low
#         # -> in_progress, high (DB fails this one)
#         order2 = self._create_order(id=402, o_type='C', amount=250, flag=False)
#         self.mock_db_service.get_orders_by_user.return_value = [order1, order2]
#         self.mock_db_service.update_order_statuses.return_value = [
#             402]  # Simulate failure for order 402

#         # Act
#         with self.assertLogs(level='WARNING') as log_cm:
#             result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertFalse(result.was_successful)
#         self.mock_db_service.update_order_statuses.assert_called_once_with(
#             [(401, 'completed', 'low'), (402, 'in_progress', 'high')]
#         )
#         # 2 attempted - 1 failed = 1
#         self.assertEqual(result.processed_count, 1)
#         self.assertEqual(result.failed_orders, [(402, "DB update failed")])
#         self.assertIn("Failed to update 1 orders in DB", log_cm.output[0])

#     def test_should_report_total_failure_when_update_statuses_raises_db_exception(self) -> None:
#         """Test handling when the entire DB bulk update fails."""
#         # Arrange
#         order1 = self._create_order(
#             id=401, o_type='C', amount=10, flag=True)  # -> completed, low
#         order2 = self._create_order(
#             id=402, o_type='C', amount=250, flag=False)  # -> in_progress, high
#         db_error_msg = "Transaction rolled back"
#         self.mock_db_service.get_orders_by_user.return_value = [order1, order2]
#         self.mock_db_service.update_order_statuses.side_effect = DatabaseException(
#             db_error_msg)
#         expected_updates = [(401, 'completed', 'low'),
#                             (402, 'in_progress', 'high')]

#         # Act
#         with self.assertLogs(level='ERROR') as log_cm:
#             result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertFalse(result.was_successful)
#         self.mock_db_service.update_order_statuses.assert_called_once_with(
#             expected_updates)
#         self.assertEqual(result.processed_count, 0)  # No updates succeeded
#         expected_fail_reason = f"DB Error during bulk update: {db_error_msg}"
#         # Check failed orders list contains all intended updates
#         self.assertCountEqual(result.failed_orders, [
#             (401, expected_fail_reason),
#             (402, expected_fail_reason)
#         ])
#         self.assertIn(
#             "Critical database error during bulk update", log_cm.output[0])

#     # --- VI. ProcessingResult Verification Tests ---
#     # Many aspects covered above, adding specific aggregate tests

#     def test_should_return_overall_success_true_when_all_steps_succeed(self) -> None:
#         """Test overall success when everything works."""
#         # Arrange (using pieces from previous tests)
#         order_a = self._create_order(
#             id=101, o_type='A', amount=50.0, flag=False)
#         order_b = self._create_order(
#             id=102, o_type='B', amount=80.0, flag=False)
#         order_c = self._create_order(
#             id=103, o_type='C', amount=10.0, flag=True)
#         self.mock_db_service.get_orders_by_user.return_value = [
#             order_a, order_b, order_c]
#         self.mock_api_client.call_api.return_value = APIResponse(
#             status='success', data=75)  # For order_b
#         # Exporter and DB update mocks default to success in setUp

#         # Act
#         result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertTrue(result.was_successful)
#         self.assertEqual(result.processed_count, 3)  # All 3 were updated
#         self.assertEqual(result.failed_orders, [])

#     def test_should_aggregate_all_failure_reasons_correctly_in_failed_orders(self) -> None:
#         """Test aggregation of multiple failure types in the result."""
#         # Arrange
#         order_api_fail = self._create_order(
#             id=107, o_type='B', amount=50, flag=False)  # API Exception
#         order_export_ok = self._create_order(
#             id=101, o_type='A', amount=50, flag=False)  # Export OK
#         order_db_fail = self._create_order(
#             id=402, o_type='C', amount=250, flag=False)  # DB Update Fail
#         order_ok = self._create_order(
#             id=103, o_type='C', amount=10, flag=True)  # OK

#         api_error_msg = "API Down"
#         db_fail_id = 402

#         self.mock_db_service.get_orders_by_user.return_value = [
#             order_api_fail, order_export_ok, order_db_fail, order_ok]
#         # API fails for 107
#         self.mock_api_client.call_api.side_effect = lambda oid: \
#             APIException(api_error_msg) if oid == 107 else APIResponse(
#                 status='success', data=100)
#         # Exporter succeeds (default mock)
#         # DB update fails for 402
#         self.mock_db_service.update_order_statuses.return_value = [db_fail_id]

#         # Act
#         result = self.processor.process_orders_for_user(TEST_USER_ID)

#         # Assert
#         self.assertFalse(result.was_successful)

#         # Expected updates attempted: (107, api_failure), (101, exported), (402, in_progress, high), (103, completed)
#         # Expected DB failures: 402
#         # Expected processing failures: 107
#         expected_failures = [
#             (107, api_error_msg),
#             (402, "DB update failed")
#         ]
#         # Use assertCountEqual for list comparison regardless of order
#         self.assertCountEqual(result.failed_orders, expected_failures)

#         # Processed count = (updates attempted) - (db failures) = 4 - 1 = 3
#         # Note: The definition of processed_count can be debated. Here it means "updates sent to DB that didn't fail at DB level".
#         # If API failure means it wasn't 'processed', the count would be 2. Let's stick to the code's apparent logic.
#         self.assertEqual(result.processed_count, 3)


# if __name__ == '__main__':
#     unittest.main(verbosity=2)

import pytest
import os
from unittest.mock import Mock, MagicMock, patch, mock_open, call
from typing import List, Dict, Tuple

from order_processing.order_processor import OrderProcessingService
from order_processing.models import Order, APIResponse, ProcessingResult
from order_processing.exceptions import DatabaseException, APIException, CsvExportException
from order_processing.interfaces import DatabaseService, APIClient


class TestOrderProcessingService:
    @pytest.fixture
    def db_service_mock(self) -> MagicMock:
        """Provides a mock DatabaseService."""
        mock = MagicMock(spec=DatabaseService, instance=True)
        mock.get_orders_by_user.return_value = []
        mock.update_order_statuses.return_value = []
        return mock

    @pytest.fixture
    def api_client_mock(self) -> MagicMock:
        """Provides a mock APIClient."""
        mock = MagicMock(spec=APIClient, instance=True)
        mock.call_api.return_value = APIResponse(status='success', data=100)
        return mock

    @pytest.fixture
    def service(self, db_service_mock: DatabaseService, api_client_mock: APIClient) -> OrderProcessingService:
        """Provides an instance of OrderProcessingService with mocks injected."""
        return OrderProcessingService(db_service=db_service_mock, api_client=api_client_mock)

    # === BASE CASE TESTS ===

    def test_should_return_successful_result_when_no_orders(self, service: OrderProcessingService, db_service_mock: MagicMock):
        # Arrange
        user_id = 1
        db_service_mock.get_orders_by_user.return_value = []

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert isinstance(result, ProcessingResult)
        assert result.was_successful is True
        assert result.processed_count == 0
        assert len(result.failed_orders) == 0
        db_service_mock.get_orders_by_user.assert_called_once_with(user_id)
        db_service_mock.update_order_statuses.assert_not_called()

    def test_should_return_successful_result_when_orders_processed_successfully(
        self, service: OrderProcessingService, db_service_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        orders = [
            Order(id=101, order_type='A', amount=50.0, flag=False),
            Order(id=102, order_type='B', amount=80.0, flag=False),
            Order(id=103, order_type='C', amount=50.0, flag=True)
        ]
        db_service_mock.get_orders_by_user.return_value = orders

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert result.was_successful is True
        assert result.processed_count == 3
        assert len(result.failed_orders) == 0

    # === TYPE A ORDER TESTS ===

    @patch('order_processing.services.exporters.open', new_callable=mock_open)
    @patch('order_processing.order_processor.time.time')
    def test_should_export_type_a_order_successfully(
        self,
        mock_time: MagicMock,
        mock_open_file: MagicMock,
        service: OrderProcessingService,
        db_service_mock: MagicMock
    ):
        # Arrange
        fixed_timestamp = 1234567890
        mock_time.return_value = fixed_timestamp
        user_id = 1
        order_a = Order(id=101, order_type='A', amount=100.0, flag=False)
        orders = [order_a]
        db_service_mock.get_orders_by_user.return_value = orders

        expected_filename = f'orders_type_A_{user_id}_{fixed_timestamp}.csv'
        expected_header = ['ID', 'Type', 'Amount',
                           'Flag', 'Status', 'Priority', 'Notes']
        expected_row = ['101', 'A', 100.0, 'false', 'exported', 'low', '']

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert result.was_successful is True
        assert result.processed_count == 1
        assert len(result.failed_orders) == 0

        mock_open_file.assert_called_once_with(
            expected_filename, 'w', newline='', encoding='utf-8')
        handle = mock_open_file()
        call_header = call().write(','.join(expected_header) + '\r\n')
        call_row = call().write(','.join(map(str, expected_row)) + '\r\n')
        assert call_header in handle.mock_calls
        assert call_row in handle.mock_calls

        db_service_mock.update_order_statuses.assert_called_once_with(
            [(101, 'exported', 'low')])
        assert order_a.status == 'exported'

    @patch('order_processing.services.exporters.open', new_callable=mock_open)
    @patch('order_processing.order_processor.time.time')
    def test_should_include_high_value_note_in_csv_when_amount_exceeds_150(
        self,
        mock_time: MagicMock,
        mock_open_file: MagicMock,
        service: OrderProcessingService,
        db_service_mock: MagicMock
    ):
        # Arrange
        fixed_timestamp = 1234567890
        mock_time.return_value = fixed_timestamp
        user_id = 1
        order_a = Order(id=101, order_type='A', amount=151.0, flag=False)
        orders = [order_a]
        db_service_mock.get_orders_by_user.return_value = orders

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert result.was_successful is True
        handle = mock_open_file()

        # The high value note should be in the Notes column for the row
        expected_row = ['101', 'A', 151.0, 'false',
                        'exported', 'low', 'High value order']
        call_row = call().write(','.join(map(str, expected_row)) + '\r\n')
        assert call_row in handle.mock_calls

    @patch('order_processing.services.exporters.open', new_callable=mock_open)
    @patch('order_processing.order_processor.time.time')
    def test_should_not_include_high_value_note_in_csv_when_amount_below_150(
        self,
        mock_time: MagicMock,
        mock_open_file: MagicMock,
        service: OrderProcessingService,
        db_service_mock: MagicMock
    ):
        # Arrange
        fixed_timestamp = 1234567890
        mock_time.return_value = fixed_timestamp
        user_id = 1
        order_a = Order(id=101, order_type='A', amount=150.0,
                        flag=False)  # Exactly 150
        orders = [order_a]
        db_service_mock.get_orders_by_user.return_value = orders

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert result.was_successful is True
        handle = mock_open_file()

        # No high value note should be present
        expected_row = ['101', 'A', 150.0, 'false', 'exported', 'low', '']
        unexpected_row = ['101', 'A', 150.0, 'false',
                          'exported', 'low', 'High value order']

        call_expected = call().write(','.join(map(str, expected_row)) + '\r\n')
        call_unexpected = call().write(','.join(map(str, unexpected_row)) + '\r\n')

        assert call_expected in handle.mock_calls
        assert call_unexpected not in handle.mock_calls

    @patch('order_processing.services.exporters.open')
    def test_should_set_status_to_export_failed_when_io_error_occurs(
        self,
        mock_open: MagicMock,
        service: OrderProcessingService,
        db_service_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order_a = Order(id=101, order_type='A', amount=100.0, flag=False)
        orders = [order_a]
        db_service_mock.get_orders_by_user.return_value = orders

        # Simulate an IOError when opening the file
        mock_open.side_effect = IOError("Simulated file write error")

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert not result.was_successful  # Should be False due to export failure
        assert order_a.status == 'export_failed'
        # The update to status=export_failed was processed
        assert result.processed_count == 1
        assert (101, "CSV export failed") in result.failed_orders

    # === TYPE B ORDER TESTS ===

    def test_should_call_api_for_type_b_order(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        api_client_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order_id = 102
        order_b = Order(id=order_id, order_type='B', amount=80.0, flag=False)
        orders = [order_b]
        db_service_mock.get_orders_by_user.return_value = orders

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert result.was_successful is True
        api_client_mock.call_api.assert_called_once_with(order_id)

    def test_should_set_status_to_processed_when_api_data_equals_50_and_amount_below_100(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        api_client_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order_b = Order(id=102, order_type='B', amount=80.0, flag=False)
        orders = [order_b]
        db_service_mock.get_orders_by_user.return_value = orders
        api_client_mock.call_api.return_value = APIResponse(
            status='success', data=50)  # Exactly 50

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert result.was_successful is True
        assert order_b.status == 'processed'

    def test_should_set_status_to_processed_when_api_data_above_50_and_amount_below_100(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        api_client_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order_b = Order(id=102, order_type='B', amount=80.0, flag=False)
        orders = [order_b]
        db_service_mock.get_orders_by_user.return_value = orders
        api_client_mock.call_api.return_value = APIResponse(
            status='success', data=75)  # Above 50

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert result.was_successful is True
        assert order_b.status == 'processed'

    def test_should_set_status_to_pending_when_api_data_below_50(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        api_client_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order_b = Order(id=102, order_type='B', amount=80.0, flag=False)
        orders = [order_b]
        db_service_mock.get_orders_by_user.return_value = orders
        api_client_mock.call_api.return_value = APIResponse(
            status='success', data=49)  # Below 50

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert result.was_successful is True
        assert order_b.status == 'pending'

    def test_should_set_status_to_review_required_when_api_data_above_50_and_amount_above_100(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        api_client_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order_b = Order(id=102, order_type='B', amount=150.0,
                        flag=False)  # Above 100
        orders = [order_b]
        db_service_mock.get_orders_by_user.return_value = orders
        api_client_mock.call_api.return_value = APIResponse(
            status='success', data=75)  # Above 50

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert result.was_successful is True
        assert order_b.status == 'review_required'

    def test_should_set_status_to_api_error_when_api_returns_failure(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        api_client_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order_b = Order(id=102, order_type='B', amount=80.0, flag=False)
        orders = [order_b]
        db_service_mock.get_orders_by_user.return_value = orders
        api_client_mock.call_api.return_value = APIResponse(
            status='error', data={'message': 'Invalid request'})

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert result.was_successful is True
        assert order_b.status == 'api_error'

    def test_should_set_status_to_api_failure_when_api_throws_exception(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        api_client_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order_b = Order(id=102, order_type='B', amount=80.0, flag=False)
        orders = [order_b]
        db_service_mock.get_orders_by_user.return_value = orders
        api_client_mock.call_api.side_effect = APIException(
            "Simulated API exception")

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert not result.was_successful  # Should be False because of the API exception
        assert order_b.status == 'api_failure'
        assert (102, "Simulated API exception") in result.failed_orders

    def test_should_handle_api_returning_non_numeric_data(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        api_client_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order_b = Order(id=102, order_type='B', amount=80.0, flag=False)
        orders = [order_b]
        db_service_mock.get_orders_by_user.return_value = orders
        api_client_mock.call_api.return_value = APIResponse(
            status='success', data="not-a-number")

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert result.was_successful is True
        # Per the implementation in order_processor.py
        assert order_b.status == 'api_data_error'

    # === TYPE C ORDER TESTS ===

    def test_should_set_status_to_completed_when_flag_is_true_for_type_c(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order_c = Order(id=103, order_type='C', amount=50.0, flag=True)
        orders = [order_c]
        db_service_mock.get_orders_by_user.return_value = orders

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert result.was_successful is True
        assert order_c.status == 'completed'

    def test_should_set_status_to_in_progress_when_flag_is_false_for_type_c(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order_c = Order(id=103, order_type='C', amount=50.0, flag=False)
        orders = [order_c]
        db_service_mock.get_orders_by_user.return_value = orders

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert result.was_successful is True
        assert order_c.status == 'in_progress'

    # === UNKNOWN ORDER TYPE TESTS ===

    def test_should_set_status_to_unknown_type_for_unsupported_order_type(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order_x = Order(id=108, order_type='X', amount=50.0,
                        flag=False)  # Unknown type
        orders = [order_x]
        db_service_mock.get_orders_by_user.return_value = orders

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert result.was_successful is True
        assert order_x.status == 'unknown_type'
        assert result.processed_count == 1
        db_service_mock.update_order_statuses.assert_called_once_with(
            [(108, 'unknown_type', 'low')])

    # === PRIORITY SETTING TESTS ===

    def test_should_set_high_priority_when_amount_exceeds_200(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order = Order(id=104, order_type='A', amount=201.0,
                      flag=False)  # Amount > 200
        orders = [order]
        db_service_mock.get_orders_by_user.return_value = orders

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert order.priority == 'high'

    def test_should_set_low_priority_when_amount_equals_200(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order = Order(id=104, order_type='A', amount=200.0,
                      flag=False)  # Exactly 200
        orders = [order]
        db_service_mock.get_orders_by_user.return_value = orders

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert order.priority == 'low'

    def test_should_set_low_priority_when_amount_below_200(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order = Order(id=104, order_type='A', amount=199.0,
                      flag=False)  # Below 200
        orders = [order]
        db_service_mock.get_orders_by_user.return_value = orders

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert order.priority == 'low'

    # === DATABASE UPDATE TESTS ===

    def test_should_call_update_order_statuses_with_correct_parameters(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order = Order(id=103, order_type='C', amount=50.0, flag=True)
        orders = [order]
        db_service_mock.get_orders_by_user.return_value = orders

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        db_service_mock.update_order_statuses.assert_called_once_with(
            [(103, 'completed', 'low')])
        assert result.processed_count == 1  # One successful DB update

    def test_should_mark_failed_orders_when_db_update_fails_for_some_orders(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order1 = Order(id=110, order_type='C', amount=50.0,
                       flag=True)  # Will fail in DB
        order2 = Order(id=111, order_type='C', amount=50.0,
                       flag=True)  # Will succeed
        orders = [order1, order2]
        db_service_mock.get_orders_by_user.return_value = orders

        # Simulate failure for order with ID 110
        db_service_mock.update_order_statuses.return_value = [
            110]  # Return the IDs that failed

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert not result.was_successful  # Overall result should be failure
        assert result.processed_count == 1  # Only one order was updated successfully
        # Verify the failed order is recorded
        assert (110, "DB update failed") in result.failed_orders
        db_service_mock.update_order_statuses.assert_called_once_with([
            (110, 'completed', 'low'),
            (111, 'completed', 'low')
        ])

    # === ERROR HANDLING TESTS ===

    def test_should_return_failure_result_when_db_get_orders_throws_exception(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        db_service_mock.get_orders_by_user.side_effect = DatabaseException(
            "Simulated DB fetch error")

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert not result.was_successful
        assert result.processed_count == 0
        assert (-1, "DB Error fetching orders: Simulated DB fetch error") in result.failed_orders

    def test_should_handle_db_exception_during_bulk_update(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order = Order(id=103, order_type='C', amount=50.0, flag=True)
        orders = [order]
        db_service_mock.get_orders_by_user.return_value = orders
        db_service_mock.update_order_statuses.side_effect = DatabaseException(
            "Simulated bulk update error")

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert not result.was_successful
        assert result.processed_count == 0
        assert (
            103, "DB Error during bulk update: Simulated bulk update error") in result.failed_orders

    def test_should_continue_processing_remaining_orders_when_one_order_fails(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        api_client_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order1 = Order(id=101, order_type='B', amount=80.0, flag=False)
        order2 = Order(id=102, order_type='A', amount=100.0, flag=False)
        order3 = Order(id=103, order_type='C', amount=50.0, flag=True)
        orders = [order1, order2, order3]
        db_service_mock.get_orders_by_user.return_value = orders

        # Make the API call for the first order fail
        def api_side_effect(order_id):
            if order_id == 101:
                raise APIException("Simulated API exception for order 101")
            return APIResponse(status='success', data=75)

        api_client_mock.call_api.side_effect = api_side_effect

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert not result.was_successful  # One failure means overall not successful
        assert result.processed_count == 2  # Two orders should still be processed
        assert (101, "Simulated API exception for order 101") in result.failed_orders
        assert order1.status == 'api_failure'
        assert order2.status == 'exported'
        assert order3.status == 'completed'

    # === EXTREME VALUE TESTS ===

    def test_should_handle_zero_order_amount(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order = Order(id=103, order_type='C', amount=0.0, flag=True)
        orders = [order]
        db_service_mock.get_orders_by_user.return_value = orders

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert result.was_successful is True
        assert order.priority == 'low'  # 0 < 200, so should be low
        assert order.status == 'completed'  # Type C with flag=True

    def test_should_handle_very_large_order_amount(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order = Order(id=103, order_type='C', amount=1000000.0, flag=True)
        orders = [order]
        db_service_mock.get_orders_by_user.return_value = orders

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert result.was_successful is True
        assert order.priority == 'high'  # 1000000 > 200, so should be high
        assert order.status == 'completed'  # Type C with flag=True

    def test_should_handle_negative_order_amount(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        order = Order(id=103, order_type='C', amount=-100.0, flag=True)
        orders = [order]
        db_service_mock.get_orders_by_user.return_value = orders

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert result.was_successful is True
        assert order.priority == 'low'  # -100 < 200, so should be low
        assert order.status == 'completed'  # Type C with flag=True

    # === MULTIPLE ORDERS TESTS ===

    def test_should_process_all_orders_when_multiple_orders_exist(
        self,
        service: OrderProcessingService,
        db_service_mock: MagicMock,
        api_client_mock: MagicMock
    ):
        # Arrange
        user_id = 1
        orders = [
            Order(id=101, order_type='A', amount=50.0, flag=False),
            Order(id=102, order_type='B', amount=80.0, flag=False),
            Order(id=103, order_type='C', amount=250.0,
                  flag=True),  # High priority due to amount
            Order(id=104, order_type='X', amount=10.0,
                  flag=False)   # Unknown type
        ]
        db_service_mock.get_orders_by_user.return_value = orders

        # Act
        result = service.process_orders_for_user(user_id)

        # Assert
        assert result.was_successful is True
        assert result.processed_count == 4

        # Check each order has correct status
        assert orders[0].status == 'exported'
        assert orders[1].status == 'processed'
        assert orders[2].status == 'completed'
        assert orders[3].status == 'unknown_type'

        # Check priorities
        assert orders[0].priority == 'low'
        assert orders[1].priority == 'low'
        assert orders[2].priority == 'high'  # Amount > 200
        assert orders[3].priority == 'low'
