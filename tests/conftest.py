"""Pytest configuration."""


def pytest_configure(config):
    """Configure pytest."""
    config.addinivalue_line("markers", "slow: mark test as slow")
    config.addinivalue_line("markers", "integration: mark test as integration test")
