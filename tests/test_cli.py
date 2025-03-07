import pytest
from unittest.mock import patch, MagicMock, mock_open
from click.testing import CliRunner
from wiz import cli, files, apply

def test_files_command(runner):
    """Test the 'files' command."""
    with patch('wiz.get_file_table') as mock_get_table:
        # Mock the return value of get_file_table
        mock_table = MagicMock()
        mock_get_table.return_value = (mock_table, ['file1.py', 'file2.py'])

        result = runner.invoke(files)

        assert result.exit_code == 0
        # The function was called once
        mock_get_table.assert_called_once()

def test_apply_command_stdin(runner):
    """Test the 'apply' command with stdin input."""
    stdin_content = (
        "[FILE test.py]\n"
        "print('hello world')\n"
        "[/FILE]\n"
    )

    with patch('wiz.process_file_blocks') as mock_process:
        # Configure the mock to return a single file result
        mock_process.return_value = [('test.py', "print('hello world')", 1)]

        # Mock file operations
        with patch('builtins.open', mock_open()):
            with patch('os.makedirs'):
                # Invoke the apply command with stdin input
                result = runner.invoke(apply, ['-'], input=stdin_content)

                assert result.exit_code == 0
                # Verify process_file_blocks was called
                mock_process.assert_called_once()

def test_apply_command_file(runner):
    """Test the 'apply' command with file input."""
    file_content = (
        "[FILE test.py]\n"
        "print('hello world')\n"
        "[/FILE]\n"
    )

    with patch('wiz.process_file_blocks') as mock_process:
        # Configure the mock to return a single file result
        mock_process.return_value = [('test.py', "print('hello world')", 1)]

        # Mock file operations
        with patch('builtins.open', mock_open(read_data=file_content)):
            with patch('os.makedirs'):
                # Invoke the apply command with file input
                result = runner.invoke(apply, ['.response.md'])

                assert result.exit_code == 0
                # Verify process_file_blocks was called
                mock_process.assert_called_once()

def test_prompt_command(runner):
    """Test the 'prompt' command."""
    with patch('wiz.reply') as mock_reply:
        mock_reply.return_value = "Response content"
        with patch('builtins.open', mock_open()):
            result = runner.invoke(cli, ['prompt', 'How can I improve this code?'])

            assert result.exit_code == 0
            # Verify reply was called with the question
            mock_reply.assert_called_once()
            assert 'How can I improve this code?' in mock_reply.call_args[0][0]