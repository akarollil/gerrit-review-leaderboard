"""For converting and persisting pygerrit Changes as leaderboard Reviewers,
Changes, and Comments
"""
from datetime import datetime
from ..models import Change, Reviewer, Comment


def convert_to_utc_datetime(timestamp_utc):
    """Converts given timestamp to a datetime object

    Timestamp in pygerrit change is in seconds since epoch in UTC which
    is stored in the database as a datetime object

    :arg str timestamp_utc: timestamp in UTC as string
    :Returns: UTC datetime object corresponding to timestamp_utc
    """
    return datetime.utcfromtimestamp(float(timestamp_utc))


def get_last_synced_change_timestamp():
    """Return the last synced change's UTC datetime

    :Returns: Latest change UTC datetime among changes in database,
              None if there are no changes
    """
    try:
        change = Change.objects.latest('timestamp')
        return change.timestamp
    except Change.DoesNotExist:
        return None


def _get_or_create_reviewer(reviewer_name):
    try:
        reviewer = Reviewer.objects.get(full_name=reviewer_name)
    except Reviewer.DoesNotExist:
        # add new reviewer
        reviewer = Reviewer(full_name=reviewer_name)
        reviewer.save()
    return reviewer


def _change_exists(change_id):
    """Check if change exists in database
    """
    # change ID is unique
    change_count = Change.objects.filter(change_id=change_id).count()
    return change_count != 0


def update(gerrit_changes):
    """Update database based on given gerrit changes

    Update Change, Comment, and Reviewer tables with information in
    list of gerrit changes. Adds comments and changes to reviewers,
    creating new reviewers if they don't exist. Ignores duplicate
    changes if any.
    :arg List of pygerrit.models.Change: list of changes fetched using pygerrit from gerrit
    """
    for gerrit_change in gerrit_changes:
        change = Change()
        change.timestamp = convert_to_utc_datetime(
            gerrit_change.last_update_timestamp)
        change.owner_full_name = gerrit_change.owner.name
        change.subject = gerrit_change.subject
        change.project_name = gerrit_change.project
        change.change_id = gerrit_change.change_id
        if _change_exists(change.change_id):
            # This could happen either because of a fetch overlap or because of
            # a comment added to a merged change. Ignore both.
            continue
        # commit to database
        change.save()
        # reviewers for change
        reviewers = []
        # process comments, add comment and change to reviewer
        for gerrit_comment in gerrit_change.comments:
            comment = Comment()
            comment.timestamp = convert_to_utc_datetime(
                gerrit_comment.timestamp)
            comment.message = gerrit_comment.message
            # link comment to change
            comment.change = change
            # commit to database
            comment.save()
            reviewer_name = gerrit_comment.reviewer.name
            reviewer = _get_or_create_reviewer(reviewer_name)
            # link comment to reviewer
            reviewer.comments.add(comment)
            # link change to reviewer (change already linked will just get
            # updated
            reviewer.changes.add(change)
            # save reviewer
            reviewer.save()
            # add to list of reviewers for this change
            reviewers.append(reviewer)
