import pytest
from unittest.mock import patch, mock_open
from wiz import project_files

@pytest.fixture
def mock_glob():
    """Mock glob to return predefined file list."""
    with patch('wiz.glob') as mock:
        mock.return_value = [
            'main.py',
            'utils.py',
            'test_file.py',
            '.hidden_file.py',
            'node_modules/some_file.js',
            'image.png',
            'document.pdf',
            'ignored_pattern.txt'
        ]
        yield mock

def test_project_files_basic(mock_glob):
    """Test basic file filtering without exclude pattern."""
    with patch('os.path.exists', return_value=False):  # No .gitignore
        result = project_files()
        # Should exclude binary files, hidden files, and node_modules
        assert 'main.py' in result
        assert 'utils.py' in result
        assert 'test_file.py' in result
        assert '.hidden_file.py' not in result
        assert 'node_modules/some_file.js' not in result
        assert 'image.png' not in result
        assert 'document.pdf' not in result

def test_project_files_with_exclude(mock_glob):
    """Test file filtering with exclude pattern."""
    with patch('os.path.exists', return_value=False):  # No .gitignore
        result = project_files(exclude_pattern=r'test_.*\.py$')
        assert 'main.py' in result
        assert 'utils.py' in result
        assert 'test_file.py' not in result

def test_gitignore_patterns():
    """Test respecting .gitignore patterns."""
    mock_gitignore_content = "ignored_pattern*\n*.log"

    with patch('wiz.glob', return_value=['file.py', 'ignored_pattern.txt', 'debug.log']):
        with patch('os.path.exists', return_value=True):
            with patch('builtins.open', mock_open(read_data=mock_gitignore_content)):
                with patch('fnmatch.fnmatch') as mock_fnmatch:
                    # Set up mock behavior
                    def match_side_effect(filename, pattern):
                        if pattern == "ignored_pattern*" and filename.startswith("ignored_pattern"):
                            return True
                        if pattern == "*.log" and filename.endswith(".log"):
                            return True
                        return False

                    mock_fnmatch.side_effect = match_side_effect

                    result = project_files()

                    # Only file.py should be included
                    assert 'file.py' in result
                    assert 'ignored_pattern.txt' not in result
                    assert 'debug.log' not in result