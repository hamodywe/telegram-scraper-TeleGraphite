"""Command-line interface for TeleGraphite.

This module provides a command-line interface for fetching and saving posts from Telegram channels.
It handles command-line arguments, configuration, and execution of the fetcher.
"""

import argparse
import asyncio
import logging
import os
import sys
import traceback
from pathlib import Path

from telegraphite.client import TelegramClientManager
from telegraphite.errors import AuthenticationError, ConfigurationError, FetchError
from telegraphite.fetcher import ChannelFetcher
from telegraphite.logging_config import configure_logging
from telegraphite.store import PostStore


def setup_logging(verbose: bool = False, log_file: str = None):
    """Set up logging configuration.

    Args:
        verbose: Whether to enable verbose logging.
        log_file: Optional path to a log file.
    """
    configure_logging(verbose=verbose, log_file=log_file)


async def run_once(args):
    """Run the fetcher once.

    Args:
        args: Command-line arguments.
        
    Raises:
        AuthenticationError: If there is an error with Telegram authentication.
        FetchError: If there is an error fetching posts.
    """
    logger = logging.getLogger(__name__)
    try:
        async with TelegramClientManager(args.env_file) as client:
            store = PostStore(args.data_dir)
            # Prepare filter options
            filters = {
                "keywords": args.keywords or [],
                "media_only": args.media_only,
                "text_only": args.text_only,
            }
            
            # Prepare schedule options
            schedule = {
                "days": args.days or [],
                "times": args.times or [],
            }
            
            fetcher = ChannelFetcher(
                client=client,
                store=store,
                channels_file=args.channels_file,
                limit=args.limit,
                filters=filters,
                schedule=schedule,
                contact_patterns_file=args.contact_patterns_file,
            )
            posts = await fetcher.fetch_all_channels()
            logger.info(f"Fetched {len(posts)} posts from channels")
            
            # Save posts
            success = await fetcher.fetch_and_save()
            if success:
                logger.info("Successfully saved posts and media")
            else:
                logger.error("Failed to save some posts or media")
                
    except AuthenticationError as e:
        logger.error(f"Authentication error: {e}")
        raise
    except FetchError as e:
        logger.error(f"Error fetching posts: {e}")
        raise
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        logger.debug(traceback.format_exc())
        raise FetchError(f"Failed to fetch posts: {e}")


async def run_continuous(args):
    """Run the fetcher continuously with a specified interval.

    Args:
        args: Command-line arguments.
        
    Raises:
        KeyboardInterrupt: If the user interrupts the process.
    """
    logger = logging.getLogger(__name__)
    logger.info(f"Running continuously with {args.interval} seconds interval")
    
    while True:
        try:
            # Check if we should run based on schedule
            should_run = True
            
            # Check day of week if specified
            if args.days:
                current_day = datetime.now().strftime("%A").lower()
                if current_day not in args.days:
                    should_run = False
                    logger.info(f"Skipping run on {current_day} (not in schedule)")
            
            # Check time of day if specified
            if args.times and should_run:
                current_time = datetime.now().strftime("%H:%M")
                # Check if current time is close to any scheduled time (within 5 minutes)
                time_match = False
                for scheduled_time in args.times:
                    scheduled_hour, scheduled_minute = map(int, scheduled_time.split(':'))
                    current_hour, current_minute = map(int, current_time.split(':'))
                    
                    # Calculate difference in minutes
                    scheduled_minutes = scheduled_hour * 60 + scheduled_minute
                    current_minutes = current_hour * 60 + current_minute
                    diff_minutes = abs(scheduled_minutes - current_minutes)
                    
                    if diff_minutes <= 5:  # Within 5 minutes of scheduled time
                        time_match = True
                        break
                
                if not time_match:
                    should_run = False
                    logger.info(f"Skipping run at {current_time} (not in schedule)")
            
            if should_run:
                await run_once(args)
                
            logger.info(f"Sleeping for {args.interval} seconds...")
            await asyncio.sleep(args.interval)
        except KeyboardInterrupt:
            logger.info("Interrupted by user")
            break
        except AuthenticationError as e:
            logger.error(f"Authentication error: {e}")
            logger.info("Waiting 60 seconds before retrying...")
            await asyncio.sleep(60)  # Wait longer for auth errors
        except FetchError as e:
            logger.error(f"Error fetching posts: {e}")
            logger.info("Waiting 30 seconds before retrying...")
            await asyncio.sleep(30)
        except Exception as e:
            logger.error(f"Unexpected error: {e}")
            logger.debug(traceback.format_exc())
            logger.info("Waiting 10 seconds before retrying...")
            await asyncio.sleep(10)


def parse_args():
    """Parse command-line arguments.

    Returns:
        Parsed arguments.
    """
    # allow_abbrev=False: argparse otherwise accepts any unambiguous prefix,
    # so "--l" resolved against both --limit and --log-file and the run died
    # with "ambiguous option" instead of doing anything (issue #1). Prefixes
    # are not a documented interface here, and silently binding one to a
    # different option after a new flag is added is worse than rejecting it.
    parser = argparse.ArgumentParser(
        description="Fetch and save posts from Telegram channels",
        allow_abbrev=False,
    )

    parser.add_argument(
        "-c",
        "--channels-file",
        default="channels.txt",
        help="Path to file containing channel usernames (default: channels.txt)",
    )
    parser.add_argument(
        "-d",
        "--data-dir",
        default="data",
        help="Directory to store posts and media (default: data)",
    )
    parser.add_argument(
        "-e",
        "--env-file",
        default=".env",
        help="Path to .env file with API credentials (default: .env)",
    )
    parser.add_argument(
        "-l",
        "--limit",
        type=int,
        default=10,
        help="Maximum number of posts to fetch per channel (default: 10)",
    )
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )
    parser.add_argument(
        "--log-file",
        help="Path to log file (logs will be written to this file in addition to console)",
    )
    parser.add_argument(
        "--contact-patterns-file",
        default="contact_patterns.txt",
        help="Path to file containing email and phone patterns (default: contact_patterns.txt)",
    )
    parser.add_argument(
        "--config",
        help="Path to YAML configuration file",
    )
    
    # Filter options
    filter_group = parser.add_argument_group("filter options")
    filter_group.add_argument(
        "--keywords",
        nargs="+",
        help="Filter posts containing specific keywords",
    )
    filter_group.add_argument(
        "--media-only",
        action="store_true",
        help="Only fetch posts containing media (photos, documents)",
    )
    filter_group.add_argument(
        "--text-only",
        action="store_true",
        help="Only fetch posts containing text",
    )
    
    # Schedule options
    schedule_group = parser.add_argument_group("schedule options")
    schedule_group.add_argument(
        "--days",
        nargs="+",
        choices=["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"],
        help="Days of the week to run the fetcher (for continuous mode)",
    )
    schedule_group.add_argument(
        "--times",
        nargs="+",
        help="Times of day to run the fetcher in HH:MM format (for continuous mode)",
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Once command
    once_parser = subparsers.add_parser(
        "once", help="Fetch posts once and exit"
    )

    # Continuous command
    continuous_parser = subparsers.add_parser(
        "continuous", help="Fetch posts continuously"
    )
    continuous_parser.add_argument(
        "-i",
        "--interval",
        type=int,
        default=3600,
        help="Interval between fetches in seconds (default: 3600)",
    )

    args = parser.parse_args()

    # Default to 'once' if no command is specified
    if not args.command:
        args.command = "once"

    return args


def main():
    """Main entry point for the command-line interface.
    
    Returns:
        Exit code (0 for success, 1 for error).
    """
    try:
        args = parse_args()
        setup_logging(args.verbose, args.log_file)
        logger = logging.getLogger(__name__)
        
        # Create data directory if it doesn't exist
        Path(args.data_dir).mkdir(exist_ok=True, parents=True)

        # Check if channels file exists
        if not os.path.exists(args.channels_file):
            logger.error(f"Channels file not found: {args.channels_file}")
            logger.info("Create a text file with one channel username per line.")
            return 1

        # Check if .env file exists
        if not os.path.exists(args.env_file):
            logger.error(f".env file not found: {args.env_file}")
            logger.info("Create a .env file with API_ID and API_HASH from https://my.telegram.org/")
            return 1
            
        if args.command == "once":
            try:
                asyncio.run(run_once(args))
                return 0
            except (AuthenticationError, FetchError) as e:
                logger.error(str(e))
                return 1
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                logger.debug(traceback.format_exc())
                return 1
        elif args.command == "continuous":
            try:
                asyncio.run(run_continuous(args))
                return 0
            except KeyboardInterrupt:
                logger.info("Interrupted by user")
                return 0
            except Exception as e:
                logger.error(f"Unexpected error: {e}")
                logger.debug(traceback.format_exc())
                return 1
        else:
            logger.error("No command specified. Use 'once' or 'continuous'.")
            return 1
    except Exception as e:
        print(f"Error: {e}")
        return 1


if __name__ == "__main__":
    sys.exit(main())


if __name__ == "__main__":
    main()