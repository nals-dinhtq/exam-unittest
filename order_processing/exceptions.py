# -*- coding: utf-8 -*-
"""
Custom exceptions for the order processing application.
"""


class OrderProcessingException(Exception):
    """Base exception for errors during order processing."""

    pass


class APIException(OrderProcessingException):
    """Exception raised for errors during API interactions."""

    pass


class DatabaseException(OrderProcessingException):
    """Exception raised for errors during database operations."""

    pass


class CsvExportException(OrderProcessingException):
    """Exception raised for errors during CSV file export."""

    pass
