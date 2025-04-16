import sys
import base64
import mimetypes
import os
from typing import List

import litellm
from rich.console import Console
from rich.markup import escape

# Create console for error/status output - all UI/logs go to stderr
console = Console(stderr=True)

# Check if API key is available
api_key = os.environ.get("ANTHROPIC_API_KEY")
if not api_key:
    console.print("[bold red]Error: ANTHROPIC_API_KEY environment variable is not set[/bold red]")
    console.print("Please set your Anthropic API key by running: export ANTHROPIC_API_KEY=your_key_here")

# Configure LiteLLM
litellm.drop_params = True  # Drop provider-specific parameters for better compatibility

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
    """
    Parse attachments in a way that's compatible with LiteLLM's format for Anthropic models.
    LiteLLM will handle the conversion to the proper format for each provider.
    """
    if attachment.startswith("http"):
        # For URL images
        return {
            "type": "image_url",
            "image_url": {
                "url": attachment
            }
        }
    else:
        # For local images - convert to base64
        image_media_type = mimetypes.guess_type(attachment)
        with open(attachment, 'rb') as f:
            buffer = f.read()
            image_data = base64.standard_b64encode(buffer).decode("utf-8")
            return {
                "type": "image_url",
                "image_url": {
                    "url": f"data:{image_media_type[0]};base64,{image_data}"
                }
            }

def reply(question, files=None, attachments=None, max_tokens=60000, thinking_tokens=16000, exclude_pattern=None,
          file_table_func=None, show_tokens=False, model="anthropic/claude-3-7-sonnet-20250219", api_base=None):
    """
    Send a prompt to LLM with files and attachments and return the response.

    Args:
        question: The prompt to send to LLM
        files: List of file paths to include
        attachments: List of image paths or URLs to include
        max_tokens: Maximum number of tokens in the response
        thinking_tokens: Maximum number of tokens for thinking
        exclude_pattern: Pattern to exclude files
        file_table_func: Function to generate file table and list (required)
        show_tokens: Whether to show token counts in the file table
        model: LiteLLM model identifier (e.g., "anthropic/claude-3-7-sonnet-20250219", "openai/gpt-4o")
        api_base: Custom API base URL for the LLM provider (for self-hosted models)

    Returns:
        The text response from LLM
    """
    attachments = attachments or []  # Ensure attachments is a list

    # Get file table and list using the provided function
    table, file_list = file_table_func(files, attachments, exclude_pattern, show_tokens)

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

    # Build the messages array
    content = []

    # Add image attachments
    for att in attachments:
        content.append(parse_attachment(att))

    # Add text content
    content.append({
        "type": "text",
        "text": body
    })

    open('.messages.md', 'w').write(system + "\n---\\n" + body)

    console.print("[bold yellow]Question:[/bold yellow]")
    console.print(question)
    console.print()

    parts = []

    console.print(f"[bold blue]Waiting for LLM {escape(model)}...[/bold blue]")

    stdout = Console(file=sys.stdout)

    try:
        # Create messages array for LiteLLM format
        messages = [
            {"role": "system", "content": system},
            {"role": "user", "content": content}
        ]

        # Call LiteLLM completion with streaming
        stream = litellm.completion(
            model=model,
            messages=messages,
            max_tokens=max_tokens,
            temperature=1,
            stream=True,
            reasoning_effort="low",
            drop_params=True,
            thinking={"type": "enabled", "budget_tokens": thinking_tokens},
            api_base=api_base
        )

        for chunk in stream:
            if chunk.choices and len(chunk.choices) > 0:
                delta = chunk.choices[0].delta

                # Handle regular content
                if delta.content is not None:
                    parts.append(delta.content)
                    stdout.print(escape(delta.content), end="")

                # Handle thinking output
                if hasattr(delta, 'thinking') and delta.thinking:
                    console.print(f"[dim]{escape(delta.thinking)}[/dim]", end="")
                elif hasattr(delta, 'thinking_blocks') and delta.thinking_blocks:
                    for tb in delta.thinking_blocks:
                        if thinking := tb.get('thinking', None):
                            console.print(f"[dim]{escape(thinking)}[/dim]", end="")
                elif hasattr(delta, 'reasoning_content') and delta.reasoning_content:
                    console.print(f"[dim]{escape(delta.reasoning_content)}[/dim]", end="")
    except Exception as e:
        console.print(f"[bold red]Error during API call: {str(e)}[/bold red]")

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
