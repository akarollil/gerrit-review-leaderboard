#!/usr/bin/env python
"""Fetch changes from gerrit server using pygerrit
"""

import calendar
from datetime import datetime, timedelta
import getpass
import logging
import sys

from pygerrit.client import GerritClient
from pygerrit.error import GerritError


def _find_user_name():
    """Find user name of current user."""
    return getpass.getuser()


def fetch_changes(hostname, datetime_utc, port=29418):
    """Fetch merged changes from gerrit after timestamp.

    Connects to gerrit at given hostname via SSH and uses gerrit query
    to fetch all changes merged after given datetime. Expects current
    user to have public key.

    :arg str hostname: gerrit server hostname
    :arg datetime.datetime datetime_utc: datetime obj specifying time
         in UTC, changes fetched should have been merged after time
         specified
    :arg int port: port for gerrit service

    :Return: List of Change objects if any, empty list otherwise
    """
    # from http://review.cyanogenmod.org/Documentation/user-search.html
    # gerrit query time should be in the format:
    #
    #     2006-01-02[ 15:04:05[.890][ -0700]]
    #
    # NOTE: specifying anything other than the date results in the query
    # failing to return any changes even though they exist. So this won't work:
    # gerrit_query_time_format = "%Y-%m-%d %H:%M:%S".
    gerrit_query_time_format = "%Y-%m-%d"
    # since we can't specify timezone, the query date is in UTC
    time_utc_str = datetime_utc.strftime(gerrit_query_time_format)
    fetch_query = "status:merged after:%s" % time_utc_str
    # for limiting changes during testing
    # fetch_query += " limit:80"
    # get current user name
    username = _find_user_name()
    try:
        logging.info("Connecting to %s@%s:%d", username, hostname, port)
        gerrit = GerritClient(host=hostname,
                              username=username,
                              port=port)
        logging.info("Connected to Gerrit version [%s]",
                     gerrit.gerrit_version())
    except GerritError as err:
        logging.error("Gerrit error: %s", err)
        return []

    logging.info("Fetching changes with %s", fetch_query)
    changes = []
    try:
        changes = gerrit.query(fetch_query)
    except ValueError as value_error:
        # should not happen as query above should have no errors
        logging.error("Query %s failed: %s", fetch_query, value_error)

    logging.info("Number of changes fetched: %d", len(changes))
    return changes


def _main():
    # set log level to INFO
    logging.basicConfig(level=logging.INFO)
    # fetch past 2 days' changes, have to be specified in UTC days
    day_before_datetime_utc = datetime.utcnow() - timedelta(days=1)
    timestamp = calendar.timegm(day_before_datetime_utc.timetuple())
    local_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    logging.info("Fetching changes since %s", local_time)
    fetch_changes("gerrit.myhost.com", day_before_datetime_utc)


if __name__ == "__main__":
    sys.exit(_main())