import os
import requests
from typing import List
from exam import Order, APIResponse, APIException, DatabaseService, APIClient, OrderProcessingService


class MockDatabaseService(DatabaseService):
    """
    Mock implementation of DatabaseService for testing purposes.
    """

    def __init__(self):
        # Sample data for testing
        self.orders = {
            1: [
                Order(id=101, type='A', amount=120.0, flag=False),
                Order(id=102, type='B', amount=250.0, flag=True),
                Order(id=103, type='C', amount=80.0, flag=False)
            ]
        }

    def get_orders_by_user(self, user_id: int) -> List[Order]:
        """Get all orders for a specific user"""
        return self.orders.get(user_id, [])

    def update_order_status(self, order_id: int, status: str, priority: str) -> bool:
        """Update order status and priority in database"""
        # Implement status update logic
        print(
            f"Order {order_id} status updated to '{status}' with priority '{priority}'")
        return True


class MockAPIClient(APIClient):
    """
    Mock implementation of APIClient for testing purposes.
    """

    def call_api(self, order_id: int) -> APIResponse:
        """Call external API for order processing"""
        # Simulate API call
        if order_id % 2 == 0:
            return APIResponse(status="success", data=75)
        else:
            return APIResponse(status="success", data=30)


class RealAPIClient(APIClient):
    """
    Real implementation of APIClient that calls an actual API.
    """

    def __init__(self, api_url: str, api_key: str = None):
        self.api_url = api_url
        self.api_key = api_key

    def call_api(self, order_id: int) -> APIResponse:
        """Call external API for order processing"""
        try:
            headers = {}
            if self.api_key:
                headers['Authorization'] = f"Bearer {self.api_key}"

            response = requests.get(
                f"{self.api_url}/orders/{order_id}",
                headers=headers,
                timeout=10
            )

            if response.status_code == 200:
                data = response.json()
                return APIResponse(status="success", data=data.get("value", 0))
            else:
                return APIResponse(status="error", data=None)

        except requests.RequestException as e:
            raise APIException(f"API call failed: {str(e)}")

# ...tiếp tục từ phần trên


def main():
    """
    Main function to demonstrate the OrderProcessingService
    """
    # Initialize Mock Database Service for testing
    db_service = MockDatabaseService()

    # Use mock API client for testing
    api_client = MockAPIClient()

    # Or use Real API Client if needed (commented out)
    # Get API key from environment variable for security
    api_key = os.environ.get("API_KEY")
    api_client = RealAPIClient(
        api_url="https://api.example.com", api_key=api_key)

    # Initialize OrderProcessingService
    order_service = OrderProcessingService(
        db_service=db_service, api_client=api_client)

    # Process orders for user_id=1
    user_id = 1
    result = order_service.process_orders(user_id=user_id)

    if result:
        print(f"Order processing successful for user {user_id}")

        # Display order status after processing
        orders = db_service.get_orders_by_user(user_id)
        for order in orders:
            print(
                f"Order {order.id}: Status={order.status}, Priority={order.priority}")
    else:
        print(f"Order processing failed for user {user_id}")


if __name__ == "__main__":
    main()
