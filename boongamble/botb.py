# SPDX-License-Identifier: MIT
"""
Code for interfacing with BotB.
"""

from bs4 import BeautifulSoup
from functools import cached_property
from dataclasses import dataclass
import datetime
from enum import Enum
import re
import requests
from requests.adapters import HTTPAdapter, Retry
import pickle
import pytz
import os.path
from typing import Dict, List, Optional, Union

#: Parser to use for BeautifulSoup; see:
#: https://www.crummy.com/software/BeautifulSoup/bs4/doc/#installing-a-parser
SOUP_PARSER = "lxml"

# https://stackoverflow.com/questions/15431044/can-i-set-max-retries-for-requests-request
REQ_RETRIES = Retry(
    total=5, connect=5, read=5, backoff_factor=1, status_forcelist=[500, 502, 503, 504]
)


class AlertType(Enum):
    ALL = -1
    OTHER = 0
    GOT_BOONS = 1


@dataclass
class Alert:
    """BotB alert base class."""

    #: Type of the alert, auto-assigned based on the message
    type: AlertType  # = AlertType.OTHER
    message: str
    link: str
    #: Arbitrary data for the alert. Differs based on alert type.
    data: Optional[dict] = None

    @classmethod
    def from_message(cls, message: str, link: str):
        msg_type = AlertType.OTHER
        data = None

        # Boons alert
        res = re.search(
            r"(?P<username>(.*)) gave you b(?P<boons>([0-9.]*))( and they said \"(?P<message>(.*))\")?",
            message,
        )
        if res:
            data = {
                "username": res.group("username"),
                "boons": float(res.group("boons")),
                "message": res.group("message") or "",
            }
            msg_type = AlertType.GOT_BOONS

        return Alert(type=msg_type, message=message, link=link, data=data)


@dataclass
class BotBr:
    """Class for BotBrs. Matches API data."""

    # string, since this is used to match against the aura PNG name so we need the 0 padding
    aura: str
    aura_color: str
    avatar_url: str
    badge_levels: list
    boons: float
    botbr_class: str  # has to be renamed from class since class is a Python keyword
    class_icon: str
    create_date_str: str
    id: int
    laston_date_str: str
    level: int
    name: str
    palette_id: int
    points: int
    points_array: Dict[str, int]
    profile_url: str

    @cached_property
    def create_date(self) -> datetime.datetime:
        return datetime.strptime(self.create_date_str, "%Y-%m-%d").replace(
            tzinfo=pytz.timezone("America/Los_Angeles")
        )

    @cached_property
    def laston_date(self) -> datetime.datetime:
        return datetime.strptime(self.laston_date_str, "%Y-%m-%d").replace(
            tzinfo=pytz.timezone("America/Los_Angeles")
        )

    @classmethod
    def from_payload(cls, payload: dict):
        payload_parsed = payload.copy()

        payload_parsed["botbr_class"] = payload_parsed.pop("class")

        for intval in ("id", "level", "points"):
            payload_parsed[intval] = int(payload_parsed[intval])

        for floatval in ("boons",):
            payload_parsed[floatval] = float(payload_parsed[floatval])

        # SITE BUG: empty points_array becomes a list instead of a dict
        if isinstance(payload_parsed["points_array"], list):
            payload_parsed["points_array"] = {}
        else:
            for key, val in payload_parsed["points_array"].copy().items():
                payload_parsed["points_array"][key] = int(val)

        for dateval in ("create_date", "laston_date"):
            payload_parsed[dateval + "_str"] = payload_parsed.pop(dateval)

        return cls(**payload_parsed)


class UnauthenticatedException(Exception):
    """
    Exception raised when trying to call an authenticated method without
    authentication.
    """


def require_auth(func):
    """Decorator for BotB class functions which require authentication."""

    def wrapper(self, *args, **kwargs):
        if self.botbr_id is None:
            raise UnauthenticatedException(
                "This method requires authentication; create BotB object with .login() or .use_cookie_file()"
            )

        return func(self, *args, **kwargs)

    return wrapper


class BotB:
    """BotB API class."""

    botbr_id: int
    user_id: int

    def __init__(self):
        self._s = requests.Session()
        self._s.mount("http://", HTTPAdapter(max_retries=REQ_RETRIES))
        self._s.mount("https://", HTTPAdapter(max_retries=REQ_RETRIES))
        self.botbr_id = None
        self.user_id = None

    def _post_login_init(self, cookie_file: str = "_cookies.pkl"):
        """Common init steps shared by both of the login functions."""
        cookies = self._s.cookies.get_dict()

        self.botbr_id = int(cookies["botbr_id"])
        # Unused? TODO
        # self.user_id = int(cookies["user_id"])

        _user = self.get_self_botbr()
        if not _user:
            raise UnauthenticatedException(
                f"Failed to log in: can't find user for BotBr ID ({self.botbr_id})"
            )
        self.username = _user.name

        with open(cookie_file, "wb") as f:
            pickle.dump(self._s.cookies, f)

        return self

    @classmethod
    def login(
        cls,
        email: str,
        password: str,
        cookie_file: str = "_cookies.pkl",
        force_fresh_login: bool = False,
    ):
        """Log into BotB and get the session cookie."""
        if not os.path.exists(cookie_file) or force_fresh_login:
            b = cls()

            login_post = b._s.post(
                "https://battleofthebits.com/barracks/Login/",
                data={"email": email, "password": password, "submitok": "LOGIN"},
            )

            if login_post.status_code != 200:
                raise UnauthenticatedException(
                    f"Failed to log in; check email and password"
                )

            return b._post_login_init(cookie_file=cookie_file)

        return cls.use_cookie_file(cookie_file)

    @classmethod
    def use_cookie_file(cls, cookie_file: str = "_cookies.pkl"):
        """Log into BotB using a saved session cookie."""
        b = cls()
        b._s = requests.Session()

        with open(cookie_file, "rb") as f:
            b._s.cookies.update(pickle.load(f))

        return b._post_login_init(cookie_file=cookie_file)

    #
    # Public API methods
    #
    def get_botbr_id_by_username(self, username: str) -> Union[int, None]:
        """Get the ID of a BotBr by their username."""
        ret = self._s.get(f"https://battleofthebits.com/api/v1/botbr/search/{username}")
        if ret.status_code != 200:
            return None

        users = ret.json()
        if not users:
            return None

        for user in users:
            if user["name"] == username:
                return int(user["id"])

        return None

    def get_botbr_by_id(self, botbr_id: int) -> BotBr:
        """Get BotBr info by BotBr ID."""
        ret = self._s.get(f"https://battleofthebits.com/api/v1/botbr/load/{botbr_id}")
        if ret.status_code != 200:
            return None

        botbr_data = ret.json()

        return BotBr.from_payload(botbr_data)

    def get_botbr_by_username(self, username: str) -> BotBr:
        """Get BotBr info by username."""
        botbr_id = self.get_botbr_id_by_username(username)
        if not botbr_id:
            return None

        return self.get_botbr_by_id(botbr_id)

    #
    # Private API/hack methods
    #

    @require_auth
    def get_self_botbr(self):
        """Get your own profile info."""
        return self.get_botbr_by_id(self.botbr_id)

    @require_auth
    def get_alerts(
        self, filter_types: Union[AlertType, List[AlertType]] = AlertType.ALL
    ) -> List[Alert]:
        """Get a list of alerts for the user."""
        ret = self._s.get(
            f"https://battleofthebits.com/ajax/req/botbr/AjaxAlerts/{self.botbr_id}"
        )
        out = []
        soup = BeautifulSoup(ret.text, SOUP_PARSER)

        if isinstance(filter_types, AlertType):
            filter_types = [filter_types]

        # > .grid_8 > div.inner.clearfix > a.boxLink
        for alert_html in soup.select("a.boxLink"):
            message = alert_html.text.split("\n\t")[-1]
            alert = Alert.from_message(
                link=alert_html["href"],
                message=message,
            )

            if filter_types == [AlertType.ALL] or alert.type in filter_types:
                out.append(alert)

        return out

    @require_auth
    def give_boons(
        self,
        username: str,
        amount: float,
        message: str = "",
        overflow_message: bool = False,
    ):
        """Send boons to the given user."""
        if not overflow_message and len(message) > 56:
            raise ValueError("Message must be 56 characters or shorter")

        ret = self._s.post(
            f"https://battleofthebits.com/barracks/Profile/{username}/GaveBoons",
            data={
                "amount": amount,
                "message": message,
                "giveboons": "Give b00ns",
            },
        )

        # TODO error handling
        # if ret.status_code != 200:
        # 	print("error?", ret.status_code)
