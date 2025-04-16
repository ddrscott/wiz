import sys
import base64
import mimetypes
from typing import List

import anthropic
from rich.console import Console
from rich.markup import escape

# Create console for error/status output - all UI/logs go to stderr
console = Console(stderr=True)

# Initialize Anthropic client
client = anthropic.Anthropic()

# Constants
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

def reply(question, files=None, attachments=None, max_tokens=60000, thinking_tokens=16000, exclude_pattern=None, file_table_func=None):
    """
    Send a prompt to Claude with files and attachments and return the response.

    Args:
        question: The prompt to send to Claude
        files: List of file paths to include
        attachments: List of image paths or URLs to include
        max_tokens: Maximum number of tokens in the response
        thinking_tokens: Maximum number of tokens for thinking
        exclude_pattern: Pattern to exclude files
        file_table_func: Function to generate file table and list (required)

    Returns:
        The text response from Claude
    """
    attachments = attachments or []  # Ensure attachments is a list

    # Get file table and list using the provided function
    table, file_list = file_table_func(files, attachments, exclude_pattern)

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

def process_file_blocks(lines: List[str]) -> List[tuple]:
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
