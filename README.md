# RSS Feed Summarizer

This project fetches posts from an RSS feed and summarizes them using Anthropic's Claude AI.

## Features

- Fetches entries from a list of RSS feed 
- Filters entries from the last 24 hours (configurable)
- Uses [LLM](https://github.com/simonw/llm) to generate a concise summary of the content with whatever model you prefer
- Outputs the summary to the console

## Usage

```bash
ANTHROPIC_API_KEY="your-api-key-here" uv run rss_summarizer.py
```

## Configuration

- The prompt for Claude AI is stored in `prompt.txt` for easy editing
- The RSS feed URL is set in the `main()` function in `rss_summarizer.py`

## License

MIT