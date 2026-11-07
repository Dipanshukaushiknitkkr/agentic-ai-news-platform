import pytest

def pytest_addoption(parser):
    parser.addoption("--slow", action="store_true", default=False, help="Run slow integration tests")

def pytest_collection_modifyitems(config, items):
    if not config.getoption("--slow"):
        skip_slow = pytest.mark.skip(reason="Skipped: requires --slow flag and model download")
        for item in items:
            if "slow" in item.keywords:
                item.add_marker(skip_slow)
