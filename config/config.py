import os
import configparser


class Config:
    _instance = None

    @classmethod
    def instance(cls):
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def __init__(self):
        if self._instance is not None:
            raise Exception("Config is a singleton")
        self._instance = self
        if not hasattr(self, "config"):
            self.config = configparser.ConfigParser()
            # current_dir = os.path.dirname(os.path.abspath(__file__))
            base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

            config_file = None
            if os.path.isfile("config/config.ini"):
                config_file = "config/config.ini"
            elif os.path.isfile("config/config-example.ini"):
                config_file = "config/config-example.ini"
            else:
                raise FileNotFoundError("Config file not found")

            cfg_path = os.path.join(base_dir, config_file)
            self.config.read(cfg_path)

    def getboolean(self, section, option):
        return self.config.getboolean(section, option)

    def validate_config(self):
        if self.api_id in ["", "YOUR_API_ID"]:
            raise ValueError("Please set your API ID in config.ini")

        if self.api_hash in ["", "YOUR_API_HASH"]:
            raise ValueError("Please set your API hash in config.ini")

        if self.email_address in ["", "YOUR_EMAIL_ADDRESS"]:
            raise ValueError("Please set your email address in config.ini")

        if self.email_password in ["", "YOUR_EMAIL_PASSWORD"]:
            raise ValueError("Please set your email password in config.ini")

        if self.email_host in ["", "YOUR_EMAIL_HOST"]:
            raise ValueError("Please set your email host in config.ini")

        if self.email_port in ["", "YOUR_EMAIL_PORT"]:
            raise ValueError("Please set your email port in config.ini")

    def get_base_dir(self):
        return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    @property
    def alert_new(self):
        return self.config["alerts"]["alert_new"]

    @property
    def alert_reminder(self):
        return self.config["alerts"]["alert_reminder"]

    @property
    def reminder_limit(self):
        return self.config["alerts"]["reminder_limit"]

    @property
    def include_channel(self):
        return self.config["alerts"]["include_channel"]

    @property
    def api_id(self):
        return self.config["telegram"]["api_id"]

    @property
    def api_hash(self):
        return self.config["telegram"]["api_hash"]

    @property
    def channel(self):
        return self.config["telegram"]["channel"]

    @property
    def db_path(self):
        return self.config["database"]["db_path"]

    @property
    def email_address(self):
        return self.config["email"]["address"]

    @property
    def email_password(self):
        return self.config["email"]["password"]

    @property
    def email_host(self):
        return self.config["email"]["host"]

    @property
    def email_port(self):
        return int(self.config["email"]["port"])

    @property
    def email_strings_path(self):
        return self.config["email"]["email_strings_path"]

    @property
    def email_template_path(self):
        return self.config["email"]["email_template_path"]

    @property
    def timezone(self):
        return self.config["time"]["timezone"]

    @property
    def time_format(self):
        return self.config["time"]["time_format"]

    @property
    def time_window_minutes(self):
        return int(self.config["time"]["time_window_minutes"])

    @property
    def debug(self):
        return int(self.config["debug"]["debug"])
