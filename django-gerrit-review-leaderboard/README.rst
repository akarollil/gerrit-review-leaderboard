=========================
Gerrit Review Leaderboard
=========================

Gerrit Review Leaderboard is a Django app that displays a leaderboard
for gerrit reviewers based on review and comment count.

Detailed documentation is in the "docs" directory.

Quick start
-----------

1. Build package using:

    python3 setup.py sdist

1. Install using:
     
    pip3 install --process-dependency-links --user dist/django-gerrit-review-leaderboard-0.1.tar.gz

1. Add "leaderboard" to your INSTALLED_APPS setting like
this:

    INSTALLED_APPS = [
        ...
        'leaderboard',
    ]

2. Include the leaderboard URLconf in your project urls.py like this::

    path('leaderboard/', include('leaderboard.urls')),

3. Run `python manage.py migrate` to create the leaderboard models.

4. Update configuration file at <path> with info to connect to a gerrit
server (TODO: this should be in the admin page).

5. Copy over SSH private key and known_hosts file to where the app can
get to it (e.g. /var/www/.ssh - TODO: this should also be configured via
the admin page.

6. Visit http://127.0.0.1:8000/leaderboard/ to see the leaderboard.

