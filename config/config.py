"""
Module that provides a custom dynamic configuration object
and is used to load and validate the configuration values.

See config-example.ini for an example configuration file.
"""

import os
import configparser
from typing import Any, Dict, Optional

"""
Inspired from
https://alexandra-zaharia.github.io/posts/python-configuration-and-dataclasses/
"""


class DynamicConfig:
    """
    A class to represent a custom dynamic configuration object.
    """

    def __init__(self, conf: Dict[str, Any]):
        """
        Initializes the DynamicConfig object and sets the configuration values
        as attributes using setattr.
        """
        self._raw: Dict[str, Any] = conf

        for key, value in self._raw.items():
            setattr(self, key, value)

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Sets the attribute value.

        Args:
            name (str): The name of the attribute.
            value (Any): The value of the attribute.
        """
        super().__setattr__(name, value)

    def __getattr__(self, name: str) -> Any:
        """
        Gets the attribute value.

        Args:
            name (str): The name of the attribute.

        Returns:
            Any: The value of the attribute.
        """
        if name in self._raw:
            return self._raw[name]
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )


class ConfigIni:
    """
    A class to represent a configuration object using a ConfigParser object,
    and to provide methods to access and validate the configuration values.
    """

    def __init__(self, conf: configparser.ConfigParser, config_path: str):
        """
        Initializes the ConfigIni object and sets the configuration values
        as attributes using setattr.

        Args:
            conf (configparser.ConfigParser): The ConfigParser object.
            config_path (str): The path to the configuration file.
        """
        self._raw: configparser.ConfigParser = conf
        self._config_path: str = config_path
        for key, value in self._raw.items():
            setattr(self, key, DynamicConfig(dict(value.items())))

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Sets the attribute value.

        Args:
            name (str): The name of the attribute.
            value (Any): The value of the attribute.
        """
        super().__setattr__(name, value)

    def __getattr__(self, name: str) -> Any:
        """
        Gets the attribute value.

        Args:
            name (str): The name of the attribute.

        Returns:
            Any: The value of the attribute."""
        if name in self._raw:
            return DynamicConfig(dict(self._raw[name].items()))
        raise AttributeError(
            f"'{self.__class__.__name__}' object has no attribute '{name}'"
        )

    def getboolean(self, section: str, option: str) -> bool:
        """
        Gets the boolean value of the specified option in the specified section.

        Args:
            section (str): The name of the section.
            option (str): The name of the option.

        Returns:
            bool: The boolean value of the option."""
        return self._raw.getboolean(section, option)

    def get_config_path(self) -> str:
        """
        Gets the path to the configuration file.

        Returns:
            str: The path to the configuration file.
        """
        return self._config_path

    def get_sections(self) -> list[str]:
        """
        Gets the sections in the configuration file.

        Returns:
            list[str]: The sections in the configuration file."""
        return self._raw.sections()

    def get_options(self, section: str) -> list[str]:
        """
        Gets the options in the specified section.

        Args:
            section (str): The name of the section.

        Returns:
            list[str]: The options in the specified section."""
        return self._raw.options(section)

    def _pretty_print_config(
        self, config: Dict[str, Dict[str, Any]], indent: int = 0
    ) -> str:
        """
        Pretty prints the configuration values.

        Args:
            config (Dict[str, Dict[str, Any]]): The configuration values.
            indent (int): The indentation level.

        Returns:
            str: The pretty printed configuration values.
        """
        result = []
        for section, options in config.items():
            result.append(f"{'  ' * indent}{section}:")
            for key, value in options.items():
                result.append(f"{'  ' * (indent + 1)}{key}: {value}")
        return "\n".join(result)

    def list_config_values(self) -> str:
        """
        Lists the configuration values.

        Returns:
            str: The pretty printed configuration values.
        """
        config = {}
        for section in self._raw.sections():
            config[section] = dict(self._raw[section].items())
        return self._pretty_print_config(config, 4)


def load_config(base_dir: Optional[str] = None) -> ConfigIni:
    """
    Loads the configuration file (either config.ini or config-example.ini).
    config-example.ini is the provided example config and is used as a fallback
    if config.ini is not found.

    Args:
        base_dir (Optional[str]): The base directory.

    Returns:
        ConfigIni: The configuration object.
    """
    if base_dir is None:
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

    if os.path.isfile("config/config.ini"):
        config_path = "config/config.ini"
    elif os.path.isfile("config/config-example.ini"):
        config_path = "config/config-example.ini"
    else:
        raise FileNotFoundError("Config file not found")

    cfg_parser = configparser.ConfigParser()
    cfg_parser.read(config_path)

    return ConfigIni(cfg_parser, config_path)


def validate_config(config: ConfigIni) -> None:
    """
    Validates the configuration values.

    Args:
        config (ConfigIni): The configuration object.
    """
    if (
        config.alerts.alert_new_get_by_time_window is True
        and config.alerts.alert_new_get_by_last_update is True
    ):
        raise ValueError(
            """alert_new_get_by_time_window and alert_new_get_by_last_update
            cannot both be set to 1"""
        )

    if (
        config.alerts.alert_new_get_by_time_window is False
        and config.alerts.alert_new_get_by_last_update is False
    ):
        raise ValueError(
            """alert_new_get_by_time_window and alert_new_get_by_last_update
            cannot both be set to 0"""
        )

    if config.telegram.api_id in ["", "YOUR_API_ID"]:
        raise ValueError("Please set your API ID in config.ini")

    if config.telegram.api_hash in ["", "YOUR_API_HASH"]:
        raise ValueError("Please set your API hash in config.ini")

    if config.email.address in ["", "YOUR_EMAIL_ADDRESS"]:
        raise ValueError("Please set your email address in config.ini")

    if config.email.password in ["", "YOUR_EMAIL_PASSWORD"]:
        raise ValueError("Please set your email password in config.ini")

    if config.email.host in ["", "YOUR_EMAIL_HOST"]:
        raise ValueError("Please set your email host in config.ini")

    if config.email.port in ["", "YOUR_EMAIL_PORT"]:
        raise ValueError("Please set your email port in config.ini")

    if config.debug.log_level not in ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]:
        raise ValueError(
            """Please set a valid log level in config.ini\n
            Must be: DEBUG, INFO, WARNING, ERROR, CRITICAL"""
        )


def get_base_dir() -> str:
    """
    Gets the base directory.

    Returns:
        str: The base directory.
    """
    return os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
