# Common pytest fixtures go here
import pytest
from click.testing import CliRunner

@pytest.fixture
def runner():
    """Create a CLI runner for testing commands."""
    return CliRunner()