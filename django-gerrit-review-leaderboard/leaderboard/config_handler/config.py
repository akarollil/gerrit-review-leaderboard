"""Handles creation and loading of configuration file for fetching changes
from gerrit"""
import configparser
import logging
import os


# configuration file for fetching gerrit changes
CONFIG_FILE = "fetcher.cfg"
CUR_DIR = os.getcwd()
CONFIG_FILE_PATH = "%s/%s" % (CUR_DIR, CONFIG_FILE)
CONFIG_FILE_SECTION = "fetch"


class GerritFetchConfig:
    """Provides methods for reading configuration file and returning info
    needed for fetching changes from gerrit
    """

    def __init__(self):
        self.config = configparser.ConfigParser()
        try:
            with open(CONFIG_FILE_PATH) as config_file:
                self.config.read_file(config_file)
        except IOError:
            logging.warning(
                "Configuration file %s not found, creating a default one",
                CONFIG_FILE_PATH)
            self._create_default_config_file()
        with open(CONFIG_FILE_PATH) as config_file:
            self.config.read_file(config_file)
        self._hostname = self.config[CONFIG_FILE_SECTION]['hostname']
        self._username = self.config[CONFIG_FILE_SECTION]['username']
        self._port = int(self.config[CONFIG_FILE_SECTION]['port'])
        self._max_days = int(self.config[CONFIG_FILE_SECTION]['maxdays'])
        logging.info(
            "Loaded hostname: %s username: %s port: %d max_days: %d from %s",
            self._hostname,
            self._username,
            self._port,
            self._max_days,
            CONFIG_FILE_PATH)

    def _create_default_config_file(self):
        self.config[CONFIG_FILE_SECTION] = {'hostname': 'gerrit.myhost.com',
                                            'username': 'gerritleaderboard',
                                            'port': '29418',
                                            'maxdays': '180'}
        # write config file
        with open(CONFIG_FILE_PATH, 'w') as config_file:
            self.config.write(config_file)

    def hostname(self):
        """Returns gerrit serverhostname read from config file
        """
        return self._hostname

    def username(self):
        """Returns gerrit server username read from config file
        """
        return self._username

    def port(self):
        """Returns gerrit server port read from config file
        """
        return self._port

    def max_days(self):
        """Returns maximum number of days worth of changes to fetch, read
        from config file
        """
        return self._max_days
