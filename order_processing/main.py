# -*- coding: utf-8 -*-
"""
Example usage script for the order processing module.
Sets up dependencies (mocks) and runs the processor.
"""
import sys
import os

# Adjust path if running script directly from project root
# sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from order_processing.models import Order
from order_processing.services.database import InMemoryDbService
from order_processing.services.api_client import MockApiClient
from order_processing.order_processor import OrderProcessingService
from order_processing.config import setup_logging


def run_processing_example():
    """Sets up and runs the order processing example."""
    # Setup basic logging
    setup_logging()

    # --- Setup Dependencies (Mocks for Demo) ---
    # Sample Data - Matches original script's intent
    user1_orders_data = [
        Order(id=101, order_type='A', amount=50.0,
              flag=False),       # Exported, Low Prio
        # API -> data=30 (<50) -> Pending, Low Prio
        Order(id=102, order_type='B', amount=80.0, flag=False),
        # Flag=T -> Completed, High Prio
        Order(id=103, order_type='C', amount=250.0, flag=True),
        # Exported (high value note), Low Prio
        Order(id=104, order_type='A', amount=160.0, flag=True),
        # API -> Error Status -> api_error, Low Prio
        Order(id=105, order_type='B', amount=120.0, flag=False),
        # API -> data=75 (>=50), amount < 100 -> processed, Low Prio
        Order(id=106, order_type='B', amount=90.0, flag=False),
        # API -> Exception -> api_failure, Low Prio
        Order(id=107, order_type='B', amount=50.0, flag=False),
        # Unknown Type -> unknown_type, Low Prio
        Order(id=108, order_type='X', amount=10.0, flag=False),
        # API -> data=75 (>=50), amount >= 100 -> review_required, Low Prio
        Order(id=109, order_type='B', amount=150.0, flag=False),
        # Flag=F -> in_progress, Low Prio -> DB Update Fails (Simulated)
        Order(id=110, order_type='C', amount=10.0, flag=False),
    ]
    # Important: Pass copies to the DB service if you want to compare before/after easily
    # For simplicity here, we pass the list directly, the DB service now creates copies on get
    mock_db = InMemoryDbService(initial_orders={1: user1_orders_data})
    mock_api = MockApiClient()

    # --- Instantiate the Service ---
    processor = OrderProcessingService(db_service=mock_db, api_client=mock_api)

    # --- Run Processing ---
    user_to_process = 1
    processing_result = processor.process_orders_for_user(user_to_process)

    # --- Display Results ---
    print("\n--- Processing Summary ---")
    print(f"Overall Success: {processing_result.was_successful}")
    print(
        f"Processed Count (intended for DB update & succeeded): {processing_result.processed_count}")
    print(f"Failed Orders/Steps ({len(processing_result.failed_orders)}):")
    if processing_result.failed_orders:
        # Sort for consistent output
        for order_id, reason in sorted(processing_result.failed_orders):
            print(
                f"  - Order ID: {order_id if order_id != -1 else 'N/A'}, Reason: {reason}")
    else:
        print("  None")

    print("\n--- Final Order States in DB (Simulation) ---")
    # Fetch final states AFTER processing
    try:
        final_orders = mock_db.get_orders_by_user(user_to_process)
        if final_orders:
            # Sort for consistent output
            for order in sorted(final_orders, key=lambda o: o.id):
                print(f"  Order ID: {order.id:<3}, Type: {order.order_type:<1}, Amount: {order.amount:>6.2f}, "
                      f"Flag: {str(order.flag):<5}, Status: {order.status:<17}, Priority: {order.priority}")
        else:
            print("  No orders found in DB for user.")
    except Exception as e:
        print(f"  Error fetching final states from mock DB: {e}")


if __name__ == "__main__":
    run_processing_example()
