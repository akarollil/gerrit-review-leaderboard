"""For pulling gerrit changes based on existing changes in database and
persisting
"""
from datetime import datetime, timedelta
import logging

from . import database_helper
from ..gerrit_handler import fetch


# Pull up to 6 months of changes
MAX_MONTHS = 6
MAX_DAYS = MAX_MONTHS * 30


def _do_pull(host_name, port=29418):
    """Pull changes from gerrit that are not in database

    Pull changes from gerrit created after change last saved into
    database, limited to a maximum time period of MAX_MONTHS

    :arg str hostname: gerrit server hostname
    :arg int port: port for gerrit service
    :Return: List of Change objects if any, empty list otherwise
    """
    # Latest timestamp found for a change in the database. Changes after this
    # timestamp will be pulled, but the time is limited to MAX_DAYS
    last_synced_change_datetime_utc = database_helper.get_last_synced_change_timestamp()
    logging.info(
        "Last pulled change has UTC datetime: %s",
        last_synced_change_datetime_utc)
    current_datetime_utc = datetime.utcnow()
    # If no changes found, pull changes since MAX_DAYS prior to now
    max_days_ago_datetime_utc = current_datetime_utc - timedelta(days=MAX_DAYS)
    fetch_after_datetime_utc = None
    if not last_synced_change_datetime_utc:
        # fetch MAX_DAYS worth of prior changes if no changes exist in database
        fetch_after_datetime_utc = max_days_ago_datetime_utc
    else:
        # fetch changes since timestamp of latest change in database only if
        # not more than MAX_DAYS have elapsed since then
        days_to_pull = abs(
            current_datetime_utc -
            last_synced_change_datetime_utc).days
        if days_to_pull > MAX_DAYS:
            logging.info(
                "%d days elapsed since last pull. Only pulling last %d days.",
                days_to_pull, MAX_DAYS)
            # fetch MAX_DAYS worth of prior changes
            fetch_after_datetime_utc = max_days_ago_datetime_utc
        else:
            logging.info("Fetching changes since last pull...")
            # fetch all changes since last fetched change
            fetch_after_datetime_utc = last_synced_change_datetime_utc

    return fetch.fetch_changes(host_name, fetch_after_datetime_utc, port)


def pull_and_store_changes(hostname):
    """Pull changes from gerrit, process, and store in database

    Pulls changes since last pull up to a maximum of MAX_DAYS, and
    updates reviewer, changes, and comments tables in database. Links
    changes and comments to reviewers. Links comments to changes.

    :arg str hostname: gerrit server hostname
    :arg int port: port for gerrit service
    """

    gerrit_changes = _do_pull(hostname)
    database_helper.update(gerrit_changes)
