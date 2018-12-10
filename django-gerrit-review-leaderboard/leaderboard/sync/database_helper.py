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


def _ignore_comment(gerrit_change, gerrit_comment):
    """Check if comment needs to be ignored

    :arg pygerrit.models.Change gerrit_change: Change associated with comment
    :arg pygerrit.models.Comment gerrit_comment: Comment to be checked
    :Returns: True if comment should be ignored, False otherwise
    """
    # reviewer might not have a name, but will have a username
    reviewer_name = (
        gerrit_comment.reviewer.name if gerrit_comment.reviewer.name
        else gerrit_comment.reviewer.username)
    # ignore Jenkins Build or Gerrit Code Review comments
    if "Jenkins" in reviewer_name or "Gerrit" in reviewer_name:
        return True
    # ignore change owner comments (replies)
    if gerrit_change.owner.name == reviewer_name or \
            gerrit_change.owner.username == reviewer_name:
        return True
    # ignore comments that are just +1s or +2s
    if "Code-Review+1" in gerrit_comment.message or \
            "Code-Review+2" in gerrit_comment.message:
        return True
    # ignore comments related to rebases
    if "was rebased"in gerrit_comment.message:
        return True

    return False


def update(gerrit_changes):
    """Update database based on given gerrit changes

    Update Change, Comment, and Reviewer tables with information in
    list of gerrit changes. Adds comments and changes to reviewers,
    creating new reviewers if they don't exist. Ignores duplicate
    changes if any.
    :arg List of pygerrit.models.Change: list of changes fetched using
        pygerrit from gerrit
    """
    for gerrit_change in gerrit_changes:
        if _change_exists(gerrit_change.change_id):
            # This could happen either because of a fetch overlap or because of
            # a comment added to a merged change. Ignore both.
            continue
        change_timestamp = convert_to_utc_datetime(
            gerrit_change.last_update_timestamp)

        # owner might not have a name, but will have a username
        owner = (
            gerrit_change.owner.name if gerrit_change.owner.name
            else gerrit_change.owner.username)
        # create change
        change = Change(
            timestamp=change_timestamp,
            owner_full_name=owner,
            subject=gerrit_change.subject,
            project_name=gerrit_change.project,
            change_id=gerrit_change.change_id
        )
        # commit change to database
        change.save()
        # process comments, add comment and change to reviewer
        for gerrit_comment in gerrit_change.comments:
            # ignore comment if necessary
            if _ignore_comment(gerrit_change, gerrit_comment):
                continue
            # create comment
            comment_timestamp = convert_to_utc_datetime(
                gerrit_comment.timestamp)
            comment = Comment(
                timestamp=comment_timestamp,
                message=gerrit_comment.message,
                change=change)
            comment.save()
            # get reviewer, creating if necessary
            # reviewer might not have a name, but will have a username
            reviewer_name = (
                gerrit_comment.reviewer.name if gerrit_comment.reviewer.name
                else gerrit_comment.reviewer.username)
            reviewer = _get_or_create_reviewer(reviewer_name)
            # link comment to reviewer
            reviewer.comments.add(comment)
            # link change to reviewer (change already linked will just get
            # updated
            reviewer.changes.add(change)
