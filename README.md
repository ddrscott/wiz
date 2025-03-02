# 🧙‍♂️ Wizard Prompt CLI

> *Summon the power of Claude AI to transform your code with a wave of your terminal wand!*

[![PyPI version](https://img.shields.io/pypi/v/wizard-prompt-cli.svg)](https://pypi.org/project/wizard-prompt-cli/)
[![Python Versions](https://img.shields.io/pypi/pyversions/wizard-prompt-cli.svg)](https://pypi.org/project/wizard-prompt-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Wizard Prompt CLI is a magical command-line interface that conjures Claude AI to analyze, enhance, and transform your project files. Ask questions about your code in natural language, and watch as the AI wizard works its spells to provide insights and implement changes.

## ✨ Magical Features

- 🔮 Automatically scans your project's grimoire of files, carefully avoiding binary artifacts
- 📜 Respects ancient incantations like `.gitignore` rules
- 🌊 Streams Claude's mystical thinking process as it crafts responses
- 🪄 Magically applies code changes with a single command
- 🧪 Powerful file filtering to focus the AI's attention on specific scrolls of code
- 📚 Handles file output with proper directory creation spells
- 📥 Supports reading enchantments from stdin

## 🧙 Installation

Summon the Wizard to your environment:

```bash
pip install wizard-prompt-cli
```

Or conjure it from source:

```bash
git clone https://github.com/ddrscott/wizard-prompt-cli.git
cd wizard-prompt-cli
pip install -e .
```

## 🪄 Usage

Wizard Prompt CLI offers two main incantations:

### 📝 Prompt Command

Invoke Claude with your questions and project files:

```bash
wiz prompt "How can I improve this code?"
```

Include specific scrolls:

```bash
wiz prompt -f main.py -f utils.py "How can I make these files more efficient?"
```

Options:
- `-f, --file`: Specify files to include (can be used multiple times)
- `-o, --output`: Location to write response (default: `.response.md`)

The wizard's response will be saved to `.response.md` by default, and a copy of the full messages including system prompt will be saved to `.messages.md`.

### ✨ Apply Command

Cast the spell to implement the suggested changes:

```bash
wiz apply
```

Or specify a different spell book:

```bash
wiz apply custom_response.md
```

You can also channel content directly to the apply command:

```bash
cat response.md | wiz apply -
```

## 📚 How It Works

1. The `prompt` command channels your question and file contents to Claude
2. Claude weaves a spell over your files and provides a response with suggested changes
3. Changes are formatted with `[FILE path]...[/FILE]` magical markers
4. The `apply` command interprets these markers and transforms your files

## 🌟 Examples

Ask the wizard to refactor a specific function:

```bash
wiz prompt -f src/utils.py "Refactor the parse_data function to be more efficient"
```

Conjure a new feature:

```bash
wiz prompt "Add a progress bar to the file processing function"
```

Then cast the spell to apply the changes:

```bash
wiz apply
```

Or channel the response directly:

```bash
wiz prompt "Fix bugs" | wiz apply -
```

## 📜 License

[MIT License](LICENSE)

---

<p align="center">
  <a href="https://github.com/ddrscott/wizard-prompt-cli">
    <img src="https://img.shields.io/github/stars/ddrscott/wizard-prompt-cli.svg?style=social&label=Star&maxAge=2592000" alt="GitHub stars">
  </a>
</p>

<p align="center">
  <i>✨ If this magical tool helped you, consider giving it a star! ✨</i>
</p>
