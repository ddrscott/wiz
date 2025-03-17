import os
import sys
import re
from glob import glob
import fnmatch
from typing import List, Tuple, Dict, Any, Optional

import click
import anthropic
import yaml
from rich.console import Console
from rich.progress import Progress, SpinnerColumn, TextColumn, TimeElapsedColumn
from rich.table import Table
from rich.markup import escape

# Create console for error/status output - all UI/logs go to stderr
console = Console(stderr=True)

client = anthropic.Anthropic()

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
TAG = 'FILE'
system = f"""You are a 100x developer helping with a project.

**Strict Rules**
- all file output must be complete.
- wrap output with `[{TAG} path]...[/{TAG}]` tags and triple-tick fences.
- The output will be piped into another program to automatically adjust all files. Strict coherence to the format is paramount!

**Example Output**
[{TAG} path/to/foo.py]
```python
puts "hello world"
```
[/{TAG}]

[{TAG} path/to/bar.py]
```javascript
console.log("good bye world")
```
[/{TAG}]

**Notes**
- It is okay to explain things, but keep it brief and to the point!
- YOU MUST ALWAYS WRAP code files between [{TAG}] and [/{TAG}] tags!!!
"""


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

def parse_attachment(attachment):
    if attachment.startswith("http"):
        return {
            "type": "image",
            "source": {
                "type": "url",
                "url": attachment,
            },
        },
    else:
        import base64
        import mimetypes
        image_media_type = mimetypes.guess_type(attachment)
        with open(attachment, 'rb') as f:
            buffer = f.read()
            image_data = base64.standard_b64encode(buffer).decode("utf-8")
            return {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": image_media_type[0],
                    "data": image_data,
                },
            }

def get_file_table(files=None, attachments=None, exclude_pattern=None):
    """
    Generate and return a table of files and attachments that would be included in a prompt.
    Also returns the list of files being processed.
    """
    attachments = attachments or []  # Ensure attachments is a list

    if files:
        console.print(f"Using specified files: {', '.join(files)}")
        file_list = files
    else:
        file_list = project_files(exclude_pattern)

    # Display file stats in a table
    table = Table(title="Files Being Processed")
    table.add_column("File", style="cyan")
    table.add_column("Size", justify="right", style="green")
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
                    file_size = os.path.getsize(file)
                    # Add to table
                    size_str = f"{file_size / 1024:.1f} KB" if file_size > 1024 else f"{file_size} bytes"
                    table.add_row(file, size_str, "✓ Read", "Text File")
            except Exception as e:
                table.add_row(file, "N/A", str(e), "Error")

            progress.update(task, advance=1)

    # Add attachments to the table
    for attachment in attachments:
        try:
            if attachment.startswith("http"):
                table.add_row(attachment, "URL", "✓ Included", "Remote Image")
            else:
                file_size = os.path.getsize(attachment)
                size_str = f"{file_size / 1024:.1f} KB" if file_size > 1024 else f"{file_size} bytes"
                ext = os.path.splitext(attachment)[1][1:].upper() or "Unknown"
                table.add_row(attachment, size_str, "✓ Included", f"Image ({ext})")
        except Exception as e:
            table.add_row(attachment, "N/A", f"Error: {str(e)}", "Image Error")

    return table, file_list

def reply(question, files=None, attachments=None, max_tokens=60000, thinking_tokens=16000, exclude_pattern=None):
    attachments = attachments or []  # Ensure attachments is a list

    table, file_list = get_file_table(files, attachments, exclude_pattern)

    # Show summary table
    console.print(table)

    body = [f"Help me with following files: {', '.join(file_list)}"]

    # Read files content for the prompt
    for file in file_list:
        try:
            with open(file, 'r') as f:
                content = f.read()
                body.append(f"""[{TAG} {file}]""")
                body.append(content)
                body.append(f"""[/{TAG}]""")
        except Exception as e:
            console.print(f"[bold red]Error reading {file}: {str(e)}[/bold red]")

    body = '\n'.join(body)
    body = f"""{body}\n---\n\n{question}

**Reminder**
- wrap resulting code between `[{TAG}]` and `[/{TAG}]` tags!!!
"""
    images = [
        parse_attachment(att)
        for att in attachments
    ]
    messages = [
        {
            "role": "user",
            "content": images + [
                {
                    "type": "text",
                    "text": body
                }
            ]
        }
    ]
    open('.messages.md', 'w').write(system + "\n---\\n" + body)

    console.print("[bold yellow]Question:[/bold yellow]")
    console.print(question)
    console.print()

    parts = []
    thinking_output = ""

    console.print("[bold blue]Waiting for Claude...[/bold blue]")

    stdout = Console(file=sys.stdout)
    # Stream response through a Live display
    with client.messages.stream(
        model="claude-3-7-sonnet-20250219",
        max_tokens=max_tokens,
        temperature=1,
        system=system,
        messages=messages, # type: ignore
        thinking={
            "type": "enabled",
            "budget_tokens": thinking_tokens,
        }
    ) as stream:
        for event in stream:
            if event.type == "content_block_start":
                console.print()
            elif event.type == "content_block_delta":
                if event.delta.type == "thinking_delta":
                    thinking_output += event.delta.thinking
                    # Display thinking in a side panel or as a subtitle
                    console.print(f"[dim]{escape(event.delta.thinking)}[/dim]", end="")
                elif event.delta.type == "text_delta":
                    parts.append(event.delta.text)
                    stdout.print(escape(event.delta.text), end="")
            elif event.type == "content_block_stop":
                console.print()

    return ''.join(parts)

def process_file_blocks(lines: List[str]) -> List[Tuple[str, str, int]]:
    f"""
    Process input text containing file blocks in the format:
    [{TAG} path/to/file]
    (optional) ```language
    content
    (optional) ```
    [/{TAG}]

    Returns a list of tuples: (file_path, content, line_number)
    """
    result = []
    i = 0

    while i < len(lines):
        line = lines[i].rstrip()

        # Look for file block start
        if line.startswith('[FILE ') and line.endswith(']'):
            line_number = i + 1
            file_path = line[6:-1].strip()
            i += 1

            # Check if there's an opening code fence (optional)
            if i < len(lines) and lines[i].strip().startswith('```'):
                i += 1  # Skip the fence line

            # Collect content lines
            content_lines = []

            while i < len(lines):
                current_line = lines[i].strip()
                if current_line == f'[/{TAG}]':
                    break
                elif (current_line == '```' and
                      i + 1 < len(lines) and
                      lines[i + 1].strip() == f'[/{TAG}]'):
                    i += 1  # Skip the fence line
                    break

                content_lines.append(lines[i].rstrip())
                i += 1

            if i >= len(lines):
                print(f"Warning: Missing [/{TAG}] marker for file block at line {line_number}", file=sys.stderr)
                break

            # Skip [/FILE]
            i += 1

            content = '\n'.join(content_lines)
            result.append((file_path, content, line_number))

        else:
            i += 1

    return result

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
def prompt(question_text, file, output, image, max_tokens, thinking_tokens, exclude):
    question = ' '.join(question_text)

    if question:
        try:
            response = reply(question, files=file, attachments=image, max_tokens=max_tokens,
                           thinking_tokens=thinking_tokens, exclude_pattern=exclude)
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
def files(file, image, exclude):
    """
    List files that would be included in a prompt without calling the LLM.

    This command shows you exactly what files would be processed if you ran a prompt
    with the same parameters, helping you to verify the files before spending API tokens.
    """
    table, file_list = get_file_table(files=file, attachments=image, exclude_pattern=exclude)

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
