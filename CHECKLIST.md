# Unit Test Checklist

## CsvOrderExporter Tests (`test_csv_exporter.py`)

- [ ] **test_should_return_empty_string_and_log_info_when_orders_list_is_empty**
  - Arrange: Provide an empty list of `Order` objects to the exporter.
  - Act: Call `CsvOrderExporter.export_orders`.
  - Assert: Returns an empty string, logs an informational message.

- [ ] **test_should_create_csv_write_header_and_one_row_and_update_status_when_single_order_provided**
  - Arrange: Provide a list containing a single `Order` object. Mock `open` and `csv.writer`.
  - Act: Call `CsvOrderExporter.export_orders`.
  - Assert: Creates a CSV file, writes the correct header and data row, updates the order's status to `ORDER_STATUS_EXPORTED` in memory, returns the correct filename.

- [ ] **test_should_create_csv_write_header_and_multiple_rows_and_update_statuses_when_multiple_orders_provided**
  - Arrange: Provide a list containing multiple `Order` objects. Mock `open` and `csv.writer`.
  - Act: Call `CsvOrderExporter.export_orders`.
  - Assert: Creates a CSV file, writes the correct header and data rows for all orders, updates all orders' statuses to `ORDER_STATUS_EXPORTED` in memory, returns the correct filename.

- [ ] **test_should_include_high_value_note_when_amount_exceeds_threshold**
  - Arrange: Provide an `Order` list where one order's `amount` is greater than `HIGH_PRIORITY_THRESHOLD`. Mock `open` and `csv.writer`.
  - Act: Call `CsvOrderExporter.export_orders`.
  - Assert: The CSV row for the high-value order includes the `HIGH_VALUE_ORDERS` constant in the 'Notes' column.

- [ ] **test_should_not_include_high_value_note_when_amount_at_or_below_threshold**
  - Arrange: Provide an `Order` list where order `amount`s are less than or equal to `HIGH_PRIORITY_THRESHOLD`. Mock `open` and `csv.writer`.
  - Act: Call `CsvOrderExporter.export_orders`.
  - Assert: The CSV rows for these orders have an empty string in the 'Notes' column.

- [ ] **test_should_write_flag_as_lowercase_string**
  - Arrange: Provide `Order` objects with `flag` set to `True` and `False`. Mock `open` and `csv.writer`.
  - Act: Call `CsvOrderExporter.export_orders`.
  - Assert: The 'Flag' column in the CSV contains the lowercase strings 'true' and 'false' respectively.

- [ ] **test_should_raise_csv_export_exception_log_exception_and_set_status_failed_when_ioerror_on_open**
  - Arrange: Provide an `Order` list. Mock `open` to raise an `IOError`.
  - Act: Call `CsvOrderExporter.export_orders`.
  - Assert: Raises `CsvExportException`, logs the exception details, updates the order's status to `ORDER_STATUS_EXPORT_FAILED` in memory.

- [ ] **test_should_raise_csv_export_exception_log_exception_and_set_status_failed_when_ioerror_on_write**
  - Arrange: Provide an `Order` list. Mock `csv.writer.writerow` to raise an `IOError` after writing some rows.
  - Act: Call `CsvOrderExporter.export_orders`.
  - Assert: Raises `CsvExportException`, logs the exception details, updates statuses correctly in memory (orders not written before error are marked `ORDER_STATUS_EXPORT_FAILED`, successfully written ones retain original status).

## OrderProcessingService Initialization Tests (`test_order_processor.py::TestOrderProcessingServiceInitialization`)

- [ ] **test_should_initialize_successfully_when_valid_dependencies_provided**
  - Arrange: Provide valid mock instances of `DatabaseService`, `APIClient`, and `CsvOrderExporter`.
  - Act: Instantiate `OrderProcessingService`.
  - Assert: Service instance is created successfully with dependencies assigned correctly.

- [ ] **test_should_raise_typeerror_when_invalid_db_service_provided**
  - Arrange: Provide an invalid object or `None` as `db_service`.
  - Act: Instantiate `OrderProcessingService`.
  - Assert: Raises `TypeError` with a specific message.

- [ ] **test_should_raise_typeerror_when_invalid_api_client_provided**
  - Arrange: Provide an invalid object or `None` as `api_client`.
  - Act: Instantiate `OrderProcessingService`.
  - Assert: Raises `TypeError` with a specific message.

- [ ] **test_should_use_default_exporter_when_exporter_not_provided**
  - Arrange: Provide valid `db_service` and `api_client`, but `None` for `exporter`. Patch `CsvOrderExporter`.
  - Act: Instantiate `OrderProcessingService`.
  - Assert: A default `CsvOrderExporter` instance is created and assigned.

## OrderProcessingService Execution Tests (`test_order_processor.py::TestOrderProcessingServiceExecution`)

### II. Fetching Orders Tests

- [ ] **test_should_return_success_and_zero_counts_when_no_orders_found**
  - Arrange: Mock `db_service.get_orders_by_user` to return an empty list.
  - Act: Call `service.process_orders_for_user`.
  - Assert: Returns a `ProcessingResult` with `was_successful=True`, `processed_count=0`, and empty `failed_orders`. `get_orders_by_user` was called. No other dependencies called.

- [ ] **test_should_return_failure_when_get_orders_raises_db_exception**
  - Arrange: Mock `db_service.get_orders_by_user` to raise `DatabaseException`.
  - Act: Call `service.process_orders_for_user`.
  - Assert: Returns a `ProcessingResult` with `was_successful=False`, `processed_count=0`, and `failed_orders` containing the DB error reason. `get_orders_by_user` was called. Logs the error. No other dependencies called.

### III. Single Order Processing Logic Tests

- **Type A:**
  - [ ] **test_should_mark_type_a_for_export_and_update_low_priority_when_amount_low**
    - Arrange: Mock `get_orders_by_user` to return a Type A order with `amount <= ORDER_PRIORITY_THRESHOLD`. Mock exporter and time.
    - Act: Call `service.process_orders_for_user`.
    - Assert: `exporter.export_orders` called with the Type A order. `db_service.update_order_statuses` called with the order ID, status `ORDER_STATUS_EXPORTED`, and priority `ORDER_PRIORITY_LOW`. Order priority updated in memory.
  - [ ] **test_should_mark_type_a_for_export_and_update_high_priority_when_amount_high**
    - Arrange: Mock `get_orders_by_user` to return a Type A order with `amount > ORDER_PRIORITY_THRESHOLD`. Mock exporter and time.
    - Act: Call `service.process_orders_for_user`.
    - Assert: `exporter.export_orders` called with the Type A order. `db_service.update_order_statuses` called with the order ID, status `ORDER_STATUS_EXPORTED`, and priority `ORDER_PRIORITY_HIGH`. Order priority updated in memory.

- **Type B:**
  - [ ] **test_should_call_api_client_when_order_type_b**
    - Arrange: Mock `get_orders_by_user` to return a Type B order.
    - Act: Call `service.process_orders_for_user`.
    - Assert: `api_client.call_api` was called with the correct order ID.
  - [ ] **test_should_set_status_processed_when_type_b_api_success_data_high_amount_low**
    - Arrange: Mock `get_orders_by_user` for Type B order with `amount < ORDER_AMOUNT_THRESHOLD`. Mock `api_client.call_api` to return success with `data >= API_DATA_THRESHOLD`.
    - Act: Call `service.process_orders_for_user`.
    - Assert: `db_service.update_order_statuses` called with status `ORDER_STATUS_PROCESSED`. Order status updated in memory.
  - [ ] **test_should_set_status_pending_when_type_b_api_success_data_low**
    - Arrange: Mock `get_orders_by_user` for Type B order. Mock `api_client.call_api` to return success with `data < API_DATA_THRESHOLD`.
    - Act: Call `service.process_orders_for_user`.
    - Assert: `db_service.update_order_statuses` called with status `ORDER_STATUS_PENDING`. Order status updated in memory.
  - [ ] **test_should_set_status_review_required_when_type_b_api_success_data_high_amount_high**
    - Arrange: Mock `get_orders_by_user` for Type B order with `amount >= ORDER_AMOUNT_THRESHOLD`. Mock `api_client.call_api` to return success with `data >= API_DATA_THRESHOLD`.
    - Act: Call `service.process_orders_for_user`.
    - Assert: `db_service.update_order_statuses` called with status `ORDER_STATUS_REVIEW_REQUIRED`. Order status updated in memory.
  - [ ] **test_should_set_status_api_data_error_when_type_b_api_success_data_non_numeric**
    - Arrange: Mock `get_orders_by_user` for Type B order. Mock `api_client.call_api` to return success with non-numeric `data`.
    - Act: Call `service.process_orders_for_user`.
    - Assert: `db_service.update_order_statuses` called with status `ORDER_STATUS_API_DATA_ERROR`. Order status updated in memory.
  - [ ] **test_should_set_status_api_error_when_type_b_api_returns_error_status**
    - Arrange: Mock `get_orders_by_user` for Type B order. Mock `api_client.call_api` to return a non-'success' status.
    - Act: Call `service.process_orders_for_user`.
    - Assert: `db_service.update_order_statuses` called with status `ORDER_STATUS_API_ERROR`. Order status updated in memory.
  - [ ] **test_should_set_status_api_failure_and_report_failure_when_type_b_api_raises_exception**
    - Arrange: Mock `get_orders_by_user` for Type B order. Mock `api_client.call_api` to raise `APIException`.
    - Act: Call `service.process_orders_for_user`.
    - Assert: Returns `ProcessingResult` with `was_successful=False` and the failed order ID/reason. `db_service.update_order_statuses` called with status `ORDER_STATUS_API_FAILURE`. Order status updated in memory.

- **Type C:**
  - [ ] **test_should_set_status_completed_when_type_c_and_flag_true**
    - Arrange: Mock `get_orders_by_user` to return a Type C order with `flag=True`.
    - Act: Call `service.process_orders_for_user`.
    - Assert: `db_service.update_order_statuses` called with status `ORDER_STATUS_COMPLETED`. Order status updated in memory.
  - [ ] **test_should_set_status_in_progress_when_type_c_and_flag_false**
    - Arrange: Mock `get_orders_by_user` to return a Type C order with `flag=False`.
    - Act: Call `service.process_orders_for_user`.
    - Assert: `db_service.update_order_statuses` called with status `ORDER_STATUS_IN_PROGRESS`. Order status updated in memory.
- **Unknown Type:**
  - [ ] **test_should_set_status_unknown_type_when_order_type_not_abc**
    - Arrange: Mock `get_orders_by_user` to return an order with an unknown type.
    - Act: Call `service.process_orders_for_user`.
    - Assert: `db_service.update_order_statuses` called with status `ORDER_STATUS_UNKNOWN_TYPE`. Order status updated in memory.
- **Priority Calculation:**
  - [ ] **test_should_set_correct_priority_based_on_amount (parametrized)**
    - Arrange: Mock `get_orders_by_user` to return an order with varying amounts (above, at, below `ORDER_PRIORITY_THRESHOLD`, zero, negative).
    - Act: Call `service.process_orders_for_user`.
    - Assert: `db_service.update_order_statuses` called with the correct priority (`high` or `low`) based on the amount threshold. Order priority updated correctly in memory.

### IV. CSV Export Logic Tests

- [ ] **test_should_call_exporter_when_type_a_orders_exist**
  - Arrange: Mock `get_orders_by_user` to return a mix of orders including Type A. Mock exporter and time.
  - Act: Call `service.process_orders_for_user`.
  - Assert: `exporter.export_orders` was called exactly once with only the Type A orders and correct user ID/timestamp. Other order types processed correctly. `db_service.update_order_statuses` called with correct statuses for all orders.
- [ ] **test_should_not_call_exporter_when_no_type_a_orders_exist**
  - Arrange: Mock `get_orders_by_user` to return orders, but none of Type A.
  - Act: Call `service.process_orders_for_user`.
  - Assert: `exporter.export_orders` was not called. Other orders processed correctly. `db_service.update_order_statuses` called.
- [ ] **test_should_set_status_export_failed_in_db_update_when_exporter_raises_exception**
  - Arrange: Mock `get_orders_by_user` to return Type A and other orders. Mock `exporter.export_orders` to raise `CsvExportException` and set status to `ORDER_STATUS_EXPORT_FAILED` in memory.
  - Act: Call `service.process_orders_for_user`.
  - Assert: Returns `ProcessingResult` with `was_successful=False` and failed Type A orders listed. `db_service.update_order_statuses` called with Type A orders having status `ORDER_STATUS_EXPORT_FAILED`. Other orders processed normally.

### V. Database Update Logic Tests

- [ ] **test_should_call_update_statuses_with_correct_data_when_changes_exist**
  - Arrange: Mock `get_orders_by_user` to return orders where processing changes status or priority for some, but not all.
  - Act: Call `service.process_orders_for_user`.
  - Assert: `db_service.update_order_statuses` was called with a list containing *only* the tuples for orders whose status or priority changed. Correct `processed_count` returned.
- [ ] **test_should_not_call_update_statuses_when_no_changes_occur (Except Type A)**
  - Arrange: Mock `get_orders_by_user` to return non-Type A orders where processing results in the same status/priority as the initial state.
  - Act: Call `service.process_orders_for_user`.
  - Assert: `db_service.update_order_statuses` was *not* called. `processed_count` reflects the number of orders processed without errors (even if no DB update needed).
- [ ] **test_should_report_partial_failure_when_update_statuses_returns_failed_ids**
  - Arrange: Mock `get_orders_by_user` to return orders needing updates. Mock `db_service.update_order_statuses` to return a list of failed order IDs.
  - Act: Call `service.process_orders_for_user`.
  - Assert: Returns `ProcessingResult` with `was_successful=False`, correct `processed_count` (attempted - failed), and `failed_orders` listing the DB failures.
- [ ] **test_should_report_total_failure_when_update_statuses_raises_db_exception**
  - Arrange: Mock `get_orders_by_user` to return orders needing updates. Mock `db_service.update_order_statuses` to raise `DatabaseException`.
  - Act: Call `service.process_orders_for_user`.
  - Assert: Returns `ProcessingResult` with `was_successful=False`, `processed_count=0`, and `failed_orders` listing *all* orders intended for update with the DB error reason.

### VI. Aggregate/Complex Scenarios & Edge Cases

- [ ] **test_should_continue_processing_other_orders_when_one_order_fails_api_call**
  - Arrange: Mock `get_orders_by_user` with multiple orders. Mock `api_client.call_api` to raise `APIException` for one specific Type B order.
  - Act: Call `service.process_orders_for_user`.
  - Assert: Returns `ProcessingResult` with `was_successful=False`, listing only the failed API order. Other orders (Type A, C, or other B) are processed normally. `db_service.update_order_statuses` is called with correct final statuses for all orders (including the error status for the failed one). Correct `processed_count`.
- [ ] **test_should_report_failure_and_log_error_when_unexpected_exception_in_processing_loop**
  - Arrange: Mock `get_orders_by_user`. Patch an internal method (e.g., `_determine_priority`) to raise an unexpected `Exception`.
  - Act: Call `service.process_orders_for_user`.
  - Assert: Returns `ProcessingResult` with `was_successful=False`, listing the order(s) that hit the exception with the reason. Logs the exception. `db_service.update_order_statuses` called with status `ORDER_STATUS_PROCESSING_ERROR` for the affected order(s). Correct `processed_count`.
- [ ] **test_should_return_overall_success_true_when_all_steps_succeed_with_mixed_order_types**
  - Arrange: Mock `get_orders_by_user` with a mix of Type A, B, C orders. Ensure all mocks (`db_service`, `api_client`, `exporter`) simulate success.
  - Act: Call `service.process_orders_for_user`.
  - Assert: Returns `ProcessingResult` with `was_successful=True`, `processed_count` equal to the total number of orders, and empty `failed_orders`. All dependencies called correctly.
- [ ] **test_should_aggregate_all_failure_reasons_correctly_in_failed_orders**
  - Arrange: Mock `get_orders_by_user` with multiple orders. Set up mocks to cause different failures: `APIException`, `CsvExportException`, and `db_service.update_order_statuses` returning failed IDs. Include one order that processes successfully.
  - Act: Call `service.process_orders_for_user`.
  - Assert: Returns `ProcessingResult` with `was_successful=False`, correct `processed_count` (total attempted updates - DB failures). `failed_orders` list contains tuples for *all* types of failures (API, Export, DB) with correct order IDs and reasons.
- [ ] **test_should_not_call_db_update_and_calculate_processed_count_correctly_when_no_status_or_priority_changes**
  - Arrange: Mock `get_orders_by_user` to return only non-Type A orders where processing results in no change to status or priority.
  - Act: Call `service.process_orders_for_user`.
  - Assert: `db_service.update_order_statuses` is *not* called. Returns `ProcessingResult` with `was_successful=True` (assuming no processing errors), empty `failed_orders`, and `processed_count` equal to the total number of orders processed. Exporter is not called. API is called for Type B if present.
