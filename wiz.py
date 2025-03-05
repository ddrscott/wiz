import os
import sys
from glob import glob
import fnmatch
from typing import List, Tuple

import click
import anthropic
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


def project_files():
    # Fetch all files with status indicator
    with console.status("[bold green]Scanning project files...", spinner="dots"):
        all_files = glob('**/*.*', recursive=True)

    # Function to check if a file should be ignored
    def should_ignore(file):
        # ignore image files
        if file.endswith(ignore_ext):
            return True
        # ignore hidden files and node_modules
        if file.startswith('.') or 'node_modules' in file:
            return True
        for ignore_file in ignore_files:
            if os.path.exists(ignore_file):
                with open(ignore_file, 'r') as f:
                    ignore_patterns = f.read().splitlines()
                    for pattern in ignore_patterns:
                        if fnmatch.fnmatch(file, pattern):
                            return True
        return False

    # Filter files with progress display
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

def reply(question, files=None, attachments=None, max_tokens=60000, thinking_tokens=16000):
    attachments = attachments or []  # Ensure attachments is a list

    if files:
        console.print(f"Using specified files: {', '.join(files)}")
        file_list = files
    else:
        file_list = project_files()

    # Display file stats in a table
    table = Table(title="Files Being Processed")
    table.add_column("File", style="cyan")
    table.add_column("Size", justify="right", style="green")
    table.add_column("Status", style="yellow")
    table.add_column("Type", style="magenta")  # Add type column to differentiate files and attachments

    body = [f"Help me with following files: {', '.join(file_list)}"]

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
                    body.append(f"""[{TAG} {file}]""")
                    body.append(content)
                    body.append(f"""[/{TAG}]""")

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

    # Show summary table
    console.print(table)

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
@click.group()
def cli():
    pass

@cli.command()
@click.argument('question_text', nargs=-1, required=True)
@click.option('--file', '-f', help='Files to include in the question', multiple=True)
@click.option('--image', '-i', help='Image to include in the question', multiple=True)
@click.option('--output', '-o', help='location write response without thoughts', default='.response.md')
@click.option('--max-tokens', '-m', help='Max tokens for the response', default=60000)
@click.option('--thinking-tokens', '-t', help='Max tokens for the thinking', default=16000)
def prompt(question_text, file, output, image, max_tokens, thinking_tokens):
    question = ' '.join(question_text)

    if question:
        try:
            response = reply(question, files=file, attachments=image, max_tokens=max_tokens)
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
