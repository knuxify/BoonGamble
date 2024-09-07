# SPDX-License-Identifier: MIT
"""
Main loop for the operation of the bot.
"""

from . import logger
from .config import config
from .botb import Alert, AlertType, BotB
from .gamble import gamble, to_max_value

import logging
import os.path
import secrets
import time
import traceback
import yaml

MIN_VALUE = config.get("min_value", 1.00)
MAX_MULTIPLIER = config.get("max_multiplier", 4)
COOLDOWN = config.get("cooldown", 21600)

# transactions: [{"username": str, "amount": float, "message": str, "timestamp": int}]
state = {"handled_alerts": 0, "cooldowns": {}, "transactions": []}
if os.path.exists("_state.yml"):
    with open("_state.yml", "r") as state_file:
        state = yaml.safe_load(state_file)


def save_state() -> None:
    """Save the state to the file."""
    with open("_state.yml", "w+") as state_file:
        yaml.dump(state, state_file)

def give_boons_logged(
    b: BotB, input_alert: Alert, username: str, amount: float, message: str, **kwargs
):
    """BotB.give_boons() but logs transactions."""
    if "transactions" not in state:
        state["transactions"] = []
    state["transactions"].append(
        {
            "username": username,
            "input_amount": input_alert.data["boons"],
            "input_message": input_alert.data.get("message", ""),
            "amount": amount,
            "message": message,
            "timestamp": time.time(),
        }
    )

    return b.give_boons(username, amount, message=message, **kwargs)


# https://stackoverflow.com/a/1384506
# too lazy to write this myself
def format_seconds_to_hhmmss(seconds):
    hours = seconds // (60 * 60)
    seconds %= 60 * 60
    minutes = seconds // 60
    seconds %= 60
    return "%02i:%02i:%02i" % (hours, minutes, seconds)


def witty_message(in_value: float, out_value: float) -> str:
    """Generate a witty response message based on the status."""
    if out_value == 0:
        return f"You lost it ALL, n00b.. what bad luck! (lost b{in_value:.2f})"

    elif in_value > out_value:
        return (
            secrets.choice(
                [
                    "Not quite so lucky this time, eh, n00b??",
                    "Better luck next tiem, n00b!!",
                    "Not quite boonsave, eh, n00b??",
                    "Aw dang it, n00b!",
                ]
            )
            + f" (lost b{(in_value - out_value):.2f})"
        )

    elif in_value == out_value:
        return "Got back what you put in, n00b? How 'bout another try?"

    # TODO scale messages based on how close to the multiplier they are
    elif in_value < out_value:
        msg = ""
        if in_value == in_value * MAX_MULTIPLIER:
            msg = "JACKPOT!!! You get teh full multiplier!"
        elif in_value < out_value * 1.15:
            msg = "Hey, that's a nice little victory, eh?"
        else:
            msg = secrets.choice(
                [
                    "Lucky you, you win, n00b!!",
                    "Sweet sweet b00ns coming your way!!",
                ]
            )
        return msg + f" (won b{(out_value - in_value):.2f})"

    return "ERROR: Witty Message Machine Broke"


def alert_same_as_alert(a1: Alert, a2: Alert):
    if a1.data["boons"] != a2.data["boons"]:
        return False
    if a1.data["username"] != a2.data["username"]:
        return False
    if a1.data["message"] != a2.data["message"]:
        return False
    return True


def alert_same_as_transaction(alert: Alert, transaction: dict):
    if alert.data["boons"] != transaction["input_amount"]:
        return False
    if alert.data["username"] != transaction["username"]:
        return False
    if "message" in alert.data and "input_message" in transaction and \
            alert.data["message"] != transaction["input_message"]:
        return False

    return True


def transaction_same_as_transaction(t1: dict, t2: dict):
    if t1["input_amount"] != t1["input_amount"]:
        return False
    if t1["username"] != t1["username"]:
        return False
    if "input_message" in t1 and "input_message" in t2 and \
            t1["input_message"] != t2["input_message"]:
        return False

    return True


def main() -> None:
    """Main loop of the bot."""
    logger.info("Starting BoonGamble...")

    b = BotB.login(
        config["email"], config["password"], cookie_file=config["cookie_file"]
    )
    if not b:
        raise Exception("Failed to log in")

    logger.info("Logged in succesfully.")

    while True:
        alerts = b.get_alerts(filter_types=[AlertType.GOT_BOONS])

        # Getting alerts times out a lot, try again later if that's the case
        if not alerts:
            time.sleep(5)
            continue

        if "transactions" not in state:
            state["transactions"] = []

        # There are two major problems with parsing alerts:
        # - There is no way to get an exact timestamp, only a relative one;
        # - Alerts on the alert page are truncated to 100.
        # So, we use transaction logs and check if the entries match up.
        #
        # puke if you're reading this, please add a timestamp data attribute
        # to the alerts, thanks <3 (or a real user access API, though that
        # is a very steep thing to request + probably could lead to abuse.)
        if state["handled_alerts"] < 100:
            new_alerts = alerts[state["handled_alerts"]:]

        else:
            last_transactions = list(reversed(state["transactions"][-100:]))
            new_alerts = []
            for alert in alerts:
                if not alert_same_as_transaction(alert, last_transactions[0]):
                    new_alerts.append(alert)
                else:
                    break

            # This breaks on double alerts with the same message, sender and boon count.
            # In that case, we count how many alerts with this message we had before,
            # vs how much we have now. If the number has changed, we add the changed number.
            # The only case in which this can break is if someone sends more than 100 alerts
            # in the few seconds it takes the bot to refresh or if someone sends more than
            # 98 or so comments. Neither of these are possible with how slow BotB is,
            # and you better not try it (:
            if alert_same_as_transaction(alerts[len(new_alerts)], last_transactions[0]):
                a_doubles = 1
                for alert in alerts[1:]:
                    if not alert_same_as_alert(alert, alerts[0]):
                        break
                    a_doubles += 1
                t_doubles = 1
                for transaction in last_transactions[1:]:
                    if not transaction_same_as_transaction(transaction, last_transactions[0]):
                        break
                    t_doubles += 1
                new_doubles = a_doubles - t_doubles
                if new_doubles > 0:
                    new_alerts += alerts[len(new_alerts):len(new_alerts)+new_doubles]

        if new_alerts:
            logger.info(
                f'Need to parse {len(new_alerts)} alerts...'
            )
            # New boon transfer, time to parse
            for alert in new_alerts[::-1]:
                # Don't handle too many transfers right after each other lest we anger
                # the site gods
                time.sleep(1)

                logger.info("Parsing alert...")

                try:
                    message = alert.data.get("message", "")
                    boons = alert.data["boons"]
                    username = alert.data["username"]
                except (AttributeError, KeyError):
                    try:
                        username = alert.data["username"]
                        boons = alert.data["boons"]
                    except:  # noqa: E722
                        give_boons_logged(
                            b,
                            alert,
                            username,
                            0.01,
                            message="Failed to get boon count, contact admin!!",
                        )

                    logging.error("Failed to get alert data for alert")
                    state["handled_alerts"] += 1

                    continue

                # Handle !boonsave command, which allows for a direct transfer bypassing
                # the gambling process (used to add funds to the bot)
                if message.lower().startswith("!boonsave") or "(donation)" in message.lower():
                    logging.info(f"Got boonsave of b{boons:.2f} from {username}")
                    state["handled_alerts"] += 1
                    continue

                # Make sure we respect cooldown
                if "cooldowns" not in state:
                    state["cooldowns"] = {}

                if username in state["cooldowns"]:
                    cooldown_diff = time.time() - state["cooldowns"][username]
                    if cooldown_diff < COOLDOWN:
                        cooldown_left = COOLDOWN - cooldown_diff
                        cooldown_left_str = format_seconds_to_hhmmss(cooldown_left)

                        give_boons_logged(
                            b,
                            alert,
                            username,
                            boons,
                            message=f"Not so fast, n00b! (Cooldown: wait {cooldown_left_str} & try again)",
                        )
                        state["handled_alerts"] += 1

                        logging.info(f"User {username} hit cooldown")

                        continue

                # Get our total stored boon count
                our_boons = b.get_self_botbr().boons

                # The input value is the amount of boons we've been sent
                max_value = to_max_value(our_boons)

                # Verify that the input value is within bounts
                if boons > max_value:
                    give_boons_logged(
                        b,
                        alert,
                        username,
                        boons,
                        message=f"Whaddarya, tha bank?! (Max. value is b{max_value:.2f})",
                        overflow_message=True,
                    )

                    logging.info(
                        f"User {username} tried to pay too much (b{boons:.2f})"
                    )
                    state["handled_alerts"] += 1

                    continue

                if boons < MIN_VALUE:
                    give_boons_logged(
                        b,
                        alert,
                        username,
                        boons,
                        message=f"That won't do, n00b!! (Min. value is b{MIN_VALUE:.2f})",
                    )

                    logging.info(
                        f"User {username} tried to pay too little (b{boons:.2f})"
                    )
                    state["handled_alerts"] += 1

                    continue

                # Time to GAMBLE!
                try:
                    out_value = gamble(boons, max_value)
                except:  # noqa: E722
                    give_boons_logged(
                        b,
                        alert,
                        username,
                        boons,
                        message="Yikes, sumthin's wrong!! (Internal exception: GAMBL_ERR)",
                    )

                    logging.error(
                        "Failed to calculate gamble value, traceback follows:", alert
                    )
                    traceback.print_exc()
                    state["handled_alerts"] += 1

                    continue

                # Set cooldown right before sending boons
                state["cooldowns"][username] = time.time()

                # Send the win amount back to the player with a witty message
                give_boons_logged(
                    b,
                    alert,
                    username,
                    out_value,
                    message=witty_message(boons, out_value),
                    overflow_message=True,
                )

                logger.info(
                    f"User {username} sent b{boons:.2f} and got b{out_value:.2f} back (bank status estimate: {(our_boons + boons - out_value):.2f})"
                )

                state["handled_alerts"] += 1
            save_state()

        # Once everything's done, sleep for a few seconds to allow the next request(s)
        # to come in
        time.sleep(5)
