# -*- coding: utf-8 -*-
from __future__ import unicode_literals

from django.db import models


class Change(models.Model):
    """A gerrit change for a project which can have multiple Comments
    and Reviewers
    """
    # Time in UTC change was last updated
    timestamp = models.DateTimeField()
    # Owner/author of change, this is the person who made the change
    owner_full_name = models.CharField(max_length=70)
    # Gerrit change's subject, this is the commit summary message
    subject = models.CharField(max_length=200)
    # Gerrit project name
    project_name = models.CharField(max_length=50)
    # Gerrit change ID hash
    change_id = models.CharField(max_length=50, primary_key=True)

    def __str__(self):
        return u"<Change %s %s %s %s>" % (
            self.change_id, self.owner_full_name, self.subject, self.timestamp)


class Comment(models.Model):
    """Comment posted by a reviewer for a Change. This can be an approval
    (e.g. +1) for a patchset or a comment about a patchset or on a file in a
    patchset
    """
    # Time in UTC when comment was posted
    timestamp = models.DateTimeField()
    # Comment message
    message = models.CharField(max_length=2000)
    # Each Comment is associated with a single Change
    change = models.ForeignKey(Change, on_delete=models.CASCADE)

    def __str__(self):
        return u"<Comment %s %s>" % (self.message[:50], self.timestamp)


class Reviewer(models.Model):
    full_name = models.CharField(max_length=70)
    # A reviewer may review many changes
    changes = models.ManyToManyField(Change)
    # A reviewer may have many comments
    comments = models.ManyToManyField(Comment)

    def __str__(self):
        return u"<Reviewer %s>" % (self.full_name)
