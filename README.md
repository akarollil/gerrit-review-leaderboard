# Gerrit Review Leaderboard

Simple web application that shows leaderboards for gerrit reviews. Leaderboards shown are for:

* Count of reviews
* Count of comments

across reviews for periods of day, week, month, 3 months, and 6 months.

## Installation

### Prerequisites

Host with:

* a webserver
* Python
** pygerrit (https://pypi.python.org/pypi/pygerrit/0.2.1)
* SSH public key access to gerrit service

### Setup

* Download gerrit-review-board.zip
* Untar to webserver resources folder
* Setup xxxx

## Design

###  Requirements

* List of reviewers ranked by review count, and comment count, filter-able by project, time frame

### UI

Simple page that shows ranking table and allows sorting based on review count or comment count and has a choice of time frame (day, week, month)

### Backend

Python service that connects to gerrit, syncs changes and associated comments across projects, and provides model for UI to fetch information for leaderboard. Initial sync is for commits up to 6 months old. Further syncs are driven by refreshes and by an hourly fetch driven by a timer. Each subsequent fetch driven by client request or timer will be for changes updated or comments posted after the most recent change/comment timestamp. Currently the granularity of a fetch is a UTC day (gerrit query specifying a timestamp that includes seconds or the timezone is broken).