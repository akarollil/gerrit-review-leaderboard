"""
Tests, including a 'system' test that when pointed to a gerrit server, fetches
changes, stores them, and then dumps database into a JSON file
"""
from datetime import datetime, timedelta
from django.test import TestCase
import time

from pygerrit.models import Account
from pygerrit.models import Change as GerritChange
from pygerrit.models import Comment as GerritComment

from . import views
from . models import Change
from . models import Comment
from . models import Reviewer
from . sync import database_helper
from . sync import fetcher


def dump_db(file_name="dbdump.txt"):
    from django.core.serializers import serialize
    reviewers = Reviewer.objects.all()
    changes = Change.objects.all()
    comments = Comment.objects.all()
    reviewers_json = serialize('json', list(reviewers))
    changes_json = serialize('json', list(changes))
    comments_json = serialize('json', list(comments))
    f = open(file_name, 'w')
    f.write("REVIEWERS:\n")
    f.write(reviewers_json)
    f.write("\n\nCHANGES:\n")
    f.write(changes_json)
    f.write("\n\nCOMMENTS:\n")
    f.write(comments_json)
    f.close()


class TestDatabaseHelper(TestCase):
    OWNER = "John Doe"
    SUBJECT = "My fix for everything"
    PROJECT = "leaderboard"
    REVIEWER = "Mary Jane"
    COMMENT_MSG = "This really fixes everything!"

    def test_get_last_synced_change_timestamp(self):
        # test with no changes present
        last_synced_ts = database_helper.get_last_synced_change_timestamp()
        self.assertIsNone(last_synced_ts)
        # test with changes present
        now = time.time()
        latest_ts = None
        for i in range(1, 3):
            timestamp = database_helper.convert_to_utc_datetime(str(now + i))
            latest_ts = timestamp
            change = Change(
                timestamp=timestamp, change_id="test_change_id_%d" % i)
            change.save()

        last_synced_ts = database_helper.get_last_synced_change_timestamp()
        self.assertEqual(last_synced_ts, latest_ts)

    def test_convert_to_utc_datetime(self):
        """Sanity check for converting UTC timestamp string to UTC datetime
        """
        datetime_utc = database_helper.convert_to_utc_datetime("0")
        self.assertEqual(datetime_utc.year, 1970)
        self.assertEqual(datetime_utc.month, 1)
        self.assertEqual(datetime_utc.day, 1)
        self.assertEqual(datetime_utc.hour, 0)
        self.assertEqual(datetime_utc.minute, 0)
        self.assertEqual(datetime_utc.second, 0)

    def test_update_no_change(self):
        database_helper.update([])
        change_count = Change.objects.count()
        self.assertEqual(change_count, 0, "No changes should have been saved")

    def _make_gerrit_comment(self, reviewer_name):
        gerrit_comment = GerritComment([])
        gerrit_comment.timestamp = str(time.time())
        gerrit_comment.reviewer = Account([])
        gerrit_comment.reviewer.name = reviewer_name
        gerrit_comment.message = self.COMMENT_MSG
        return gerrit_comment

    def _make_gerrit_change(self, timestamp, change_id, comments):
        gerrit_change = GerritChange([])
        gerrit_change.last_update_timestamp = timestamp or str(time.time())
        gerrit_change.owner = Account([])
        gerrit_change.owner.name = self.OWNER
        gerrit_change.subject = self.SUBJECT
        gerrit_change.project = self.PROJECT
        gerrit_change.change_id = change_id or "change_id_%s" % str(time.time())
        gerrit_change.comments = comments
        return gerrit_change

    def _make_gerrit_change_with_comments(self, change_id=None, timestamp=None,
                                          reviewers=[]):
        """Make a gerrit change object for use in testing

        Make a gerrit change object with given change ID, and timestamp, and
        comments by each reviewer in given list of reviewers.
        """
        gerrit_comments = []
        for reviewer in reviewers:
            gerrit_comment = self._make_gerrit_comment(reviewer)
            gerrit_comments.append(gerrit_comment)

        return self._make_gerrit_change(timestamp, change_id,
                                        gerrit_comments)

    def _assert_reviewer_change_comments_counts(self, expected_reviewer_count,
                                                expected_change_count,
                                                expected_comment_count):
        found_reviewer_count = Reviewer.objects.count()
        self.assertEqual(found_reviewer_count, expected_reviewer_count,
                         "There should be %d reviewer(s), found %d" %
                         (expected_reviewer_count, found_reviewer_count))
        found_change_count = Change.objects.count()
        self.assertEqual(found_change_count, expected_change_count,
                         "There should be %d change(s), found %d" %
                         (expected_change_count, found_change_count))
        found_comment_count = Comment.objects.count()
        self.assertEqual(found_comment_count, expected_comment_count,
                         "There should be %d comment(s), found %d" %
                         (expected_comment_count, found_comment_count))

    def _assert_reviewer_change_comments(self, expected_reviewer_data,
                                         total_expected_changes):
        """Test database for reviewer and associated comment and change count

        expected_reviewer_data is a list of expectations, each of which is a
        list of the form:
        ["reviewer_name_string", change_count_int, comment_count_int]
        total_expected_changes needs to be explicitly specified as a change
        can be associated with multiple reviewers
        """
        total_expected_reviewers = 0
        total_expected_comments = 0
        for reviewer_data in expected_reviewer_data:
            reviewer_name = reviewer_data[0]
            expected_change_count = reviewer_data[1]
            expected_comment_count = reviewer_data[2]

            total_expected_reviewers += 1
            total_expected_comments += expected_comment_count

            # check reviewer
            try:
                reviewer = Reviewer.objects.get(full_name=reviewer_name)
            except Reviewer.DoesNotExist:
                self.fail("Reviewer %s not in database" % reviewer_name)
            # check change count
            found_changes_count = reviewer.changes.count()
            self.assertEqual(found_changes_count, expected_change_count,
                             "There should be %d change(s) for %s, found %d" %
                             (expected_change_count, reviewer_name,
                              found_changes_count))
            # check comment count
            found_comment_count = reviewer.comments.count()
            self.assertEqual(
                found_comment_count,
                expected_comment_count,
                "There should be %d comments(s) for %s, found %d." %
                (expected_comment_count,
                 reviewer_name,
                 found_comment_count))

        # check database state
        self._assert_reviewer_change_comments_counts(total_expected_reviewers,
                                                     total_expected_changes,
                                                     total_expected_comments)

    def test_update_initial_change_comment_data(self):
        timestamp_utc = str(time.time())
        timestamp_datetime = database_helper.convert_to_utc_datetime(
            timestamp_utc)
        # convert to string with second precision for test comparison
        timestamp_datetime_str = timestamp_datetime.strftime(
            '%Y-%m-%d %H:%M:%S')
        change_id = "change-id-%r" % timestamp_utc
        gerrit_change = self._make_gerrit_change_with_comments(change_id,
                                                               timestamp_utc,
                                                               [self.REVIEWER])
        database_helper.update([gerrit_change])
        # should have created one reviewer, one change, and one comment
        self._assert_reviewer_change_comments([[self.REVIEWER, 1, 1]], 1)
        # should have created a new reviewer
        reviewers = Reviewer.objects.all()
        reviewer = reviewers[0]
        # check change associated with reviewer
        changes = reviewer.changes.all()
        change = changes[0]
        self.assertEqual(change.timestamp, timestamp_datetime,
                         "Found %r != Expected %r" % (change.timestamp,
                                                      timestamp_datetime))
        self.assertEqual(change.owner_full_name, self.OWNER)
        self.assertEqual(change.subject, self.SUBJECT)
        self.assertEqual(change.project_name, self.PROJECT)
        self.assertEqual(change.change_id, change_id)
        # check comment associated with reviewer
        comments = reviewer.comments.all()
        comment = comments[0]
        comment_timestamp_str = comment.timestamp.strftime(
            '%Y-%m-%d %H:%M:%S')
        self.assertEqual(comment_timestamp_str, timestamp_datetime_str)
        self.assertEqual(comment.message, self.COMMENT_MSG)
        # check associated change
        self.assertEqual(comment.change, change)

    def test_update_initial_1change_no_comments(self):
        """Merges shouldn't happen without comments (+1, +2 are comments)
        but test so that it is handled"""
        gerrit_change = self._make_gerrit_change(str(time.time()),
                                                 "change_id_12345", [])
        database_helper.update([gerrit_change])
        self._assert_reviewer_change_comments([], 1)

    def test_update_initial_1change_2comments_1reviewer(self):
        reviewer_name = "Jungle Boy"
        gerrit_change = self._make_gerrit_change_with_comments(
            reviewers=[
                reviewer_name,
                reviewer_name])
        database_helper.update([gerrit_change])
        self._assert_reviewer_change_comments([[reviewer_name, 1, 2]], 1)

    def test_update_initial_1change_2comments_2reviewers(self):
        reviewers = ["Jungle Boy", "City Girl"]
        gerrit_change = self._make_gerrit_change_with_comments(
            reviewers=reviewers)
        database_helper.update([gerrit_change])
        self._assert_reviewer_change_comments(
            [[reviewers[0], 1, 1], [reviewers[1], 1, 1]], 1)

    def test_update_initial_2changes_6comments_3reviewers(self):
        reviewers_change1 = ["Jungle Boy", "City Girl", "City Girl", "Foo Bar"]
        reviewer_change2 = ["Foo Bar"]
        gerrit_change1 = self._make_gerrit_change_with_comments(
            change_id="change_id_1",
            reviewers=reviewers_change1)
        gerrit_change2 = self._make_gerrit_change_with_comments(
            change_id="change_id_2",
            reviewers=reviewer_change2)
        database_helper.update([gerrit_change1, gerrit_change2])
        # assert expected reviewers, their associated changes, comments count
        # and also total number of expected changes
        self._assert_reviewer_change_comments(
            [["Jungle Boy", 1, 1], ["City Girl", 1, 2], ["Foo Bar", 2, 2]], 2)

    def test_update_with_existing_changes_including_duplicate(self):
        # create 2 changes with 3 reviewers with 6 comments from between them
        self.test_update_initial_2changes_6comments_3reviewers()
        # add one more change with 2 comments from 1 existing reviewer and a new
        # reviewer
        reviewers = ["Jungle Boy", "Mad Dog"]
        gerrit_change = self._make_gerrit_change_with_comments(
            change_id="change_id3",
            reviewers=reviewers)
        database_helper.update([gerrit_change])
        self._assert_reviewer_change_comments(
            [["Jungle Boy", 2, 2], ["City Girl", 1, 2], ["Foo Bar", 2, 2],
             ["Mad Dog", 1, 1]], 3)
        # update with same change
        database_helper.update([gerrit_change])
        # assert database the same
        self._assert_reviewer_change_comments(
            [["Jungle Boy", 2, 2], ["City Girl", 1, 2], ["Foo Bar", 2, 2],
             ["Mad Dog", 1, 1]], 3)


class TestFetcher(TestCase):
    HOST_NAME = "gerrit.myserver.com"
    PORT = 12345
    MAX_DAYS = 30
    FAKE_CHANGE = "Fake change"
    found_hostname = None
    found_datetime_str = None
    found_port = None
    saved_fetch_method = None

    def _mock_fetch(self, hostname, datetime_utc, port):
        """Mocks gerrit_handler.fetch()
        """
        self.found_hostname = hostname
        # convert to string with second precision for test comparison
        self.found_datetime_str = datetime_utc.strftime('%Y-%m-%d %H:%M:%S')
        self.found_port = port
        return self.FAKE_CHANGE

    def setUp(self):
        # mock out gerrit fetch
        self.saved_fetch_method = fetcher.fetch.fetch_changes
        fetcher.fetch.fetch_changes = self._mock_fetch

    def tearDown(self):
        # unmock gerrit fetch
        fetcher.fetch.fetch_changes = self.saved_fetch_method

    def _assert_fetch_params(self, expected_datetime_utc):
        # convert to string with milliseconds stripped for test comparison
        expected_datetime_utc_str = expected_datetime_utc.strftime(
            '%Y-%m-%d %H:%M:%S')
        fake_change = fetcher._do_pull(self.HOST_NAME, self.PORT, self.MAX_DAYS)
        self.assertEqual(self.found_hostname, self.HOST_NAME,
                         "Expected %s, found %s" % (self.HOST_NAME,
                                                    self.found_hostname))
        self.assertEqual(self.found_datetime_str, expected_datetime_utc_str,
                         "Expected %s, found %s" % (expected_datetime_utc_str,
                                                    self.found_datetime_str))
        self.assertEqual(self.found_port, self.PORT,
                         "Expected %s, found %s" % (self.PORT,
                                                    self.found_port))
        self.assertEqual(self.FAKE_CHANGE, fake_change,
                         "Expected %s, found %s" % (self.FAKE_CHANGE,
                                                    fake_change))

    def test_do_pull_no_existing_changes(self):
        # test only MAX_DAYS days of changes are fetched if no changes in
        # database
        current_datetime_utc = (
            datetime.utcnow() -
            timedelta(
                days=self.MAX_DAYS))
        self._assert_fetch_params(current_datetime_utc)

    def test_do_pull_with_existing_changes(self):
        # a change 10 days ago
        ten_days_ago_datetime_utc = datetime.utcnow() - timedelta(days=10)
        change = Change(
            timestamp=ten_days_ago_datetime_utc,
            change_id="test_change_id_1")
        change.save()
        # a change 20 days ago
        twenty_days_ago_datetime_utc = datetime.utcnow() - timedelta(days=20)
        change = Change(
            timestamp=twenty_days_ago_datetime_utc,
            change_id="test_change_id_2")
        change.save()

        self._assert_fetch_params(ten_days_ago_datetime_utc)

    def test_do_pull_with_really_old_existing_change(self):
        max_days_ago_datetime_utc = datetime.utcnow(
        ) - timedelta(days=self.MAX_DAYS)
        # a change more than MAX_DAYS days ago
        more_than_max_days_ago_utc = max_days_ago_datetime_utc - \
            timedelta(days=1)
        change = Change(
            timestamp=more_than_max_days_ago_utc,
            change_id="test_change_id_1")
        change.save()

        self._assert_fetch_params(max_days_ago_datetime_utc)


class TestView(TestCase):

    def _assert_time_period_list(self, expected_list, found_list):
        index = 0
        for expected_time_period in expected_list:
            found_time_period = found_list[index]
            self.assertEqual(
                expected_time_period,
                found_time_period,
                "Expected %s at %d, found %s" %
                (expected_time_period,
                 index,
                 found_time_period))
            index += 1

    def test_get_time_periods_no_current_selection(self):
        time_periods = views._get_time_periods()
        expected_list = ["1 Week", "1 Month", "3 Months", "6 Months"]
        self._assert_time_period_list(expected_list, time_periods)

    def test_get_time_periods_with_selection(self):
        time_periods = views._get_time_periods("3 Months")
        expected_list = ["3 Months", "1 Week", "1 Month", "6 Months"]
        self._assert_time_period_list(expected_list, time_periods)

    def test_get_time_periods_invalid_selection(self):
        time_periods = views._get_time_periods("Invalid time period")
        expected_list = ["1 Week", "1 Month", "3 Months", "6 Months"]
        self._assert_time_period_list(expected_list, time_periods)

    def _assert_start_datetime(self, time_period, end_datetime,
                               expected_start_datetime):
        found_start_datetime = views._get_start_datetime_for_time_period(
            time_period, end_datetime)
        self.assertEqual(expected_start_datetime, found_start_datetime,
                         "Expected %s found %s" % (expected_start_datetime,
                                                   found_start_datetime))

    def test_get_start_datetime_for_time_period(self):
        end_datetime = datetime(2016, 2, 23)
        # one week ago
        self._assert_start_datetime("1 Week", end_datetime,
                                    datetime(2016, 2, 16))
        # one month ago
        self._assert_start_datetime("1 Month", end_datetime,
                                    datetime(2016, 1, 24))
        # 3 months ago
        self._assert_start_datetime("3 Months", end_datetime,
                                    datetime(2015, 11, 25))
        # 6 months ago
        self._assert_start_datetime("6 Months", end_datetime,
                                    datetime(2015, 8, 27))

        # invalid time period should default to 1 Month default
        self._assert_start_datetime("Invalid time period", end_datetime,
                                    datetime(2016, 1, 24))

    def _create_change(self, change_id, project_name,
                       timestamp=datetime.utcnow()):
        change = Change()
        change.change_id = "test-change-id-" + str(change_id)
        change.owner_full_name = "John Smith"
        change.project_name = project_name
        change.subject = "A test commit"
        change.timestamp = timestamp
        change.save()
        return change

    def _create_changes_with_projects(self, project_list):
        index = 0
        for project_name in project_list:
            self._create_change(index, project_name)
            index += 1

    def _test_get_projects(self, project_names, current_project_name,
                           expected_project_list):
        self._create_changes_with_projects(project_names)
        found_project_list = views._get_projects(current_project_name)
        # verify project name count
        expected_list_len = len(project_names) + 1  # +1 for 'all'
        found_list_len = len(found_project_list)
        self.assertEqual(found_list_len, expected_list_len,
                         "Expected project list of length %d, found %d" %
                         (expected_list_len, found_list_len))
        # verify project names found in the right order
        index = 0
        for found_project_name in found_project_list:
            expected_project_name = expected_project_list[index]
            self.assertEqual(
                found_project_name,
                expected_project_list[index],
                "Expected %s at %d, found %s" %
                (expected_project_name,
                 index,
                 found_project_name))
            index += 1

    def test_get_projects_current_project_all(self):
        project_names = ["foo", "bar", "biz", "acme"]
        expected_project_list = [views.PROJECT_ALL, "acme", "bar", "biz", "foo"]
        self._test_get_projects(project_names, views.PROJECT_ALL,
                                expected_project_list)

    def test_get_projects_current_project_invalid(self):
        project_names = ["foo", "bar", "biz", "acme"]
        expected_project_list = [views.PROJECT_ALL, "acme", "bar", "biz", "foo"]
        self._test_get_projects(project_names, "invalid_current_project",
                                expected_project_list)

    def test_get_projects_current_project_bar(self):
        project_names = ["foo", "bar", "biz", "acme"]
        expected_project_list = ["bar", views.PROJECT_ALL, "acme", "biz", "foo"]
        self._test_get_projects(project_names, "bar",
                                expected_project_list)

    def test_get_projects_current_project_foo(self):
        project_names = ["foo", "bar", "acme", "biz"]
        expected_project_list = ["foo", views.PROJECT_ALL, "acme", "bar", "biz"]
        self._test_get_projects(project_names, "foo",
                                expected_project_list)

    def _create_reviewer(self, reviewer_name, changes, comments):
        reviewer = Reviewer()
        reviewer.full_name = reviewer_name
        reviewer.save()
        reviewer.comments.add(*comments)
        reviewer.changes.add(*changes)
        reviewer.save()

    def _create_comment(self, mock_change):
        comment = Comment()
        comment.timestamp = datetime.utcnow()
        comment.message = "This is a test comment"
        # comment change link doesn't affect the view in any way, but is needed
        # by the model
        comment.change = mock_change
        comment.save()
        return comment

    def _create_comments(self, mock_change, count):
        comments = []
        for _ in range(0, count):
            comments.append(self._create_comment(mock_change))
        return comments

    def _create_changes(self, project_name, age_in_days, count):
        changes = []
        age_in_datetime_utc = datetime.utcnow() - timedelta(days=age_in_days)
        for index in range(0, count):
            change_id = "%s-%s-%d" % (project_name, age_in_days, index)
            change = self._create_change(change_id, project_name,
                                         age_in_datetime_utc)
            changes.append(change)
        return changes

    def _assert_reviewers(self, project_name, time_period, expected_reviewers):
        """Asserts list of reviewer changes and comment counts

        :arg: str project_name: project name for filtering reviewers
        :arg: str time_period: time period specified as one of
            views.SORTED_TIME_PERIODS.keys()
        :arg: list expected_reviewers: a list of expected reviewer info
        """
        time_period_start_datetime = views._get_start_datetime_for_time_period(
            time_period)
        found_reviewers = views._get_reviewers_and_counts(
            project_name,
            time_period_start_datetime)

        self.assertEqual(
            len(expected_reviewers),
            len(found_reviewers),
            "Expected %d reviewers, found %d \n Expected: %r\n Found: %r" %
            (len(expected_reviewers),
             len(found_reviewers),
                expected_reviewers,
                found_reviewers))

        for reviewer_info in found_reviewers:
            self.assertTrue(
                reviewer_info in expected_reviewers,
                "Reviewer info %r not found in expected reviewers %r" %
                (reviewer_info,
                 expected_reviewers))

    def test_get_reviewers_and_counts(self):
        """Test reviewers with changes with varying ages and in multiple
        projects and with comments
        """
        projecta = "project-a"
        projectb = "project-b"
        projectc = "project-c"
        # mock change for comments
        mock_change = self._create_change("mock_change", projecta)
        # 5 changes in project-a, a day old
        five_changes_projecta_day_old = self._create_changes(projecta, 1, 5)
        # 3 changes in project-a, more than two weeks old
        three_changes_projecta_two_weeks_old = self._create_changes(projecta,
                                                                    14,
                                                                    3)
        # 2 changes in project-b, a day old
        two_changes_projectb_day_old = self._create_changes(projectb, 1, 2)
        # 10 changes in project-b, 2 months old
        ten_changes_projectb_two_months_old = self._create_changes(projectb,
                                                                   60,
                                                                   10)
        # 6 changes in project-c, 5 months old
        six_changes_projectc_five_months_old = self._create_changes(projectc,
                                                                    150,
                                                                    6)
        # assign changes to reviewers
        reviewer1 = "Kutty Krishnan"
        reviewer2 = "Naaranathu Bhrandhan"
        reviewer3 = "Thammanam Shaaji"
        reviewer4 = "Sharada Mani"

        self._create_reviewer(reviewer1, five_changes_projecta_day_old +
                              two_changes_projectb_day_old,
                              self._create_comments(mock_change, 1))
        self._create_reviewer(reviewer2, five_changes_projecta_day_old +
                              three_changes_projecta_two_weeks_old,
                              self._create_comments(mock_change, 2))
        self._create_reviewer(reviewer3, six_changes_projectc_five_months_old,
                              self._create_comments(mock_change, 3))
        self._create_reviewer(reviewer4, five_changes_projecta_day_old +
                              ten_changes_projectb_two_months_old +
                              six_changes_projectc_five_months_old,
                              self._create_comments(mock_change, 4))

        dump_db("test_reviewers.txt")

        # one week, all projects
        expected_reviewers = [
            views._create_reviewer_info(reviewer1, 7, 1),
            views._create_reviewer_info(reviewer2, 5, 2),
            views._create_reviewer_info(reviewer4, 5, 4)
        ]
        self._assert_reviewers(views.PROJECT_ALL, "1 Week", expected_reviewers)

        # one week, projecta
        expected_reviewers = [
            views._create_reviewer_info(reviewer1, 5, 1),
            views._create_reviewer_info(reviewer2, 5, 2),
            views._create_reviewer_info(reviewer4, 5, 4)
        ]
        self._assert_reviewers(projecta, "1 Week", expected_reviewers)

        # one week, projectb
        expected_reviewers = [
            # Only Kutty Krishnan with 2 changes in the past week and no
            # comments as single comment is on change in projecta
            views._create_reviewer_info(reviewer1, 2, 0)
        ]
        self._assert_reviewers(projectb, "1 Week", expected_reviewers)

        # one week, projectc, no reviewers with any changes
        expected_reviewers = []
        self._assert_reviewers(projectc, "1 Week", expected_reviewers)

        # one month, projecta
        expected_reviewers = [
            views._create_reviewer_info(reviewer1, 5, 1),
            views._create_reviewer_info(reviewer2, 8, 2),
            views._create_reviewer_info(reviewer4, 5, 4)
        ]
        self._assert_reviewers(projecta, "1 Month", expected_reviewers)

        # one month, projectb
        expected_reviewers = [
            views._create_reviewer_info(reviewer1, 2, 0)
        ]
        self._assert_reviewers(projectb, "1 Month", expected_reviewers)

        # one month, projectc
        expected_reviewers = []
        self._assert_reviewers(projectc, "1 Month", expected_reviewers)

        # three months, projecta
        expected_reviewers = [
            views._create_reviewer_info(reviewer1, 5, 1),
            views._create_reviewer_info(reviewer2, 8, 2),
            views._create_reviewer_info(reviewer4, 5, 4)
        ]
        self._assert_reviewers(projecta, "3 Months", expected_reviewers)

        # three months, projectb
        expected_reviewers = [
            views._create_reviewer_info(reviewer1, 2, 0),
            views._create_reviewer_info(reviewer4, 10, 0)
        ]
        self._assert_reviewers(projectb, "3 Months", expected_reviewers)

        # three months, projectc
        expected_reviewers = []
        self._assert_reviewers(projectc, "3 Months", expected_reviewers)

        # six months, projecta
        expected_reviewers = [
            views._create_reviewer_info(reviewer1, 5, 1),
            views._create_reviewer_info(reviewer2, 8, 2),
            views._create_reviewer_info(reviewer4, 5, 4)
        ]
        self._assert_reviewers(projecta, "6 Months", expected_reviewers)

        # six months, projectb
        expected_reviewers = [
            views._create_reviewer_info(reviewer1, 2, 0),
            views._create_reviewer_info(reviewer4, 10, 0)
        ]
        self._assert_reviewers(projectb, "6 Months", expected_reviewers)

        # six months, projectc
        expected_reviewers = [
            views._create_reviewer_info(reviewer3, 6, 0),
            views._create_reviewer_info(reviewer4, 6, 0)
        ]
        self._assert_reviewers(projectc, "6 Months", expected_reviewers)


class TestSystem(TestCase):

    def test_fetch_and_store(self):
        """Queries gerrit, updates db, deserializes database to JSON
        """
        fetcher.MAX_DAYS = 1
        fetcher.pull_and_store_changes()
        dump_db()
