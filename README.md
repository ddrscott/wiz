# AI CLI

A command-line interface for interacting with Claude AI to analyze and modify project files.

## Installation

```bash
uv pip install ai-cli
```

Or install from source:

```bash
git clone https://github.com/ddrscott/ai-cli.git
cd ai-cli
uv pip install -e .
```

## Usage

AI CLI offers two main commands:

### Prompt Command

Send a question to Claude along with project files:

```bash
claude prompt "How can I improve this code?"
```

Include specific files:

```bash
claude prompt -f main.py -f utils.py "How can I make these files more efficient?"
```

The response will be saved to `.response.md` by default.

### Apply Command

Apply changes suggested by Claude to update your files:

```bash
claude apply
```

Or specify a different input file:

```bash
claude apply custom_response.md
```

You can also pipe content directly to the apply command:

```bash
cat response.md | claude apply -
```

## Features

- Automatically scans project files, excluding binaries and respecting `.gitignore` rules
- Streams Claude's thinking process as it formulates a response
- Automatically applies file changes suggested by Claude
- Supports file filtering to focus on relevant code
- Handles code formatting with language-specific syntax highlighting
- Supports reading from stdin with the `-` argument in apply command

## How It Works

1. The `prompt` command sends your question and file contents to Claude
2. Claude analyzes your files and provides a response with suggested changes
3. Changes are formatted with `[FILE path]...[/FILE]` markers
4. The `apply` command processes these markers and updates your files

## Examples

Ask Claude to refactor a specific function:

```bash
claude prompt -f src/utils.py "Refactor the parse_data function to be more efficient"
```

Implement a new feature:

```bash
claude prompt "Add a progress bar to the file processing function"
```

Then apply the changes:

```bash
claude apply
```

Or pipe the response directly:

```bash
claude prompt "Fix bugs" | claude apply -
```

## License

[MIT License](LICENSE)
