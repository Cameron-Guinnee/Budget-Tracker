"""Tests for styling.py — color maps and formatting helpers."""

import pytest
from styling import (
    category_color_map,
    payment_method_color_map,
    payment_method_label_prefix,
    fmt_currency,
)


# ── fmt_currency ───────────────────────────────────────────────────────────

class TestFmtCurrency:
    def test_basic_integer(self):
        assert fmt_currency(1000) == "$1,000"

    def test_thousands_separator(self):
        assert fmt_currency(1234567) == "$1,234,567"

    def test_zero(self):
        assert fmt_currency(0) == "$0"

    def test_decimals(self):
        assert fmt_currency(1234.5, decimals=2) == "$1,234.50"

    def test_negative_value(self):
        assert fmt_currency(-500) == "$-500"

    def test_small_decimal(self):
        assert fmt_currency(0.99, decimals=2) == "$0.99"

    def test_default_no_decimals(self):
        result = fmt_currency(1234.99)
        assert "." not in result


# ── category_color_map ─────────────────────────────────────────────────────

class TestCategoryColorMap:
    def test_all_values_are_hex_colors(self):
        import re
        hex_pattern = re.compile(r"^#[0-9a-fA-F]{6}$")
        for cat, color in category_color_map.items():
            assert hex_pattern.match(color), f"'{cat}' has invalid color '{color}'"

    def test_income_category_present(self):
        assert "Income" in category_color_map

    def test_other_category_not_white(self):
        # Pure white (#ffffff) is invisible on light backgrounds
        assert category_color_map.get("Other", "").lower() != "#ffffff"

    def test_no_duplicate_categories(self):
        keys = list(category_color_map.keys())
        assert len(keys) == len(set(keys))


# ── payment_method_color_map ───────────────────────────────────────────────

class TestPaymentMethodColorMap:
    def test_standard_methods_present(self):
        for method in ("Credit", "Debit", "Cash", "Check"):
            assert method in payment_method_color_map

    def test_label_prefix_matches_color_map_keys(self):
        assert set(payment_method_label_prefix.keys()) == set(payment_method_color_map.keys())

    def test_all_prefixes_are_nonempty_strings(self):
        for method, prefix in payment_method_label_prefix.items():
            assert isinstance(prefix, str) and len(prefix) > 0
