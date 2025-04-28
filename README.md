# RSS Feed Summarizer

This project fetches posts from multiple RSS feeds, summarizes new entries using an AI model via the [LLM](https://github.com/simonw/llm) library, and serves the generated summary as a new RSS feed.

## Features

- Fetches entries from a configurable list of RSS feeds (`feeds.yml`).
- Filters entries based on a configurable lookback period (e.g., last 24 hours).
- Uses the [LLM](https://github.com/simonw/llm) library to generate summaries, allowing flexibility in choosing AI models.
- Uses a Jinja2 template (`prompt.j2`) for customizable AI prompts.
- Generates a persistent RSS feed (`rss/feed.xml`) containing the summaries.
- Runs a simple HTTP server to make the generated feed accessible.
- Containerized for easy deployment using Docker and Docker Compose (recommended).

## Getting Started (Docker Compose)

The easiest and recommended way to run the application is using Docker Compose.

**Prerequisites:**
- Docker Engine
- Docker Compose

**Steps:**

1.  **Clone the repository:**
    ```bash
    git clone https://github.com/your-username/rss-summary.git # Replace with your repo URL if needed
    cd rss-summary
    ```
2.  **Configure Environment Variables:**
    Copy the example environment file and edit it with your settings:
    ```bash
    cp .env.example .env
    ```
    Open `.env` in a text editor and add your `ANTHROPIC_API_KEY` (or API key for your chosen LLM provider). You can also customize other variables like `LLM_MODEL`, `RSS_LOOKBACK_HOURS`, `RSS_SERVER_PORT`, etc.

3.  **Configure Feeds:**
    Create a `feeds.yml` (see `feeds.yml.example`) and list the RSS feeds you want to summarize.

4.  **Customize Prompt (Optional):**
    Modify `prompt.j2` to change how the AI is prompted to create summaries.

5.  **Build and Run:**
    ```bash
    docker-compose up --build -d
    ```
    This command builds the Docker image (if it doesn't exist) and starts the service in the background.

6.  **Access the Feed:**
    The generated summary feed will be available at `http://localhost:8080/feed.xml` (or the port specified in your `.env` file). The feed file is also persisted in the local `./rss` directory.

7.  **View Logs:**
    ```bash
    docker-compose logs -f
    ```

8.  **Stop the Service:**
    ```bash
    docker-compose down
    ```

## Configuration

Configuration is managed through environment variables and configuration files:

-   **`.env` file:** Stores secrets (like API keys) and runtime settings (LLM model, ports, intervals, lookback period). See `.env.example` for available options.
-   **`feeds.yml`:** Defines the list of source RSS feeds to monitor.
-   **`prompt.j2`:** A Jinja2 template file used to construct the prompt sent to the LLM for summarization.

## Alternative: Running Locally with `uv`

If you prefer not to use Docker, you can run the script directly using `uv`.

**Prerequisites:**
- Python 3.x
- `uv` (Python package installer/resolver)

**Steps:**

1.  **Install Dependencies:**
    ```bash
    uv sync
    ```
2.  **Set Environment Variables:**
    You need to export the required environment variables directly in your shell or use a tool like `direnv`. Minimally, you need the API key for your chosen LLM provider:
    ```bash
    export ANTHROPIC_API_KEY="your-api-key-here"
    # Export other variables as needed (LLM_MODEL, RSS_LOOKBACK_HOURS, etc.)
    ```
3.  **Configure Feeds & Prompt:**
    Ensure `feeds.yml` and `prompt.j2` are configured as described above.

4.  **Run the Script:**
    ```bash
    uv run python rss_summarizer.py
    ```
    The script will start, fetch feeds, generate the initial summary, start the HTTP server, and then enter its refresh cycle.

## License

This project is licensed under the GNU General Public License v3.0 - see the [LICENSE](LICENSE) file for details (you may need to create this file).
