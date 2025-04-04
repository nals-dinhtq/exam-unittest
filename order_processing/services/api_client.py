# -*- coding: utf-8 -*-
"""
Concrete implementations of the APIClient interface.
Includes mock/demo implementations.
"""
import logging

from ..exceptions import APIException

# Use relative imports
from ..interfaces import APIClient
from ..models import APIResponse

log = logging.getLogger(__name__)


class MockApiClient(APIClient):
    """DEMO implementation of APIClient."""

    def call_api(self, order_id: int) -> APIResponse:
        log.info(f"API: Calling API for order {order_id}")
        # Simulate different API responses based on order ID
        if order_id % 7 == 0:  # Simulate failure for ID 105 (105%7==0)
            log.error(f"API: Simulated API Exception for order {order_id}")
            raise APIException(f"Simulated failure for order {order_id}")
        if order_id % 5 == 0:  # Simulate error response for ID 105, 110
            log.warning(f"API: Simulated API returning error status for order {order_id}")
            return APIResponse(status="error", data={"message": "Invalid request"})
        if order_id % 3 == 0:  # Simulate low data for ID 102, 108
            data_value = 30  # Simulate data < 50
            log.debug(f"API: Simulated success response with data={data_value} for order {order_id}")
            return APIResponse(status="success", data=data_value)
        else:  # Simulate high data for ID 101, 103, 104, 106, 107, 109
            data_value = 75  # Simulate data >= 50
            log.debug(f"API: Simulated success response with data={data_value} for order {order_id}")
            return APIResponse(status="success", data=data_value)


# Add real API client implementations here (e.g., RestApiClient) if needed
