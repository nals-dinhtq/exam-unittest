# -*- coding: utf-8 -*-
"""
Configuration settings, like logging setup.
"""
import logging


def setup_logging():
    """Configures basic logging for the application."""
    logging.basicConfig(
        level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    # You might want to adjust the root logger or configure specific loggers here
    # e.g., logging.getLogger('order_processing').setLevel(logging.DEBUG)

# Optionally define other configurations here
# DB_CONNECTION_STRING = "your_db_connection_string"
# API_ENDPOINT = "your_api_endpoint"
