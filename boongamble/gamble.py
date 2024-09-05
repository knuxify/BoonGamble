# SPDX-License-Identifier: MIT
"""
Win multiplier calculation code.

Preamble
============

The calculation must meet two goals:

- The more you pay, the higher the reward, and the higher the risk;
- The bot must be able to pay for itself, i.e. the win rate shouldn't be
  *too* high, but at the same time it must be high enough for people to
  play.

I am not an expert in programming gambling probabilities, so this is
a naive approach that may or may not be tweaked in the future.

How it works
============

There are two parameters to the win calculation:

- The input value - the amount paid by the player.
- The max value - the maximum amount that can be paid.

...see gamble() function for more info.
"""

from .config import config
from . import logger

import secrets
from typing import Optional, Union

# Debug option that allows for viewing the cubic bezier plot.
GAMBLE_DEBUG: bool = config.get("gamble_debug", False)
if GAMBLE_DEBUG:
    import matplotlib.pyplot as plt

    # adapted from https://github.com/isinsuatay/Cubic-Bezier-With-Python/blob/main/CubicBezier.py
    def cubic_bezier_plot(p0, p1, p2, p3, filename: str = "plot.png"):
        plt.clf()

        x_values = []
        y_values = []
        win_values = 0
        t = 0
        while t <= 1:
            x, y = cubic_bezier(t, p0, p1, p2, p3)
            x_values.append(x)
            y_values.append(y)
            if y > 1:
                win_values += 1
            t += 0.01

        plt.plot(x_values, y_values, label="Probability curve", color="blue")

        plt.scatter([p0[0]], [p0[1]], label="p0", color="red")
        plt.scatter([p1[0]], [p1[1]], label="p1", color="orange")
        plt.scatter([p2[0]], [p2[1]], label="p2", color="yellow")
        plt.scatter([p3[0]], [p3[1]], label="p3", color="green")

        plt.title("Probability curve")
        plt.legend()
        plt.grid(True)
        plt.xlabel("X")
        plt.ylabel("Y")
        # plt.axis('equal')

        if filename:
            plt.savefig(filename)
        else:
            plt.show()


MAX_MULTIPLIER = config.get("max_multiplier", 4)


# max allowed value is based on total bank value;
# at most, a lucky win matching the full max multiplier must not drain
# the account below 1/2 of its contents
def to_max_value(boons):
    """Take boon count and calculate maximum allowed value."""
    return boons / MAX_MULTIPLIER / 2


# math stolen from:
# https://blog.maximeheckel.com/posts/cubic-bezier-from-math-to-motion/
def cubic_bezier(
    t,
    p0: [Union[int, float], Union[int, float]],
    p1: [Union[int, float], Union[int, float]],
    p2: [Union[int, float], Union[int, float]],
    p3: [Union[int, float], Union[int, float]],
):
    out = [0, 0]
    for i in range(2):
        out[i] = (
            (1 - t) ** 3 * p0[i]
            + t * p1[i] * (3 * (1 - t) ** 2)
            + p2[i] * (3 * (1 - t) * t**2)
            + p3[i] * t**3
        )
    return out


def gamble(
    input_value: float, max_value: float, debug_filename: Optional[str] = None
) -> float:
    """
    Calculate probability table based on provided values.
    """
    show_stats = False

    if input_value > max_value:
        raise ValueError("Input value is larger than maximum value")

    # Get the random value we use for calculations.
    rand = secrets.randbelow(100)

    # The closer the input value to the maximum value, the more difficult we make it.
    risk = min((input_value / max_value), 1)

    if input_value < (max_value / (len(str(int(max_value))) * 1.25)):
        # For low input values, the minimum risk value is 0.65: (~25% win rate)
        if risk < 0.65:
            risk = 0.65
    else:
        # The minimum risk value is 0.75: (~16% win rate)
        if risk < 0.75:
            risk = 0.75

    # We use a cubic bezier curve to calculate the initial multiplier.
    # Cubic bezier is perhaps not the most obvious choice for this kind of
    # calculation, most notably being used for CSS animations, but 1. it's
    # all that I have experience in, and 2. it's just simple enough to be
    # easy to implement and it's customizable enough for our usecase.
    p0 = (0, 0)
    p1 = (min((risk + 0.05), 1), (MAX_MULTIPLIER / 2) - (risk / 4))
    p2 = (min((risk + 0.15), 1), (-0.25 - risk))
    p3 = (1, MAX_MULTIPLIER)

    mult = None
    for t in range(0, 101):
        curve = cubic_bezier(t / 100, p0, p1, p2, p3)
        if int(curve[0] * 100) >= rand:
            mult = curve[1]
            break
    if mult is None:
        logger.warning("mult was not found for X (this probably doesn't happen), TODO")
        show_stats = True
        mult = cubic_bezier(round(rand / 100, 2), p0, p1, p2, p3)[1]

    assert mult is not None

    # Once that's done, we can get the output boon count :D
    out_value = input_value * mult

    # Round the output value down to 2 decimal points
    out_value = round(out_value, 2)

    if GAMBLE_DEBUG or show_stats:
        # https://stackoverflow.com/a/29257837
        import math

        truncate = lambda f, n: math.floor(f * 10**n) / 10**n
        win_rate = 0
        values = {}

        for i in range(0, 101):
            for t in range(0, 101):
                curve = cubic_bezier(t / 100, p0, p1, p2, p3)
                if int(curve[0] * 100) >= i:
                    if curve[1] >= 1:
                        win_rate += 1
                    break

        lose_rate = 100 - win_rate

        logger.info(f"""--- GAMBLE STATS ---
        -> Input b{input_value}, max b{max_value}, output b{out_value}
        -> Risk {risk}
        -> Random value {rand} -- multiplier {mult}
        -> Curve points:
           -> p0 {p0}
           -> p1 {p1}
           -> p2 {p2}
           -> p3 {p3}
        -> Potential win rate ~{win_rate:.2f}%, lose rate ~{lose_rate:.2f}%""")
    if GAMBLE_DEBUG:
        cubic_bezier_plot(p0, p1, p2, p3, filename=debug_filename)

    return out_value
