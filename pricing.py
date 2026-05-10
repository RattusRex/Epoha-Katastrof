"""Price calculation helpers shared by shop search and sell flows."""

import random


RARITY_DATA = {
    "Обычный": {"dc": 5, "days_dice": 4, "base_price": 100},
    "Необычный": {"dc": 10, "days_dice": 8, "base_price": 500},
    "Редкий": {"dc": 15, "days_dice": 12, "base_price": 5000},
}

CONSUMABLE_BASE_PRICE = {
    "Обычный": 50,
    "Необычный": 250,
    "Редкий": 2500,
}

# Rarity adjustment applied to the d100 price roll before bracket lookup.
RARITY_PRICE_ROLL_ADJUSTMENT = {
    "Обычный": 10,
    "Необычный": 0,
    "Редкий": -10,
}


def get_base_price(rarity: str, consumable: str) -> int:
    """Return the base price for an item, accounting for consumables."""
    if consumable == "да" and rarity in CONSUMABLE_BASE_PRICE:
        return CONSUMABLE_BASE_PRICE[rarity]
    return RARITY_DATA[rarity]["base_price"]


def _adjusted_price_roll(rarity: str) -> int:
    """Roll d100 and apply the rarity-specific adjustment used by all shops."""
    return random.randint(1, 100) + RARITY_PRICE_ROLL_ADJUSTMENT.get(rarity, 0)


def roll_buy_price_multiplier(rarity: str):
    """Roll the buy-side price multiplier. Returns (price_roll, multiplier)."""
    price_roll = _adjusted_price_roll(rarity)
    if price_roll <= 20:
        multiplier = 1.5 + (random.randint(0, 500) / 1000)
    elif price_roll <= 40:
        multiplier = 1.0 + (random.randint(0, 490) / 1000)
    elif price_roll <= 80:
        multiplier = 0.75 + (random.randint(0, 240) / 1000)
    elif price_roll <= 90:
        multiplier = 0.5 + (random.randint(0, 240) / 1000)
    else:
        multiplier = 0.5 - (random.randint(0, 200) / 1000)
    return price_roll, multiplier


def roll_sell_price_multiplier(rarity: str):
    """Roll the sell-side price multiplier. Returns (price_roll, multiplier)."""
    price_roll = _adjusted_price_roll(rarity)
    if price_roll <= 20:
        multiplier = 0.5 - (random.randint(0, 200) / 1000)
    elif price_roll <= 42:
        multiplier = 0.5 + (random.randint(0, 250) / 1000)
    elif price_roll <= 82:
        multiplier = 0.75 + (random.randint(0, 150) / 1000)
    elif price_roll <= 92:
        multiplier = 0.9 + (random.randint(0, 350) / 1000)
    else:
        multiplier = 1.25 + (random.randint(0, 350) / 1000)
    return price_roll, multiplier


def calculate_final_price(rarity: str, consumable: str, mode: str):
    """Roll a final item price.

    mode: "buy" for searches, "sell" for sales.
    Returns (price_roll, multiplier, base_price, final_price).
    """
    if mode == "buy":
        price_roll, multiplier = roll_buy_price_multiplier(rarity)
    elif mode == "sell":
        price_roll, multiplier = roll_sell_price_multiplier(rarity)
    else:
        raise ValueError(f"Unknown price mode: {mode!r}")

    base_price = get_base_price(rarity, consumable)
    final_price = int(base_price * multiplier)
    return price_roll, multiplier, base_price, final_price
