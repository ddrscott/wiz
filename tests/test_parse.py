import pytest
from wiz import process_file_blocks, TAG

def test_process_file_blocks_basic():
    """Test basic file block processing."""
    input_lines = [
        f"[{TAG} test.py]",
        "print('hello world')",
        f"[/{TAG}]"
    ]
    result = process_file_blocks(input_lines)
    assert len(result) == 1
    assert result[0][0] == "test.py"  # file path
    assert result[0][1] == "print('hello world')"  # content
    assert result[0][2] == 1  # line number

def test_process_file_blocks_with_code_fence():
    """Test file block processing with code fences."""
    input_lines = [
        f"[{TAG} test.py]",
        "```python",
        "print('hello world')",
        "```",
        f"[/{TAG}]"
    ]
    result = process_file_blocks(input_lines)
    assert len(result) == 1
    assert result[0][0] == "test.py"
    assert result[0][1] == "print('hello world')"
    assert result[0][2] == 1

def test_process_file_blocks_multiple():
    """Test processing multiple file blocks."""
    input_lines = [
        f"[{TAG} file1.py]",
        "print('file1')",
        f"[/{TAG}]",
        "Some text in between",
        f"[{TAG} file2.py]",
        "print('file2')",
        f"[/{TAG}]"
    ]
    result = process_file_blocks(input_lines)
    assert len(result) == 2
    assert result[0][0] == "file1.py"
    assert result[0][1] == "print('file1')"
    assert result[1][0] == "file2.py"
    assert result[1][1] == "print('file2')"

def test_process_file_blocks_empty():
    """Test processing empty input."""
    input_lines = []
    result = process_file_blocks(input_lines)
    assert len(result) == 0
