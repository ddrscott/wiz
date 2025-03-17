# 🧙‍♂️ Wizard Prompt CLI

> *Summon the power of Claude AI to transform your code with a wave of your terminal wand!*

[![PyPI version](https://img.shields.io/pypi/v/wizard-prompt-cli.svg)](https://pypi.org/project/wizard-prompt-cli/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

Wizard Prompt CLI is a magical command-line interface that conjures Claude AI to analyze, enhance, and transform your project files. Ask questions about your code in natural language, and watch as the AI wizard works its spells to provide insights and implement changes.

## ⚠️ Important: API Key Required

This tool requires an **Anthropic API key** to function. You must set the `ANTHROPIC_API_KEY` environment variable before using any commands. See the [API Key Setup](#-api-key-setup) section below for details.

**Without this environment variable set, no commands will work!**

```bash
# Set this before using any wiz commands
export ANTHROPIC_API_KEY=your_api_key_here
```

## ✨ Magical Features

- 🔮 Automatically scans your project's grimoire of files, carefully avoiding binary artifacts
- 📜 Respects ancient incantations like `.gitignore` rules
- 🌊 Streams Claude's mystical thinking process as it crafts responses
- 🪄 Magically applies code changes with a single command
- 🧪 Powerful file filtering to focus the AI's attention on specific scrolls of code
- 📚 Handles file output with proper directory creation spells
- 📥 Supports reading enchantments from stdin
- 🖼️ Includes image attachment capabilities for visual context
- 🚫 Exclude files via regex patterns to fine-tune your magical selection
- 📋 Preview files that would be included before spending API tokens
- 📝 Supports `.wizrc` configuration file for persistent command-line arguments

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

## 🔑 API Key Setup

Before casting spells, you need to obtain your magical key:

1. Create an account at [Anthropic](https://console.anthropic.com/) if you don't have one
2. Generate an API key from your Anthropic dashboard
3. Set the environment variable with your secret key:

```bash
# For Linux/macOS
export ANTHROPIC_API_KEY=your_api_key_here

# For Windows (Command Prompt)
set ANTHROPIC_API_KEY=your_api_key_here

# For Windows (PowerShell)
$env:ANTHROPIC_API_KEY="your_api_key_here"
```

For permanent enchantment, add this to your shell profile (.bashrc, .zshrc, etc.).

> 🔴 **Note**: The `ANTHROPIC_API_KEY` environment variable is **required**. The tool will not function without it properly set. If you encounter errors about unauthorized access or missing API keys, please verify this variable is correctly set.

## 📝 Configuration with .wizrc

You can store command configurations in a `.wizrc` YAML file in your project directory:

```yaml
# Example .wizrc file
files:
  exclude: ["*test*"]
  image: ["screenshot.png"]
  max_tokens: 80000

# Example .wizrc configuration
files: &files
  exclude: ["*.log", "build", "dist"]
  
prompt:
  <<: *files
```

The tool will automatically load this configuration and apply it to corresponding commands. The example above shows:
- Setting exclusion patterns to ignore specific files 
- Using YAML anchors (`&files`) to define common configurations
- Inheriting settings between commands with YAML merge keys (`<<: *files`)
- Configuring command-specific options like max_tokens

Each top-level key in the YAML corresponds to a subcommand, with nested options matching the command's options. All configuration is completely optional, and command-line arguments will override settings in `.wizrc` when provided.

The `.wizrc` file is automatically excluded from git via `.gitignore`.

## 🪄 Usage

Wizard Prompt CLI offers three main incantations and supports configuration via a `.wizrc` file:

### 📝 Prompt Command

Invoke Claude with your questions and project files:

```bash
wiz prompt "How can I improve this code?"
```

Include specific scrolls:

```bash
wiz prompt -f main.py -f utils.py "How can I make these files more efficient?"
```

Add images for visual context:

```bash
wiz prompt -i screenshot.png "What UI improvements would you suggest based on this screenshot?"
```

Exclude files matching a pattern:

```bash
wiz prompt -x ".*test.*\.py$" "Analyze all non-test Python files"
```

Options:
- `-f, --file`: Specify files to include (can be used multiple times)
- `-i, --image`: Include image files as context (can be used multiple times)
- `-o, --output`: Location to write response (default: `.response.md`)
- `-m, --max-tokens`: Maximum tokens for the response (default: 60000)
- `-t, --thinking-tokens`: Maximum tokens for Claude's thinking process (default: 16000)
- `-x, --exclude`: Regular expression pattern to exclude files

The wizard's response will be saved to `.response.md` by default, and a copy of the full messages including system prompt will be saved to `.messages.md`.

### 📋 Files Command

Preview which files would be included in a prompt without calling the API:

```bash
wiz files
```

This command accepts the same filtering options as `prompt`:

```bash
wiz files -f main.py -f utils.py
```

```bash
wiz files -x ".*test.*\.py$"
```

Options:
- `-f, --file`: Specify files to include (can be used multiple times)
- `-i, --image`: Include image files as context (can be used multiple times)
- `-x, --exclude`: Regular expression pattern to exclude files

Use this command to verify file selection before spending API tokens with a real prompt.

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

Get feedback on UI design with an image:

```bash
wiz prompt -i design.png -f styles.css "How can I improve this layout?"
```

Exclude test files when analyzing your codebase:

```bash
wiz prompt -x ".*test.*\.py$|__pycache__" "Review my Python code architecture"
```

Preview files that would be included in a complex filter:

```bash
wiz files -x "\.(json|md|txt)$"
```

Focus on specific file types by excluding others:

```bash
wiz prompt -x "\.(json|md|txt)$" "Analyze only my code files, not documentation or data"
```

Adjust token limits for complex analysis:

```bash
wiz prompt -m 80000 -t 20000 "Perform a comprehensive security audit of this codebase"
```

Then cast the spell to apply the changes:

```bash
wiz apply
```

Or do it all in one and see the output at the same time:

```bash
wiz prompt "Fix bugs" | tee -a /dev/tty | wiz apply -
```

## 🔄 Git Integration Best Practices

When using Wizard Prompt CLI to modify your code, it's essential to integrate with Git or your preferred version control system to keep track of changes and maintain safety.

### Before Casting Spells

1. Commit your current changes to create a restore point:
   ```bash
   git add .
   git commit -m "Save state before wizard modifications"
   ```

2. Alternatively, create a new branch for experimental wizard changes:
   ```bash
   git checkout -b wizard-experiment
   ```

### After Applying Changes

1. Review all modifications with Git before committing:
   ```bash
   git diff
   ```

2. For a more detailed review, use a visual diff tool:
   ```bash
   git difftool
   ```

3. For a file-by-file review:
   ```bash
   git add -p
   ```

4. If you're satisfied with the changes:
   ```bash
   git add .
   git commit -m "Applied AI-suggested improvements to X"
   ```

5. If the wizard's spells went awry, revert the changes:
   ```bash
   git reset --hard HEAD~1  # If you committed before using wiz
   # or
   git checkout -- .        # If you haven't committed the wizard's changes
   ```

Always review changes carefully before committing them to your repository. The AI is powerful but not infallible - your expertise is the final arbiter of which magical transformations to keep!

## 🔧 Troubleshooting

If you encounter errors like "API key not found" or "Unauthorized", check that:

1. You have set the `ANTHROPIC_API_KEY` environment variable correctly
2. The API key is valid and active in your Anthropic account
3. You've correctly formatted the environment variable without extra spaces

You can verify your environment variable is set correctly with:

```bash
# Linux/macOS
echo $ANTHROPIC_API_KEY

# Windows PowerShell
echo $env:ANTHROPIC_API_KEY
```

## 📜 License

[MIT License](LICENSE)

---

## Star History

[![Star History Chart](https://api.star-history.com/svg?repos=wizard-prompt-cli/wizard-prompt-cli&type=Date)](https://star-history.com/#wizard-prompt-cli/wizard-prompt-cli&Date)

<p align="center">
  <i>✨ If this magical tool helped you, consider giving it a star! ✨</i>
</p>
