#!/usr/bin/env python3
"""
RSS Feed Summarizer using Claude AI

This script fetches RSS feed content from a provided URL, processes entries from the last 24 hours,
and uses Anthropic's Claude AI to generate a summary of the content.
"""

import os
import sys
import time
import datetime
import feedparser
import yaml
from dateutil import parser as date_parser
import llm # Use the llm library
from feedgen.feed import FeedGenerator
import http.server
import socketserver
import threading
import functools # For http server directory binding
import logging
from jinja2 import Environment, FileSystemLoader, select_autoescape # Add Jinja2 imports
from apscheduler.schedulers.blocking import BlockingScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.schedulers import base

def get_recent_entries(feed_url):
    """
    Fetch entries from the RSS feed published within a configurable lookback period.
    The lookback period (in hours) is set by the RSS_LOOKBACK_HOURS env var, defaulting to 24.
    """
    # Get lookback hours from env var, default to 24
    try:
        lookback_hours = int(os.environ.get("RSS_LOOKBACK_HOURS", 24))
        if lookback_hours <= 0:
            logging.warning("RSS_LOOKBACK_HOURS must be positive. Using default 24 hours.")
            lookback_hours = 24
    except ValueError:
        logging.warning("Invalid RSS_LOOKBACK_HOURS value. Using default 24 hours.")
        lookback_hours = 24

    # Log the attempt
    logging.debug(f"Attempting to fetch entries from the last {lookback_hours} hours for: {feed_url}")

    try:
        feed = feedparser.parse(feed_url)
        # Note: feedparser usually returns an empty list, not None or error on no entries
        # if not feed.entries:
        #     logging.warning(f"No entries found in feed: {feed_url}")
        #     # Don't exit here, just return empty list later
        # Get current time and calculate cutoff based on lookback_hours
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(hours=lookback_hours)

        # Filter entries published after the cutoff time
        recent_entries = []
        for entry in feed.entries:
            if hasattr(entry, 'published'):
                try:
                    pub_date = date_parser.parse(entry.published)
                    if pub_date > cutoff:
                        recent_entries.append(entry)
                except Exception as e:
                    logging.warning(f"Could not parse date for entry: {e}")

        # Log the count of filtered entries before returning
        logging.info(f"Fetched {len(recent_entries)} items from the last {lookback_hours} hours for feed: {feed_url}")
        return recent_entries
    except Exception as e:
        logging.error(f"Error fetching or parsing RSS feed for {feed_url}: {e}")
        # Return empty list instead of exiting, so other feeds can be tried
        return [] 

def load_feeds_from_yaml():
    """
    Load feed URLs from a YAML file specified by the RSS_FEEDS_CONFIG env var,
    defaulting to 'feeds.yml'.
    """
    # Get config file path from env var, default to 'feeds.yml'
    filepath = os.environ.get("RSS_FEEDS_CONFIG", "feeds.yml")
    logging.info(f"Loading feeds from: {filepath}")

    try:
        with open(filepath, 'r') as f:
            config = yaml.safe_load(f)
            if config and 'feeds' in config and isinstance(config['feeds'], list):
                # Extract URLs from the list of dictionaries
                urls = [feed.get('url') for feed in config['feeds'] if isinstance(feed, dict) and 'url' in feed]
                if not urls:
                    logging.error(f"No valid feed URLs found in {filepath}")
                    sys.exit(1)
                return urls
            else:
                logging.error(f"Invalid format in {filepath}. Expected a 'feeds' list with 'url' keys.")
                sys.exit(1)
    except FileNotFoundError:
        logging.error(f"Configuration file {filepath} not found.")
        sys.exit(1)
    except yaml.YAMLError as e:
        logging.error(f"Error parsing YAML file {filepath}: {e}")
        sys.exit(1)
    except Exception as e:
        logging.error(f"An unexpected error occurred while loading feeds: {e}")
        sys.exit(1)

# --- RSS Feed Generation ---

def generate_rss_feed(summary_text, feed_file_path):
    """
    Generates an RSS feed file, prepending the new summary to existing entries.
    """
    fg = FeedGenerator()
    feed_abspath = os.path.abspath(feed_file_path)
    feed_link = f"file://{feed_abspath}" # Default link

    # --- Default Feed Metadata (configurable via Env Vars) ---
    default_title = os.environ.get("RSS_FEED_TITLE", "AI Generated Feed Summary")
    default_desc = 'Daily summary of RSS feeds summarized by LLMs.' # Description could also be configurable if needed
    default_lang = 'en' # Language could also be configurable if needed

    # --- Add the NEW entry first ---
    fe_new = fg.add_entry(order='prepend') # Add new entry at the beginning
    # Get current time in local timezone
    now_local = datetime.datetime.now().astimezone() 
    # Format title with local time and timezone name (e.g., EST, PDT)
    entry_title = f"Summary for {now_local.strftime('%Y-%m-%d %H:%M:%S %Z')}" 
    fe_new.title(entry_title)
    # Use local time's ISO format for ID
    fe_new.id(f"urn:uuid:{now_local.isoformat()}") 
    fe_new.link(href=feed_link) # Link entry back to the feed itself (can be improved later)
    fe_new.content(summary_text, type='html')
    # Use the timezone-aware local datetime for pubDate
    fe_new.pubDate(now_local) 

    # --- Load existing entries if feed file exists ---
    parsed_feed = None
    if os.path.exists(feed_file_path):
        try:
            logging.info(f"Loading existing feed from: {feed_file_path}")
            parsed_feed = feedparser.parse(feed_file_path)
            if parsed_feed.bozo:
                 # Error during parsing
                 raise ValueError(f"Feed parsing error: {parsed_feed.bozo_exception}")
        except Exception as e:
            logging.warning(f"Could not parse existing feed file '{feed_file_path}'. A new feed will be created. Error: {e}")
            parsed_feed = None # Reset on error

    # --- Set Feed Metadata (from parsed feed or defaults) ---
    if parsed_feed and parsed_feed.feed:
        feed_title = parsed_feed.feed.get('title', default_title)
        # Try getting the 'alternate' link first
        feed_links = parsed_feed.feed.get('links', [])
        feed_link_href = next((link.get('href') for link in feed_links if link.get('rel') == 'alternate'), None)
        if feed_link_href is None: # Fallback to the main link if no alternate
             feed_link_href = parsed_feed.feed.get('link', feed_link)

        feed_desc = parsed_feed.feed.get('description', default_desc)
        feed_lang = parsed_feed.feed.get('language', default_lang)
        
        fg.title(feed_title)
        fg.link(href=feed_link_href, rel='alternate')
        fg.description(feed_desc)
        fg.language(feed_lang)

        # --- Add OLD entries ---
        logging.info(f"Adding {len(parsed_feed.entries)} existing entries.")
        for entry in parsed_feed.entries:
            fe_old = fg.add_entry(order='append') # Append old entries
            fe_old.title(entry.get('title', ''))
            fe_old.id(entry.get('id', entry.get('link', ''))) # Use id or link as fallback
            fe_old.link(href=entry.get('link', ''))

            # Handle content vs summary vs description, prefer content
            content_detail = entry.get('content')
            if content_detail:
                 # feedparser returns a list for content, usually with one item
                 content_value = content_detail[0].get('value')
                 content_type = content_detail[0].get('type', 'text/plain')
                 # Map common types to what feedgen expects
                 if 'html' in content_type:
                     fe_old.content(content_value, type='html')
                 else:
                     fe_old.content(content_value, type='text')
            elif entry.get('summary'):
                 fe_old.summary(entry.get('summary')) # feedgen uses summary()
            elif entry.get('description'):
                 fe_old.description(entry.get('description')) # feedgen uses description()

            # Use published_parsed or updated_parsed from feedparser
            pub_date_parsed = entry.get('published_parsed') or entry.get('updated_parsed')
            if pub_date_parsed:
                 # Convert struct_time (often UTC) to a timezone-aware UTC datetime
                 dt_aware_utc = datetime.datetime.fromtimestamp(time.mktime(pub_date_parsed), tz=datetime.timezone.utc)
                 # Convert UTC datetime to local timezone
                 dt_local = dt_aware_utc.astimezone()
                 fe_old.pubDate(dt_local)
            elif entry.get('published'): # Fallback to parsing string if parsed version not available
                 try:
                     # Parse the date string
                     dt_parsed = date_parser.parse(entry.get('published'))
                     # Ensure it's timezone-aware (assume UTC if naive)
                     if dt_parsed.tzinfo is None:
                         dt_parsed = dt_parsed.replace(tzinfo=datetime.timezone.utc)
                     # Convert to local timezone
                     dt_local = dt_parsed.astimezone()
                     fe_old.pubDate(dt_local)
                 except Exception as date_exc:
                     logging.warning(f"Could not parse or convert date for old entry '{entry.get('title', '')}': {date_exc}")
                     pass # Ignore if date parsing/conversion fails

    else:
        # Set default metadata if feed didn't exist or parsing failed
        fg.title(default_title)
        fg.link(href=feed_link, rel='alternate')
        fg.description(default_desc)
        fg.language(default_lang)


    try:
        # Ensure the output directory exists
        os.makedirs(os.path.dirname(feed_file_path), exist_ok=True)
        # Generate the RSS feed file
        fg.rss_file(feed_file_path, pretty=True)
        logging.info(f"RSS feed updated successfully: {feed_file_path}")
    except Exception as e:
        logging.error(f"Error writing RSS feed file: {e}")


# --- HTTP Server ---

def start_http_server(directory, port):
    """Starts a simple HTTP server in a background thread."""
    Handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=directory)
    # Suppress standard request logging from SimpleHTTPRequestHandler
    Handler.log_message = lambda *args: None 
    httpd = socketserver.TCPServer(("", port), Handler)

    logging.info(f"Serving RSS feed from directory '{directory}' on port {port}")
    logging.info(f"Feed URL: http://localhost:{port}/feed.xml") # Assuming feed is named feed.xml

    # Run the server in a separate thread
    server_thread = threading.Thread(target=httpd.serve_forever)
    server_thread.daemon = True # Allows program to exit even if thread is running
    server_thread.start()


# --- Core Logic ---

# Removed format_entries_for_prompt function
# Removed get_prompt function

def summarize_with_llm(entries):
    """
    Use the llm library to summarize the entries with the configured model.
    """
    # --- Get Model ID (with default) ---
    default_model_id = "claude-3.5-sonnet"
    env_model_id = os.environ.get("LLM_MODEL") # Check if it's set first

    if env_model_id is None:
        model_id = default_model_id
        logging.info(f"LLM_MODEL not set. Using default value: {model_id}")
    else:
        model_id = env_model_id
        logging.info(f"Using LLM_MODEL value from environment: {model_id}")

    # --- Get Max Tokens (with default) ---
    max_tokens_str = os.environ.get("LLM_MAX_TOKENS")
    default_max_tokens = 4096
    if max_tokens_str is None:
        max_tokens = default_max_tokens
        logging.info(f"LLM_MAX_TOKENS not set. Using default value: {max_tokens}")
    else:
        try:
            max_tokens = int(max_tokens_str)
            if max_tokens <= 0:
                logging.warning(f"Invalid LLM_MAX_TOKENS value '{max_tokens_str}'. Must be a positive integer. Using default: {default_max_tokens}")
                max_tokens = default_max_tokens
            else:
                logging.info(f"Using LLM_MAX_TOKENS value: {max_tokens}")
        except ValueError:
            logging.warning(f"Invalid LLM_MAX_TOKENS value '{max_tokens_str}'. Must be an integer. Using default: {default_max_tokens}")
            max_tokens = default_max_tokens


    # --- Get Model Instance ---
    try:
        model = llm.get_model(model_id)
        # Note: llm library handles API key lookup via env vars (ANTHROPIC_API_KEY)
        # or its own key management ('llm keys set anthropic').
        # No need for explicit key handling here unless overriding.
        logging.info(f"Using LLM model: {model.model_id}")
    except llm.UnknownModelError:
        logging.error(f"Unknown LLM model specified: {model_id}. Is the required plugin (e.g., llm-anthropic) installed?")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error getting LLM model '{model_id}': {e}")
        sys.exit(1)


    # --- Load and render Jinja2 template ---
    try:
        # Set up Jinja2 environment to load templates from the current directory
        env = Environment(
            loader=FileSystemLoader('.'), # Look for templates in the current dir
            autoescape=select_autoescape(['html', 'xml']) # Basic autoescaping
        )
        template = env.get_template("prompt.j2")

        # Get lookback hours for the template context
        try:
            lookback_hours = int(os.environ.get("RSS_LOOKBACK_HOURS", 24))
            if lookback_hours <= 0: lookback_hours = 24 # Ensure positive
        except ValueError:
            lookback_hours = 24

        # Render the template with the entries and lookback hours
        rendered_prompt = template.render(entries=entries, num_hours=lookback_hours)
        logging.debug("Successfully rendered Jinja2 template.")

    except Exception as e:
        logging.error(f"Error rendering Jinja2 template 'prompt.j2': {e}", exc_info=True)
        return None # Cannot proceed without a prompt

    # --- Call LLM ---
    try:
        # The system prompt is embedded within the user prompt via the Jinja template
        response = model.prompt(
            rendered_prompt,
            # Pass max_tokens as an option if the model supports it
            # Note: Check model options with 'llm models --options'
            # For Claude via llm-anthropic, max_tokens is a standard parameter.
            #max_tokens=max_tokens
        )
        logging.info(f"LLM response received (HTTP 200 OK). Waiting for full text content...")
        # response.text() handles potential streaming and returns the full string
        summary_text = response.text()
        logging.info(f"Full text content received from LLM model {model.model_id}.")
        # Optional: Log token usage if needed
        # try:
        #     usage = response.usage # Corrected: usage is often an attribute or method call result
        #     # Example assuming usage is a dict-like object or has attributes
        #     input_tokens = getattr(usage, 'input_tokens', None) or usage.get('input_tokens', 'N/A')
        #     output_tokens = getattr(usage, 'output_tokens', None) or usage.get('output_tokens', 'N/A')
        #     logging.info(f"LLM Usage - Input Tokens: {input_tokens}, Output Tokens: {output_tokens}")
        # except AttributeError: # Handle cases where usage object structure is different
        #     logging.debug("Could not retrieve token usage information (AttributeError). Usage object: %s", usage)
        # except Exception as usage_exc: # Catch other potential errors
        #     logging.debug("Could not retrieve token usage information: %s", usage_exc)
        return summary_text
    except Exception as e:
        logging.error(f"Error calling LLM model {model.model_id}: {e}", exc_info=True) # Add traceback
        return None

def run_summary_cycle(feed_file_path):
    """
    Performs one cycle of fetching, summarizing, and saving the feed.
    """
    logging.info(f"--- Starting summary cycle at {datetime.datetime.now()} ---")
    feed_urls = load_feeds_from_yaml()

    if not feed_urls:
        logging.warning("No feed URLs loaded. Skipping cycle.")
        return

    all_entries = []
    # Get recent entries for each feed based on the lookback window
    for feed_url in feed_urls:
        # Fetch entries first using the updated function
        entries = get_recent_entries(feed_url)
        # Log the result after fetching (message now includes lookback period)
        # print(f"Fetched {len(entries)} items from feed: {feed_url}") # Log is now inside get_recent_entries
        if entries:
            all_entries.extend(entries)
        # No need for an else here, the count in the log message indicates 0 entries

    if not all_entries:
        logging.info("No new entries found across all feeds in the lookback period.")
        # Don't exit, just skip generating a summary for this cycle
        return

    # Sort entries by published date (newest first)
    all_entries.sort(key=lambda x: date_parser.parse(x.published) if hasattr(x, 'published') else datetime.datetime.min.replace(tzinfo=datetime.timezone.utc), reverse=True)

    # Removed formatting step, pass raw entries to summarizer
    # entries_text = format_entries_for_prompt(all_entries)
    
    # Get summary from the configured LLM using the raw entries list
    summary = summarize_with_llm(all_entries)

    if summary:
        # Generate the RSS feed file
        generate_rss_feed(summary, feed_file_path)
    else:
        logging.error("Failed to generate summary from LLM. Skipping feed update.")

    logging.info(f"--- Summary cycle finished at {datetime.datetime.now()} ---")


def main():
    """
    Main function to set up the server and run the summary loop.
    """
    # Configuration from environment variables
    output_dir = os.environ.get("RSS_OUTPUT_DIR", "./rss")
    server_port = int(os.environ.get("RSS_SERVER_PORT", 8080))
    # Default cron schedule: daily at 9:00 AM UTC
    cron_schedule = os.environ.get("RSS_CRON_SCHEDULE", "0 9 * * *")
    feed_filename = "feed.xml"
    feed_file_path = os.path.join(output_dir, feed_filename)

    # --- Configure Logging ---
    logging.basicConfig(level=logging.INFO,
                        format='%(asctime)s - %(levelname)s - %(message)s',
                        datefmt='%Y-%m-%d %H:%M:%S')
    # Make APScheduler less verbose by default
    logging.getLogger('apscheduler.executors.default').setLevel(logging.WARNING)
    logging.getLogger('apscheduler.scheduler').setLevel(logging.INFO)


    logging.info("--- RSS Summarizer Service Starting ---")
    logging.info(f"Output Directory: {os.path.abspath(output_dir)}")
    logging.info(f"Server Port: {server_port}")
    logging.info(f"Cron Schedule: '{cron_schedule}' (Local Time)")
    logging.info(f"Feed File: {feed_file_path}")
    logging.info("---------------------------------------")

    # Ensure output directory exists
    try:
        os.makedirs(output_dir, exist_ok=True)
    except Exception as e:
        logging.error(f"Error creating output directory '{output_dir}': {e}")
        sys.exit(1)

    # Start the HTTP server in a background thread
    start_http_server(output_dir, server_port)

    # --- Set up Scheduler ---
    # By default, BlockingScheduler uses the system's local timezone
    scheduler = BlockingScheduler() 

    try:
        # Schedule the first run immediately, then follow the cron schedule
        scheduler.add_job(
            run_summary_cycle,
            args=[feed_file_path],
            id='initial_summary_run', # Give the job an ID
            name='Run summary cycle once on startup'
        )
        logging.info("Scheduled initial summary run.")

        # Schedule the recurring job based on the cron string
        # CronTrigger uses the scheduler's timezone by default (which is now local)
        scheduler.add_job(
            run_summary_cycle,
            trigger=CronTrigger.from_crontab(cron_schedule),
            args=[feed_file_path],
            id='recurring_summary_run', # Give the job an ID
            name=f'Run summary cycle based on cron: {cron_schedule}',
            replace_existing=True # Replace if ID exists (useful for potential restarts)
        )
        logging.info(f"Scheduled recurring summary run with cron: '{cron_schedule}' (Local Time)")

    except ValueError as e:
        logging.error(f"Invalid cron string format '{cron_schedule}': {e}")
        logging.error("Please check the RSS_CRON_SCHEDULE environment variable.")
        sys.exit(1)
    except Exception as e:
        logging.error(f"Error setting up scheduler: {e}", exc_info=True)
        sys.exit(1)


    logging.info("Scheduler started. Press Ctrl+C to exit.")
    try:
        # Start the scheduler (this blocks the main thread)
        scheduler.start()
    except (KeyboardInterrupt, SystemExit):
        logging.info("Shutdown requested. Stopping scheduler...")
        scheduler.shutdown()
        logging.info("Scheduler stopped. Exiting.")
        sys.exit(0)
    except Exception as e:
        logging.error(f"An unexpected error occurred in the scheduler: {e}", exc_info=True)
        scheduler.shutdown() # Attempt graceful shutdown
        sys.exit(1)


if __name__ == "__main__":
    main()
