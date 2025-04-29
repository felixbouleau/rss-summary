# RSS Feed Summarizer

This project:

- Fetches entries from a configurable list of RSS feeds (`feeds.yml`).
- Filters entries based on a configurable lookback period (e.g., last 24 hours).
- Uses [LLM](https://github.com/simonw/llm) to generate summaries, allowing flexibility in choosing AI models.
- Uses a Jinja2 template (`prompt.j2`) for customizable AI prompts.
- Generates a persistent RSS feed (`rss/feed.xml`) containing the summaries.
- Runs a simple HTTP server to make the generated feed accessible.


## Running it

I run this in Docker, side by side with [Miniflux](https://github.com/miniflux/v2) and [reddit-top-rss](https://github.com/johnwarne/reddit-top-rss):

```yml
    # [...]
    rss-summarizer:
        image: ghcr.io/felixbouleau/rss-summary:main
        env_file:
        - .env
        volumes:
        - rss-summary-feeds:/app/rss
        - ./feeds.yml:/app/feeds.yml:ro
        restart: unless-stopped
volumes:
    rss-summary-feeds:
```

The only env var I set up in .env is ANTHROPIC_API_KEY, but you can check out .env.example for a full list of options. If you want to customize the prompt you can edit prompt.j2 and bind mount it into `/app` to replace the default one.

I then add a new feed (`http://rss-summarizer:8080/feed.xml`) to Miniflux.

