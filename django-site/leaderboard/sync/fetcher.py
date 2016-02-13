"""For pulling gerrit changes based on existing changes in database and
persisting
"""
import configparser
from datetime import datetime, timedelta
import logging

from . import database_helper
from ..gerrit_handler import fetch


# configuration file for fetching gerrit changes
CONFIG_FILE = "fetcher.cfg"
CONFIG_FILE_SECTION = "fetch"


def _do_pull(hostname, port, max_days):
    """Pull changes from gerrit that are not in database

    Pull changes from gerrit created after change last saved into
    database, limited to a maximum time period of max_days

    :arg str hostname: gerrit server hostname
    :arg int port: port for gerrit service
    :arg int max_days: maximum number of days of outstanding changes
        to pull
    :Return: List of Change objects if any, empty list otherwise
    """
    logging.info(
        "Pulling from %s:%s a maximum of %d days of changes..." %
        (hostname, port, max_days))
    # Latest timestamp found for a change in the database. Changes after this
    # timestamp will be pulled, but the time is limited to max_days
    last_synced_change_datetime_utc = database_helper.get_last_synced_change_timestamp()
    logging.info(
        "Last pulled change has UTC datetime: %s",
        last_synced_change_datetime_utc)
    current_datetime_utc = datetime.utcnow()
    # If no changes found, pull changes since max_days prior to now
    max_days_ago_datetime_utc = current_datetime_utc - timedelta(days=max_days)
    fetch_after_datetime_utc = None
    if not last_synced_change_datetime_utc:
        # fetch max_days worth of prior changes if no changes exist in database
        fetch_after_datetime_utc = max_days_ago_datetime_utc
    else:
        # fetch changes since timestamp of latest change in database only if
        # not more than max_days have elapsed since then
        days_to_pull = abs(
            current_datetime_utc -
            last_synced_change_datetime_utc).days
        if days_to_pull > max_days:
            logging.info(
                "%d days elapsed since last pull. Only pulling last %d days.",
                days_to_pull, max_days)
            # fetch max_days worth of prior changes
            fetch_after_datetime_utc = max_days_ago_datetime_utc
        else:
            logging.info("Fetching changes since last pull...")
            # fetch all changes since last fetched change
            fetch_after_datetime_utc = last_synced_change_datetime_utc

    return fetch.fetch_changes(hostname, fetch_after_datetime_utc,
                               port)


def _create_default_config_file(config):
    config[CONFIG_FILE_SECTION] = {'hostname': 'gerrit.myhost.com',
                                   'port': '29418',
                                   'maxdays': '180'}
    # write config file
    with open(CONFIG_FILE, 'w') as configfile:
        config.write(configfile)
    return config


def pull_and_store_changes():
    """Pull changes from gerrit, process, and store in database

    - Loads gerrit hostname, port, and the maximum number of days to
    pull from fetcher.conf
    - Pulls changes since last pull up to a maximum number of days, and
    updates reviewer, changes, and comments tables in database.
    - Links changes and comments to reviewers. Links comments to
    changes.

    """
    config = configparser.ConfigParser()
    if not config.read(CONFIG_FILE):
        logging.warning(
            "Configuration file %s not found, creating a default one",
            CONFIG_FILE)
        config = _create_default_config_file(config)

    hostname = config[CONFIG_FILE_SECTION]['hostname']
    port = int(config[CONFIG_FILE_SECTION]['port'])
    max_days = int(config[CONFIG_FILE_SECTION]['maxdays'])
    logging.info(
        "Loaded hostname: %s port: %d max_days: %d from %s",
        hostname, port, max_days, CONFIG_FILE)
    # pull changes
    gerrit_changes = _do_pull(hostname, port, max_days)
    # update database
    database_helper.update(gerrit_changes)
