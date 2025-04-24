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
import yaml  # Add yaml import
from dateutil import parser as date_parser
from anthropic import Anthropic

def get_entries_from_last_24h(feed_url):
    """
    Fetch entries from the RSS feed that were published in the last 24 hours.
    """
    try:
        feed = feedparser.parse(feed_url)
        if not feed.entries:
            print("Error: No entries found in the feed")
            sys.exit(1)
            
        # Get current time
        now = datetime.datetime.now(datetime.timezone.utc)
        cutoff = now - datetime.timedelta(hours=24)
        
        # Filter entries from the last 24 hours
        recent_entries = []
        for entry in feed.entries:
            if hasattr(entry, 'published'):
                try:
                    pub_date = date_parser.parse(entry.published)
                    if pub_date > cutoff:
                        recent_entries.append(entry)
                except Exception as e:
                    print(f"Warning: Could not parse date for entry: {e}")
        
        return recent_entries
    except Exception as e:
        print(f"Error fetching or parsing RSS feed: {e}")
        sys.exit(1)

def load_feeds_from_yaml():
    """
    Load feed URLs from a YAML file specified by the RSS_FEEDS_CONFIG env var,
    defaulting to 'feeds.yml'.
    """
    # Get config file path from env var, default to 'feeds.yml'
    filepath = os.environ.get("RSS_FEEDS_CONFIG", "feeds.yml")
    print(f"Loading feeds from: {filepath}") # Add info message

    try:
        with open(filepath, 'r') as f:
            config = yaml.safe_load(f)
            if config and 'feeds' in config and isinstance(config['feeds'], list):
                # Extract URLs from the list of dictionaries
                urls = [feed.get('url') for feed in config['feeds'] if isinstance(feed, dict) and 'url' in feed]
                if not urls:
                    print(f"Error: No valid feed URLs found in {filepath}")
                    sys.exit(1)
                return urls
            else:
                print(f"Error: Invalid format in {filepath}. Expected a 'feeds' list with 'url' keys.")
                sys.exit(1)
    except FileNotFoundError:
        print(f"Error: Configuration file {filepath} not found.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file {filepath}: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred while loading feeds: {e}")
        sys.exit(1)


def format_entries_for_prompt(entries):
    """
    Format RSS entries into a text format for the prompt.
    """
    formatted_text = ""
    
    for i, entry in enumerate(entries, 1):
        formatted_text += f"POST {i}:\n"
        formatted_text += f"Title: {entry.title}\n"
        formatted_text += f"Link: {entry.link}\n"
        
        if hasattr(entry, 'published'):
            formatted_text += f"Published: {entry.published}\n"
            
        if hasattr(entry, 'summary'):
            formatted_text += f"Summary: {entry.summary}\n"
        elif hasattr(entry, 'description'):
            formatted_text += f"Description: {entry.description}\n"
            
        formatted_text += "\n---\n\n"
    
    return formatted_text

def get_prompt():
    """
    Read the prompt from the prompt.txt file.
    """
    try:
        with open("prompt.txt", "r") as f:
            return f.read()
    except Exception as e:
        print(f"Error reading prompt file: {e}")
        sys.exit(1)

def summarize_with_claude(entries_text):
    """
    Use Claude API to summarize the entries.
    """
    api_key = os.environ.get("ANTHROPIC_API_KEY")
    if not api_key:
        print("Error: ANTHROPIC_API_KEY environment variable not set")
        sys.exit(1)
    
    client = Anthropic(api_key=api_key)
    prompt_text = get_prompt()
    
    # Get system prompt from env var, with a default
    default_system_prompt = "Summarize the provided content accurately and concisely."
    system_prompt = os.environ.get("CLAUDE_SYSTEM_PROMPT", default_system_prompt)
    print(f"Using system prompt: '{system_prompt}'") # Add info message

    try:
        message = client.messages.create(
            model="claude-3-5-haiku-20241022",
            max_tokens=1024,
            system=system_prompt, # Use the configured system prompt
            messages=[
                {
                    "role": "user",
                    "content": f"{prompt_text}\n\nHere are the Reddit posts from the last 24 hours:\n\n{entries_text}"
                }
            ]
        )
        return message.content[0].text
    except Exception as e:
        print(f"Error calling Claude API: {e}")
        sys.exit(1)

def main():
    """
    Main function to run the RSS summarizer.
    """
    feed_urls = load_feeds_from_yaml() # Load feeds (path determined internally)

    all_entries = []
    # Get entries from the last 24 hours for each feed
    for feed_url in feed_urls:
        print(f"Fetching entries from: {feed_url}")
        entries = get_entries_from_last_24h(feed_url)
        if entries:
            all_entries.extend(entries)
        else:
            print(f"No recent entries found for: {feed_url}")

    if not all_entries:
        print("No entries found from the last 24 hours across all feeds")
        sys.exit(0)

    # Sort entries by published date (newest first) - optional but good practice
    all_entries.sort(key=lambda x: date_parser.parse(x.published) if hasattr(x, 'published') else datetime.datetime.min.replace(tzinfo=datetime.timezone.utc), reverse=True)

    # Format entries for the prompt
    entries_text = format_entries_for_prompt(all_entries)
    
    # Get summary from Claude
    summary = summarize_with_claude(entries_text)
    
    # Print the summary
    print(summary)

if __name__ == "__main__":
    main()
