FROM ubuntu:18.04

# Install apache, django, tools to build django app
ENV DEBIAN_FRONTEND noninteractive
RUN apt-get update
RUN apt-get install -y apache2 libapache2-mod-wsgi-py3 python3-django \
    python3-paramiko python3-setuptools python3-pip git
RUN apt-get clean

# Setup apache site for app
WORKDIR /var/www/gerrit-review-leaderboard

COPY django-site/mysite mysite
COPY django-gerrit-review-leaderboard/leaderboard/static/leaderboard static/leaderboard
COPY django-site/manage.py .
COPY django-site/write_config_and_run .

COPY apache2-site.conf /etc/apache2/sites-available/gerrit-leaderboard.conf
RUN a2ensite gerrit-leaderboard.conf
RUN a2dissite 000-default
RUN apache2ctl -S

# Install leaderboard app
WORKDIR /tmp/django-gerrit-review-leaderboard
COPY django-gerrit-review-leaderboard .
RUN python3 setup.py sdist
RUN pip3 install --process-dependency-links dist/django-gerrit-review-leaderboard-0.1.tar.gz

WORKDIR /var/www/gerrit-review-leaderboard
RUN python3 manage.py migrate
RUN chown www-data:www-data . db.sqlite3

# Upgrade paramiko to fix error:
#     "ValueError: CTR mode needs counter parameter, not IV"
RUN pip3 install --upgrade paramiko

EXPOSE 80

ENTRYPOINT ["/var/www/gerrit-review-leaderboard/write_config_and_run"]
CMD []
