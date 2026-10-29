"""Keep import-time app construction away from the developer's selected database."""
import os
import tempfile
from pathlib import Path


def pytest_configure(config):
    config.stylist_test_directory = tempfile.TemporaryDirectory(prefix="stylist-pytest-")
    directory = Path(config.stylist_test_directory.name)
    overrides = {
        "STYLIST_LOCAL_CONFIG": str(directory / "no-local-config.yaml"),
        "STYLIST_DATABASE": str(directory / "import-time.sqlite3"),
        "STYLIST_CHECKPOINT_DATABASE": "",
    }
    config.stylist_saved_environment = {key: os.environ.get(key) for key in overrides}
    os.environ.update(overrides)


def pytest_unconfigure(config):
    for key, value in config.stylist_saved_environment.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value
    config.stylist_test_directory.cleanup()
