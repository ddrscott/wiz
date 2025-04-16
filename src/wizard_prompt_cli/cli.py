import os
import sys
import re
from glob import glob
import fnmatch
from typing import List, Tuple, Dict, Any, Optional

import click
import yaml
import tiktoken
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.markup import escape

from .inference import reply, process_file_blocks

# Create console for error/status output - all UI/logs go to stderr
console = Console(stderr=True)

## common binary files and almost always files to ignore
ignore_ext = (
    '.png', '.jpg', '.jpeg', '.gif', '.svg', '.ico', '.webp', '.ipynb', '.pdf', '.doc', '.docx', '.ppt',
    '.pptx', '.xls', '.xlsx', '.lock', '.log', '.zip', '.tar', '.gz', '.tgz', '.rar', '.7z', '.mp4', '.avi',
    '.mov', '.mp3', '.wav', '.flac', '.ogg', '.webm', '.mkv', '.flv', '.m4a', '.wma', '.aac', '.opus', '.bmp',
    '.tiff', '.tif', '.psd', '.ai', '.eps', '.indd', '.raw', '.cr2', '.nef', '.orf', '.sr2', '.svgz', '.ico',
    '.ps', '.eps', '.pdf', '.doc', '.docx', '.ppt', '.pptx', '.xls', '.xlsx', '.odt', '.ods', '.odp',
    '.egg-info', '.whl', '.pyc', 'package-lock.json', 'yarn.lock',
)
## common files to ignore
ignore_files = ('.gitignore', '.dockerignore')


def project_files(exclude_pattern=None):
    # Cache gitignore patterns for performance
    gitignore_patterns = []
    gitignore_negation_patterns = []

    # Process .gitignore files once at the beginning
    for ignore_file in ignore_files:
        if os.path.exists(ignore_file):
            with open(ignore_file, 'r') as f:
                # Read and filter out empty lines and comments
                for line in f:
                    line = line.strip()
                    if line and not line.startswith('#'):
                        if line.startswith('!'):
                            gitignore_negation_patterns.append(line[1:])  # Store without the '!'
                        else:
                            gitignore_patterns.append(line)

    # Compile exclude regex patterns for performance
    exclude_regex_patterns = []
    if exclude_pattern:
        patterns = [exclude_pattern] if isinstance(exclude_pattern, str) else exclude_pattern
        for pattern in patterns:
            if pattern:
                try:
                    exclude_regex_patterns.append(re.compile(pattern))
                except re.error:
                    console.print(f"[bold yellow]Warning: Invalid regex pattern: {pattern}[/bold yellow]")

    # Fast path: get all files including those without extensions
    with console.status("[bold green]Scanning project files...", spinner="dots"):
        # Get all files, including those without extensions
        all_files = []
        for pattern in ['**/*.*', '**/[!.]*']:
            all_files.extend(glob(pattern, recursive=True))
        # Remove duplicates while preserving order
        all_files = list(dict.fromkeys(all_files))

    # Function to check if a file should be ignored - optimized version
    def should_ignore(file):
        # Quick check for common binary files and patterns
        if file.endswith(ignore_ext):
            return True

        # Handle hidden files, node_modules, and other common patterns
        if file.startswith('.') or 'node_modules' in file:
            return True

        if os.path.isdir(file):
            return True
        # Skip directories that are commonly ignored
        parts = file.split(os.sep)
        if any(part in ('node_modules', '__pycache__', '.git', '.idea', '.vscode') for part in parts):
            return True

        # Check custom exclude patterns
        for pattern in exclude_regex_patterns:
            if pattern.search(file):
                return True

        # Process gitignore patterns
        # First check if file is excluded by a gitignore pattern
        for pattern in gitignore_patterns:
            if _matches_gitignore_pattern(file, pattern):
                # Check if there's a negation pattern that overrides
                for neg_pattern in gitignore_negation_patterns:
                    if _matches_gitignore_pattern(file, neg_pattern):
                        return False  # Negation pattern takes precedence
                return True  # No negation pattern matched, so ignore this file

        return False

    # Helper function to match gitignore patterns properly
    def _matches_gitignore_pattern(file, pattern):
        # Special case for directory patterns like "dist/"
        if pattern.endswith('/'):
            pattern_name = pattern.rstrip('/')

            # Simplest case: direct match for directory
            if file == pattern_name or file.startswith(f"{pattern_name}/"):
                return True

            # Check if file is in a directory specified by pattern
            parts = file.split(os.sep)
            for i, part in enumerate(parts):
                if fnmatch.fnmatch(part, pattern_name):
                    # If this directory component matches, and it's not the last part (i.e., it's a directory)
                    if i < len(parts) - 1:
                        return True
            return False

        # Handle pattern with leading slash (anchored to project root)
        if pattern.startswith('/'):
            pattern = pattern[1:]
            return fnmatch.fnmatch(file, pattern)

        # Standard gitignore pattern matching

        # Check if pattern contains wildcards
        if '*' in pattern or '?' in pattern or '[' in pattern:
            # Check basename match
            basename = os.path.basename(file)
            if fnmatch.fnmatch(basename, pattern):
                return True

            # Check full path match
            return fnmatch.fnmatch(file, pattern) or fnmatch.fnmatch(file, f"*/{pattern}")
        else:
            # For patterns without wildcards, direct substring search is faster
            return pattern in file or f"/{pattern}" in file

    # Filter files with progress display and optimized batch processing
    filtered_files = []

    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Filtering files..."),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Filtering", total=len(all_files))
        for file in all_files:
            if not should_ignore(file):
                filtered_files.append(file)
            progress.update(task, advance=1)

    console.print(f"[green]Found {len(filtered_files)} relevant files[/green]")
    return filtered_files

def get_file_table(files=None, attachments=None, exclude_pattern=None, show_tokens=False):
    """
    Generate and return a table of files and attachments that would be included in a prompt.
    Also returns the list of files being processed.

    Args:
        files: List of specific files to include
        attachments: List of attachments to include
        exclude_pattern: Pattern to exclude files
        show_tokens: Whether to show token counts along with file sizes
    """
    attachments = attachments or []  # Ensure attachments is a list
    total_bytes = 0  # Initialize total byte counter
    total_tokens = 0  # Initialize total token counter

    # Initialize tiktoken encoder for claude-3 models
    encoder = tiktoken.get_encoding("cl100k_base")  # Using OpenAI's cl100k encoding

    if files:
        console.print(f"Using specified files: {', '.join(files)}")
        file_list = files
    else:
        file_list = project_files(exclude_pattern)

    # Display file stats in a table
    table = Table(title="Files Being Processed")
    table.add_column("File", style="cyan")
    table.add_column("Size", justify="right", style="green")
    if show_tokens:
        table.add_column("Tokens", justify="right", style="blue")
    table.add_column("Status", style="yellow")
    table.add_column("Type", style="magenta")  # Add type column to differentiate files and attachments

    # Read files with progress indication
    with Progress(
        SpinnerColumn(),
        TextColumn("[bold blue]Reading files..."),
        TimeElapsedColumn(),
        console=console
    ) as progress:
        task = progress.add_task("Reading", total=len(file_list))

        for file in file_list:
            try:
                with open(file, 'r') as f:
                    content = f.read()
                    file_size = os.path.getsize(file)
                    total_bytes += file_size  # Add to total

                    # Calculate tokens using tiktoken
                    if show_tokens:
                        tokens = len(encoder.encode(content))
                        total_tokens += tokens
                    else:
                        tokens = 0

                    # Add to table
                    size_str = f"{file_size / 1024:.1f} KB" if file_size > 1024 else f"{file_size} bytes"

                    if show_tokens:
                        table.add_row(file, size_str, str(tokens), "✓ Read", "Text File")
                    else:
                        table.add_row(file, size_str, "✓ Read", "Text File")
            except Exception as e:
                if show_tokens:
                    table.add_row(file, "N/A", "N/A", str(e), "Error")
                else:
                    table.add_row(file, "N/A", str(e), "Error")

            progress.update(task, advance=1)

    # Add attachments to the table
    for attachment in attachments:
        try:
            if attachment.startswith("http"):
                if show_tokens:
                    # Using a conservative estimate for remote images
                    img_token_estimate = 1200
                    total_tokens += img_token_estimate
                    table.add_row(attachment, "URL", f"~{img_token_estimate}", "✓ Included", "Remote Image")
                else:
                    table.add_row(attachment, "URL", "✓ Included", "Remote Image")
            else:
                file_size = os.path.getsize(attachment)
                total_bytes += file_size  # Add to total

                # Estimate for image tokens based on file size
                # This is a rough approximation and varies by image content and model
                if show_tokens:
                    # Roughly estimate tokens based on image size
                    if file_size < 50000:  # Small image
                        img_token_estimate = 700
                    elif file_size < 200000:  # Medium image
                        img_token_estimate = 1400
                    elif file_size < 500000:  # Large image
                        img_token_estimate = 2100
                    else:  # Very large image
                        img_token_estimate = 3000

                    total_tokens += img_token_estimate

                size_str = f"{file_size / 1024:.1f} KB" if file_size > 1024 else f"{file_size} bytes"
                ext = os.path.splitext(attachment)[1][1:].upper() or "Unknown"

                if show_tokens:
                    table.add_row(attachment, size_str, f"~{img_token_estimate}", "✓ Included", f"Image ({ext})")
                else:
                    table.add_row(attachment, size_str, "✓ Included", f"Image ({ext})")
        except Exception as e:
            if show_tokens:
                table.add_row(attachment, "N/A", "N/A", f"Error: {str(e)}", "Image Error")
            else:
                table.add_row(attachment, "N/A", f"Error: {str(e)}", "Image Error")

    # Add a row for the total
    if total_bytes > 0:
        # Format total size appropriately depending on size
        if total_bytes > 1024 * 1024:  # If more than 1MB
            total_size_str = f"{total_bytes / (1024 * 1024):.2f} MB"
        elif total_bytes > 1024:  # If more than 1KB
            total_size_str = f"{total_bytes / 1024:.2f} KB"
        else:
            total_size_str = f"{total_bytes} bytes"

        # Add a separator and then the total row
        table.add_section()
        if show_tokens:
            table.add_row("[bold]TOTAL[/bold]", f"[bold]{total_size_str}[/bold]", f"[bold]{total_tokens}[/bold]", "", "")
        else:
            table.add_row("[bold]TOTAL[/bold]", f"[bold]{total_size_str}[/bold]", "", "")

    return table, file_list

def load_wizrc_config() -> Dict[str, Any]:
    """Load configuration from .wizrc YAML file if it exists in the current directory."""
    wizrc_path = os.path.join(os.getcwd(), '.wizrc')
    config: Dict[str, Any] = {}
    if os.path.exists(wizrc_path):
        try:
            with open(wizrc_path, 'r') as f:
                yaml_config = yaml.safe_load(f)
                if yaml_config and isinstance(yaml_config, dict):
                    console.print(f"[dim]Using configuration from .wizrc file[/dim]")
                    return yaml_config
                else:
                    console.print(f"[bold yellow]Warning: .wizrc file is empty or not properly formatted[/bold yellow]")
        except Exception as e:
            console.print(f"[bold yellow]Warning: Error reading .wizrc file: {str(e)}[/bold yellow]")
    return config

@click.group()
@click.pass_context
def cli(ctx):
    """Command-line interface with .wizrc support."""
    config = load_wizrc_config()
    if config:
        # Set the default map for all commands
        ctx.default_map = config

@cli.command()
@click.argument('question_text', nargs=-1, required=True)
@click.option('--file', '-f', help='Files to include in the question', multiple=True)
@click.option('--image', '-i', help='Image to include in the question', multiple=True)
@click.option('--output', '-o', help='location write response without thoughts', default='.response.md')
@click.option('--max-tokens', '-m', help='Max tokens for the response', default=60000)
@click.option('--thinking-tokens', '-t', help='Max tokens for the thinking', default=16000)
@click.option('--exclude', '-x', help='Regular expression pattern to exclude files', multiple=True, default=None)
@click.option('--tokens', is_flag=True, help='Show token count estimates alongside file sizes')
@click.option('--model', help='Model to use for the prompt', default="anthropic/claude-3-7-sonnet-20250219")
@click.option('--llm-base', help='Base URL for the LLM API (for custom/self-hosted deployments)')
def prompt(question_text, file, output, image, max_tokens, thinking_tokens, exclude, tokens, model, llm_base):
    question = ' '.join(question_text)

    if question:
        try:
            response = reply(question, files=file, attachments=image, max_tokens=max_tokens,
                           thinking_tokens=thinking_tokens, exclude_pattern=exclude,
                           file_table_func=get_file_table, show_tokens=tokens, model=model,
                           api_base=llm_base)
            with open(output, 'w') as f:
                f.write(response)
            console.print(f"[bold green]Output written to {escape(output)}[/bold green]")
        except Exception as e:
            console.print(f"[bold red]Error:[/bold red] {str(e)}")
            console.print_exception()
    else:
        console.print("[bold red]Please provide a question as an argument[/bold red]")
        console.print("[bold]Example:[/bold] ./script.py 'How can I improve this code?'")
        console.print("[bold]Example with files:[/bold] ./script.py -f file1.py -f file2.py 'How do these files interact?'")
        console.print("[bold]Example with exclusion:[/bold] ./script.py -x '.*test.*\\.py$' -x '.*\\.log$' 'Analyze all non-test Python files'")

@cli.command()
@click.option('--file', '-f', help='Files to include in the listing', multiple=True)
@click.option('--image', '-i', help='Image to include in the listing', multiple=True)
@click.option('--exclude', '-x', help='Regular expression pattern to exclude files', multiple=True, default=None)
@click.option('--tokens', is_flag=True, help='Show token count estimates alongside file sizes')
def files(file, image, exclude, tokens):
    """
    List files that would be included in a prompt without calling the LLM.

    This command shows you exactly what files would be processed if you ran a prompt
    with the same parameters, helping you to verify the files before spending API tokens.
    """
    table, file_list = get_file_table(files=file, attachments=image, exclude_pattern=exclude, show_tokens=tokens)

    # Show summary statistics
    console.print(f"[bold green]Total Files: {len(file_list)}[/bold green]")

    # Show summary table
    console.print(table)

    # Show command example
    if file or exclude or image:
        example_cmd = "wiz prompt "
        if file:
            example_cmd += " ".join([f"-f '{f}'" for f in file]) + " "
        if image:
            example_cmd += " ".join([f"-i '{i}'" for i in image]) + " "
        if exclude:
            example_cmd += f"-x '{exclude}' "
        if tokens:
            example_cmd += "--tokens "
        example_cmd += '"Your question here"'

        console.print(f"\n[bold blue]Example command using these files:[/bold blue]")
        console.print(f"[dim]{escape(example_cmd)}[/dim]")


@cli.command()
@click.argument('input', nargs=1, required=True, default='.response.md')
def apply(input):
    if input == '-':
        console.print("[bold green]Reading from stdin...[/bold green]")
        input_lines = sys.stdin.readlines()
    else:
        console.print(f"[bold green]Processing input from {escape(input)}[/bold green]")
        try:
            with open(input, 'r') as f:
                input_lines = f.readlines()
        except FileNotFoundError:
            console.print(f"[bold red]Error: Input file '{input}' not found[/bold red]")
            sys.exit(1)

    file_blocks = process_file_blocks(input_lines)

    for file_path, content, line_number in file_blocks:
        # Create directory if needed
        directory = os.path.dirname(file_path)
        if directory:
            try:
                os.makedirs(directory, exist_ok=True)
            except OSError as e:
                console.print(f"[bold red]Error: Could not create directory '{directory}': {str(e)}[/bold red]")
                continue

        # Write content to file
        try:
            with open(file_path, 'w') as f:
                f.write(content)
            byte_count = len(content.encode('utf-8'))
            console.print(f"Processed: [cyan]{escape(file_path)}[/cyan] (from line {line_number}, {byte_count} bytes written)")
        except OSError as e:
            console.print(f"[bold red]Error: Could not write to '{file_path}': {str(e)}[/bold red]")

    if not file_blocks:
        console.print("[yellow]No file blocks found in input[/yellow]")

if __name__ == '__main__':
    cli()
