from boongamble.gamble import gamble
import boongamble.gamble
boongamble.gamble.GAMBLE_DEBUG = True

for i in range(4):
    max = 10 ** i
    print(f"!!! TESTS FOR {max} BOONS: !!!")
    for value in [max / 1000, max / 100, max / 10, max / 8, max / 4, max / 2, max / 1.5, max / 1.25, max / 1.1, max / 1.01, max]:
        gamble(value, max, debug_filename = f"tests/testgamble-{max}-{value:.2f}.png")
