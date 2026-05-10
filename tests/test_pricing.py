"""Unit tests for the pricing helpers."""

import os
import random
import sys
import unittest

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

import pricing


class GetBasePriceTests(unittest.TestCase):
    def test_non_consumable_uses_rarity_data(self):
        self.assertEqual(pricing.get_base_price("Обычный", "нет"), 100)
        self.assertEqual(pricing.get_base_price("Необычный", "нет"), 500)
        self.assertEqual(pricing.get_base_price("Редкий", "нет"), 5000)

    def test_consumable_uses_consumable_table(self):
        self.assertEqual(pricing.get_base_price("Обычный", "да"), 50)
        self.assertEqual(pricing.get_base_price("Необычный", "да"), 250)
        self.assertEqual(pricing.get_base_price("Редкий", "да"), 2500)

    def test_consumable_only_triggers_on_exact_yes(self):
        # Anything other than "да" must fall back to the rarity base price.
        for value in ("Да", "ДА", "yes", "true", "", "нет"):
            self.assertEqual(
                pricing.get_base_price("Редкий", value),
                5000,
                msg=f"value={value!r} should not be treated as consumable",
            )


class BuyMultiplierTests(unittest.TestCase):
    def test_buy_multiplier_in_documented_ranges(self):
        random.seed(0)
        for _ in range(2000):
            for rarity in ("Обычный", "Необычный", "Редкий"):
                price_roll, mult = pricing.roll_buy_price_multiplier(rarity)
                # Bound the multiplier across all branches: the lowest
                # achievable value is 0.5 - 0.2 = 0.3 (the >90 branch),
                # the highest is 1.5 + 0.5 = 2.0 (the <=20 branch).
                self.assertGreaterEqual(mult, 0.3 - 1e-9)
                self.assertLessEqual(mult, 2.0 + 1e-9)
                # Adjusted roll must lie in [-9, 110] (1..100 plus -10/+10).
                self.assertGreaterEqual(price_roll, -9)
                self.assertLessEqual(price_roll, 110)


class SellMultiplierTests(unittest.TestCase):
    def test_sell_multiplier_in_documented_ranges(self):
        random.seed(0)
        for _ in range(2000):
            for rarity in ("Обычный", "Необычный", "Редкий"):
                price_roll, mult = pricing.roll_sell_price_multiplier(rarity)
                # Lowest achievable: 0.5 - 0.2 = 0.3 (<=20 branch).
                # Highest achievable: 1.25 + 0.35 = 1.6 (>92 branch).
                self.assertGreaterEqual(mult, 0.3 - 1e-9)
                self.assertLessEqual(mult, 1.6 + 1e-9)


class CalculateFinalPriceTests(unittest.TestCase):
    def test_returns_consistent_tuple(self):
        random.seed(123)
        price_roll, mult, base, final = pricing.calculate_final_price(
            "Необычный", "нет", "buy"
        )
        self.assertEqual(base, 500)
        self.assertEqual(final, int(base * mult))

    def test_consumable_overrides_base_price(self):
        random.seed(7)
        _, _, base, _ = pricing.calculate_final_price("Редкий", "да", "sell")
        self.assertEqual(base, 2500)

    def test_unknown_mode_raises(self):
        with self.assertRaises(ValueError):
            pricing.calculate_final_price("Обычный", "нет", "barter")


class DistributionSmokeTests(unittest.TestCase):
    """Verify each branch of each multiplier table is reachable."""

    def test_buy_branches_reachable(self):
        random.seed(1)
        seen = set()
        for _ in range(5000):
            roll, _ = pricing.roll_buy_price_multiplier("Необычный")
            if roll <= 20:
                seen.add("a")
            elif roll <= 40:
                seen.add("b")
            elif roll <= 80:
                seen.add("c")
            elif roll <= 90:
                seen.add("d")
            else:
                seen.add("e")
        self.assertEqual(seen, {"a", "b", "c", "d", "e"})

    def test_sell_branches_reachable(self):
        random.seed(2)
        seen = set()
        for _ in range(5000):
            roll, _ = pricing.roll_sell_price_multiplier("Необычный")
            if roll <= 20:
                seen.add("a")
            elif roll <= 42:
                seen.add("b")
            elif roll <= 82:
                seen.add("c")
            elif roll <= 92:
                seen.add("d")
            else:
                seen.add("e")
        self.assertEqual(seen, {"a", "b", "c", "d", "e"})


if __name__ == "__main__":
    unittest.main()
