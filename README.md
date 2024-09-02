# BoonGamble

A fun BotB bot that allows you to play a game of chance with your b00ns. Check it out in action: [b00ngambler](https://battleofthebits.com/barracks/Profile/b00ngambler/)

(Disclaimer: Gambling is bad, kids! This is intended as a fun game for BotBrs (all n00bs!!) and not as a serious game of chance. Since there is no way to purchase b00ns for real-world money, no real-world money is involved. Please be mindful of your b00ns.)

## How it works

The exact mechanism for probability calculation is stored in [boongamble/gamble.py](https://github.com/knuxify/BoonGamble/blob/main/boongamble/gamble.py). See the code for an explanation.

Alternatively, if you want to have a more visual understanding of the values, you can enable debug mode and experiment with the values yourself. This requires matplotlib to be installed. Put `gamble_debug: true` in your `config.yml` and open the Python interpreter:

```python3
>>> import boongamble.gamble
# boongamble.gamble.gamble(input, max)
>>> boongamble.gamble.gamble(10, 100) # example w/ low risk
>>> boongamble.gamble.gamble(90, 100) # example w/ high risk
```

This will cause statistics to be printed and a window will pop up showing a graphical representation of the probability curve.

## Privacy

In order for the bot to operate smoothly, it stores state information which contains:

- when a user last gambled (used for cooldown)
- a log of transactions, including the amount received, amount sent, the sender/recipient, the message and the timestamp of the transaction (used for debugging bot issues, putting together statistics, etc.)

This information is only visible to the bot operator.

## Python BotB API

There is a (very) partial BotB API library in [boongamble/botb.py](https://github.com/knuxify/BoonGamble/blob/main/boongamble/botb.py). I might consider spinning it off into a separate project and making it more complete if there's interest. It's pretty well documented so if you'd like to use it for your own projects, go ahead (just be mindful of the license). Contributions welcome =)

## Running your own instance

The bot is theoretically self-hostable; in practice, no support is offered to such endeavors.

Nonetheless, the dependencies can be found in the `pyproject.toml` file. You can copy the `config.yml.sample` file to `config.yml` and adjust it to your own liking. The bot can be ran with `python3 -m boongamble` in the base directory (the one that contains the very README you're currently reading).

For development purposes, you can also spin up a shell using Poetry:

```shell
$ poetry install  # get dependencies
$ poetry shell    # open shell with venv
(...venv...) $ python3 -m boongamble
```

You can bypass the gamble and deposit money directly in the bot by setting the message to `!boonsave`.
