""" View to display a simple page with tables containing information about
gerrit reviewers
"""
from django.http import HttpResponse
from django.template import RequestContext, loader

from .models import Reviewer
from .sync import fetcher


def index(request):
    # fetch outstanding changes, up to a configured maximum specified in
    # sync/fetcher.conf
    fetcher.pull_and_store_changes()
    reviewers = Reviewer.objects.all()
    reviewers_list = []
    for reviewer in reviewers:
        reviewer_name = reviewer.full_name
        review_count = reviewer.changes.count
        comment_count = reviewer.comments.count
        reviewers_list.append({"name": reviewer_name,
                               "review_count": review_count,
                               "comment_count": comment_count})

    template = loader.get_template('leaderboard/index.html')
    context = RequestContext(request, {'reviewers': reviewers_list})

    return HttpResponse(template.render(context))
