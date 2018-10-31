""" View to display a simple page with tables containing information about
gerrit reviewers
"""
from collections import OrderedDict
from datetime import datetime, timedelta
from django.shortcuts import render
import logging

from .models import Reviewer, Change
from .sync import fetcher


PROJECT_ALL = "all"
TIME_PERIOD_DEFAULT = "1 Month"
SORTED_TIME_PERIODS = OrderedDict()
SORTED_TIME_PERIODS["1 Week"] = 7
SORTED_TIME_PERIODS[TIME_PERIOD_DEFAULT] = 30
SORTED_TIME_PERIODS["3 Months"] = 90
SORTED_TIME_PERIODS["6 Months"] = 180


def _get_projects(current_project_name):
    """Get all project names found in fetched changes

    Queries database for changes and returns a list of all associated
    projects. current_project_name if present will be returned as the
    first element in the list of returned projects.

    :arg str current_project_name: any currently selected project, which is
        validated and then guaranteed to be first in list so that it shows as
        currently selected in drop down
    :Return: list of projects in the order they should be displayed in drop
        down with current_project_name if any and valid, being the first choice
    """
    projects = []

    unique_project_changes = Change.objects.order_by().values(
        'project_name').distinct()
    for change in unique_project_changes:
        projects.append(change['project_name'])

    # sort alphabetically
    projects.sort()

    # insert 'all' option as it should be present always
    projects.insert(0, PROJECT_ALL)

    # if current_project_name is valid, make it the first element in list so
    # that it shows up as selected in project choice drop down
    if current_project_name != PROJECT_ALL and current_project_name in projects:
        projects.remove(current_project_name)
        projects.insert(0, current_project_name)
    elif current_project_name != PROJECT_ALL:
        logging.error("Currently selected project %s not found in any changes."
                      " Removing from list.", current_project_name)
    logging.debug("Returning list of projects: %r", projects)
    return projects


def _get_time_periods(current_time_period=None):
    """Return a list of time period strings to display as choices

    :arg str current_time_period: current time period selected if any which is
        guaranteed to be first in the returned list. If current_time_period
        isn't one of the string keys in SORTED_TIME_PERIODS, it is considered
        as None

    :Return: list of time periods in the order they should be displayed in drop
        down with current_time_period if any being the first choice
    """
    sorted_time_periods = list(SORTED_TIME_PERIODS)
    if current_time_period and current_time_period in sorted_time_periods:
        # make the current time period the first in the list so that it shows up
        # as selected in project choice drop down
        for time_period in sorted_time_periods:
            if time_period == current_time_period:
                sorted_time_periods.remove(time_period)
                sorted_time_periods.insert(0, time_period)
                break

    return sorted_time_periods


def _get_start_datetime_for_time_period(time_period, end_datetime=None):
    """Return a UTC datetime corresponding to start of time_period

    Given a time period, return a datetime object for the start of the time
    period. If end_datetime is not specified, use current date and time as end
    of time period for calculating start of time period.
    :arg str time_period: One of the strings in SORTED_TIME_PERIODS
        designating a period of time
    :arg datetime end_datetime: datetime corresponding to end of time period
    :Return: UTC datetime object representing start of time period
    """
    if time_period not in SORTED_TIME_PERIODS.keys():
        logging.error(
            "Time period %s not in %r. Using default %s",
            time_period, SORTED_TIME_PERIODS.keys(), TIME_PERIOD_DEFAULT)
        time_period = TIME_PERIOD_DEFAULT

    # get time period to go back in days and subtract it from current datetime
    days = SORTED_TIME_PERIODS[time_period]
    if not end_datetime:
        end_datetime = datetime.utcnow()
    start_datetime = end_datetime - timedelta(days=days)
    logging.debug(
        "Start date time for end time %r for a period of %s is %r",
        end_datetime, time_period, start_datetime)
    return start_datetime


def _create_reviewer_info(reviewer_name, review_count, comment_count):
    return {
        "name": reviewer_name,
        "review_count": review_count,
        "comment_count": comment_count
    }


def _get_reviewers(project_name, from_datetime):
    """Get reviewers from database filtered based on given parameters

    Get reviewers from database filtered with given project_name and with
    changes from from_datetime and later

    :arg str project_name: filter list of reviewers to be only those with
        changes in the corresponding project
    :arg datetime from_datetime: filter reviewers to be only those with
        changes after datetime

    :Returns: A list of :class:`.models.Reviewer` objects.
    """
    logging.debug(
        "Getting reviewers for project: %s from datetime: %r",
        project_name, from_datetime)
    if project_name == PROJECT_ALL:
        # reviewers with changes across all projects after from_datetime
        reviewers = Reviewer.objects.filter(
            changes__timestamp__gte=from_datetime).distinct()
    else:
        # reviewers with changes in given project after from_datetime
        reviewers = Reviewer.objects.filter(
            changes__project_name=project_name,
            changes__timestamp__gte=from_datetime).distinct()

    logging.debug("Found reviewers: %r", reviewers)
    return reviewers


def _get_reviewer_change_count(reviewer, project_name, from_datetime):
    """Return count of changes for reviewer

    :arg models.Reviewer reviewer: reviewer to get change count for
    :arg str project_name: filter changes to be only those in the corresponding
        project
    :arg datetime from_datetime: filter changes to be only those with timestamp
        after from_datetime

    :Return: count of changes for given reviewer filtered by project_name and
        that have a timestamp after from_datetime
    """
    if project_name == PROJECT_ALL:
        # changes across all projects after from_datetime
        changes = reviewer.changes.filter(
            timestamp__gte=from_datetime).distinct()
    else:
        # changes in given project after from_datetime
        changes = reviewer.changes.filter(
            project_name=project_name,
            timestamp__gte=from_datetime).distinct()

    return changes.count()


def _get_reviewer_comment_count(reviewer, project_name, from_datetime):
    """Return count of comments for reviewer

    :arg models.Reviewer reviewer: reviewer to get change count for
    :arg str project_name: filter comments to be only those for changes in the
        corresponding project
    :arg datetime from_datetime: filter comments to be only those with
        timestamp after from_datetime

    :Return: count of comments for given reviewer filtered by project_name and
        that have a timestamp after from_datetime
    """
    if project_name == PROJECT_ALL:
        # comments in changes across all projects after from_datetime
        comments = reviewer.comments.filter(
            timestamp__gte=from_datetime).distinct()
    else:
        # comments in changes in given project after from_datetime
        comments = reviewer.comments.filter(
            change__project_name=project_name,
            timestamp__gte=from_datetime).distinct()

    return comments.count()


def _get_reviewers_and_counts(project_name, from_datetime):
    """Return reviewers with their changes and comments counts.

    Gets reviewers with changes newer than from_datetime and and in project
    with name project_name. Returns a list of dictionaries, a dictionary for
    each reviewer in list of reviewers found, that contains the reviewer name,
    reviewer change count, and reviewer comment count.

    :arg str project_name: filter list of reviewers to be only those with
        changes in the corresponding project
    :arg datetime from_datetime: filter reviewers to be only those with
        changes after from_datetime

    :Return: A list of reviewer info dictionaries containing reviewer "name",
        "review_count" and "comment_count" info.
    """
    reviewers_info = []
    for reviewer in _get_reviewers(project_name, from_datetime):
        reviewer_name = reviewer.full_name
        review_count = _get_reviewer_change_count(reviewer, project_name,
                                                  from_datetime)
        comment_count = _get_reviewer_comment_count(reviewer, project_name,
                                                    from_datetime)
        reviewers_info.append(
            _create_reviewer_info(reviewer_name, review_count,
                                  comment_count))

    return reviewers_info


def index(request):
    # fetch outstanding changes, up to a configured maximum specified in
    # ../fetcher.cfg
    fetcher.pull_and_store_changes()

    # default to displaying reviewers with changes in all projects and for the
    # past month
    project_name = PROJECT_ALL
    time_period = TIME_PERIOD_DEFAULT
    if request.method == 'POST':
        logging.debug("request.POST = %r", request.POST)
        project_name = request.POST['project_name']
        time_period = request.POST['time_period']

    time_period_start_datetime_utc = _get_start_datetime_for_time_period(
        time_period)
    # reviewers
    reviewers_info_list = _get_reviewers_and_counts(
        project_name,
        time_period_start_datetime_utc)
    # projects
    project_list = _get_projects(project_name)
    # time choices
    time_period_list = _get_time_periods(time_period)

    context = {
        'reviewers': reviewers_info_list,
        'projects': project_list,
        'time_periods': time_period_list
    }

    return render(request, 'leaderboard/index.html', context)
