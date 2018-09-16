#!/usr/bin/env python
"""Fetch changes from gerrit server using pygerrit
"""

import calendar
from datetime import datetime, timedelta
import logging
import sys

from pygerrit.client import GerritClient
from pygerrit.error import GerritError

# the maximum number of changes to fetch at a time. 500 seems to be the limit
# for the maximum number of changes that can be fetched at a time via gerrit's
# SSH API
MAX_CHANGES_FETCH_COUNT = 500


def _fetch(gerrit_client, datetime_utc, skip):
    """Fetch changes starting from a certain date

    Use gerrit_client to fetch changes starting from datetime_utc but
    limited to MAX_CHANGES_FETCH_COUNT changes, skipping changes if
    skip is specified, starting at the newest change

    :arg pygerrit.client.GerritClient gerrit_client: Gerrit SSH client
        for use in fetching changes
    :arg datetime.datetime datetime_utc: datetime obj specifying time
        in UTC, changes fetched should have been merged after time
        specified
    :arg int skip: count of changes to skip starting from newest

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
    fetch_query = "status:merged after:%s limit:%d" % (
        time_utc_str, MAX_CHANGES_FETCH_COUNT)

    if skip:
        fetch_query += " -S %d" % skip

    logging.info("Fetching changes with %s", fetch_query)
    changes = []
    try:
        changes = gerrit_client.query(fetch_query)
    except ValueError as value_error:
        # should not happen as query above should have no errors
        logging.error("Query %s failed: %s", fetch_query, value_error)

    logging.info("Number of changes fetched: %d", len(changes))
    return changes


def fetch_changes(hostname, username, datetime_utc, port=29418, skip=None):
    """Fetch merged changes from gerrit after timestamp.

    Connects to gerrit at given hostname with given username via SSH and uses
    gerrit query to fetch all changes merged after given datetime, limited to
    500 changes. If query result has more than 500 changes, skip parameter
    can be used to specify count of already fetched changes (newest) to
    skip. Expects given username's public key on current system to have been
    installed on host with given hostname.

    :arg str hostname: gerrit server hostname
    :arg str username: gerrit username
    :arg datetime.datetime datetime_utc: datetime obj specifying time
         in UTC, changes fetched should have been merged after time
         specified
    :arg int port: port for gerrit service
    :arg int skip: count of changes to skip starting from newest

    :Return: List of Change objects if any, empty list otherwise
    """
    try:
        logging.info("Connecting to %s@%s:%d", username, hostname, port)
        gerrit_client = GerritClient(host=hostname,
                                     username=username,
                                     port=port)
        logging.info("Connected to Gerrit version [%s]",
                     gerrit_client.gerrit_version())
    except GerritError as err:
        logging.error("Gerrit error: %s", err)
        return []

    return _fetch(gerrit_client, datetime_utc, skip)


def _main():
    # set log level to INFO
    logging.basicConfig(level=logging.INFO)
    # fetch past 2 days' changes, have to be specified in UTC days
    day_before_datetime_utc = datetime.utcnow() - timedelta(days=1)
    timestamp = calendar.timegm(day_before_datetime_utc.timetuple())
    local_time = datetime.fromtimestamp(timestamp).strftime('%Y-%m-%d %H:%M:%S')
    logging.info("Fetching changes since %s", local_time)
    fetch_changes("gerrit.myhost.com", "anonymous", day_before_datetime_utc)


if __name__ == "__main__":
    sys.exit(_main())
