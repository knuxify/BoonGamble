# SPDX-License-Identifier: MIT
"""
Config file access module
"""

import yaml

config = {}

with open("config.yml", "r") as config_file:
    config = yaml.safe_load(config_file)
