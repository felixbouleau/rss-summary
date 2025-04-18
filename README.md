# RSS Feed Summarizer

This project fetches posts from an RSS feed and summarizes them using Anthropic's Claude AI.

## Features

- Fetches entries from an RSS feed (specifically configured for a Reddit worldnews feed)
- Filters entries from the last 24 hours
- Uses Claude AI to generate a concise summary of the content
- Outputs the summary to the console

## Requirements

- Python 3.8+
- An Anthropic API key

## Installation

This project uses `uv` for dependency management.

```bash
# Install dependencies
uv pip install -e .
```

## Usage

1. Make sure your Anthropic API key is set as an environment variable:

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

2. Run the script:

```bash
uv run rss_summarizer.py
```

## Configuration

- The prompt for Claude AI is stored in `prompt.txt` for easy editing
- The RSS feed URL is set in the `main()` function in `rss_summarizer.py`

## License

MIT