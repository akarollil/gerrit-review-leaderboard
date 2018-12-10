"""For fetching current open changes from gerrit and processing per project
count per reviewer"""

from ..config_handler.config import GerritFetchConfig
from ..gerrit_handler import fetch


def get_open_change_reviewers_per_project():
    """Returns count of open changes per reviewer per project

    Fetches all open changes from gerrit, and returns a dictionary containing
    all projects with open changes, and for each project, all reviewers and the
    count of changes they are reviewing. e.g.
        {
            "project-a" : {
                            "Reviewer 1": 2,
                            "Reviewer 2": 3,
                            ...
                        },
            ...
        }

    :Return: A dictionary of all projects with keyed by project name and a
    dictionary of reviewer names as keys and open change counts as values, as
    value.
    """
    config = GerritFetchConfig()
    open_changes = fetch.fetch_open_changes(
        config.hostname(), config.username(), config.port())
    open_change_reviewers_per_project = {}
    for gerrit_change in open_changes:
        project = gerrit_change.project
        reviewers = gerrit_change.reviewers
        if not reviewers:
            continue
        # Skip Jenkins
        reviewers[:] = [
            reviewer
            for reviewer in reviewers
            if reviewer.name and "Jenkins" not in reviewer.name]
        if project in open_change_reviewers_per_project:
            reviewer_open_count = open_change_reviewers_per_project[project]
            for reviewer in reviewers:
                if reviewer.name in reviewer_open_count:
                    reviewer_open_count[reviewer.name] += 1
                else:
                    reviewer_open_count[reviewer.name] = 1
        else:
            reviewer_open_count = {}
            for reviewer in reviewers:
                reviewer_open_count[reviewer.name] = 1
            open_change_reviewers_per_project[project] = reviewer_open_count
    return open_change_reviewers_per_project
