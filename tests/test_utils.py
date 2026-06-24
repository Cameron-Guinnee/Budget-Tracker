"""Tests for utils.py — config parsing helpers."""

import pytest
from utils import (
    get_budget_config,
    get_account_apy_config,
    get_transaction_tab_shared_default,
    get_transaction_tab_presets,
)


# ── get_budget_config ──────────────────────────────────────────────────────

class TestGetBudgetConfig:
    def test_returns_budgets(self, minimal_secrets_toml):
        path = minimal_secrets_toml("""
[expense_tracker.budgets]
Grocery = 500
Dining = 200
Entertainment = 100
""")
        result = get_budget_config(path)
        assert result == {"Grocery": 500.0, "Dining": 200.0, "Entertainment": 100.0}

    def test_missing_file_returns_empty(self, tmp_path):
        result = get_budget_config(str(tmp_path / "nonexistent.toml"))
        assert result == {}

    def test_no_budget_section_returns_empty(self, minimal_secrets_toml):
        path = minimal_secrets_toml("[expense_tracker]\n")
        result = get_budget_config(path)
        assert result == {}

    def test_empty_budget_section_returns_empty(self, minimal_secrets_toml):
        path = minimal_secrets_toml("[expense_tracker.budgets]\n")
        result = get_budget_config(path)
        assert result == {}

    def test_values_cast_to_float(self, minimal_secrets_toml):
        path = minimal_secrets_toml("""
[expense_tracker.budgets]
Grocery = 500
""")
        result = get_budget_config(path)
        assert isinstance(result["Grocery"], float)


# ── get_account_apy_config ─────────────────────────────────────────────────

class TestGetAccountApyConfig:
    def test_returns_apy_map(self, minimal_secrets_toml):
        path = minimal_secrets_toml("""
[[expense_tracker.accounts]]
name = "High Yield Savings"
apy = 4.5

[[expense_tracker.accounts]]
name = "Emergency Fund"
apy = 5.0
""")
        result = get_account_apy_config(path)
        assert result == {"High Yield Savings": 4.5, "Emergency Fund": 5.0}

    def test_missing_file_returns_empty(self, tmp_path):
        result = get_account_apy_config(str(tmp_path / "nonexistent.toml"))
        assert result == {}

    def test_no_accounts_section_returns_empty(self, minimal_secrets_toml):
        path = minimal_secrets_toml("[expense_tracker]\n")
        result = get_account_apy_config(path)
        assert result == {}

    def test_account_without_apy_skipped(self, minimal_secrets_toml):
        path = minimal_secrets_toml("""
[[expense_tracker.accounts]]
name = "Checking"
""")
        result = get_account_apy_config(path)
        assert result == {}

    def test_values_cast_to_float(self, minimal_secrets_toml):
        path = minimal_secrets_toml("""
[[expense_tracker.accounts]]
name = "Savings"
apy = 4
""")
        result = get_account_apy_config(path)
        assert isinstance(result["Savings"], float)


# ── get_transaction_tab_shared_default ────────────────────────────────────

class TestGetTransactionTabSharedDefault:
    def test_returns_true_when_configured(self, minimal_secrets_toml):
        path = minimal_secrets_toml("""
[expense_tracker.transaction_tab.defaults]
shared = true
""")
        assert get_transaction_tab_shared_default(path) is True

    def test_returns_false_when_configured(self, minimal_secrets_toml):
        path = minimal_secrets_toml("""
[expense_tracker.transaction_tab.defaults]
shared = false
""")
        assert get_transaction_tab_shared_default(path) is False

    def test_missing_file_returns_fallback(self, tmp_path):
        result = get_transaction_tab_shared_default(str(tmp_path / "nonexistent.toml"))
        assert result is False

    def test_missing_file_respects_custom_fallback(self, tmp_path):
        result = get_transaction_tab_shared_default(
            str(tmp_path / "nonexistent.toml"), fallback_val=True
        )
        assert result is True

    def test_missing_key_returns_fallback(self, minimal_secrets_toml):
        path = minimal_secrets_toml("[expense_tracker]\n")
        assert get_transaction_tab_shared_default(path) is False


# ── get_transaction_tab_presets ────────────────────────────────────────────

class TestGetTransactionTabPresets:
    def test_returns_preset_dict(self, minimal_secrets_toml):
        path = minimal_secrets_toml("""
[[expense_tracker.transaction_tab.presets]]
memo = "Rent"
category = "Housing"
owner = "Alice"
payment_method = "Check"
price = 1500
""")
        result = get_transaction_tab_presets(path)
        assert result is not None
        assert "Rent (Alice)" in result
        assert result["Rent (Alice)"]["memo"] == "Rent"
        assert result["Rent (Alice)"]["price"] == 1500

    def test_multiple_presets(self, minimal_secrets_toml):
        path = minimal_secrets_toml("""
[[expense_tracker.transaction_tab.presets]]
memo = "Gym"
category = "Health & Fitness"

[[expense_tracker.transaction_tab.presets]]
memo = "Netflix"
category = "Entertainment"
""")
        result = get_transaction_tab_presets(path)
        assert result is not None
        assert len(result) == 2

    def test_preset_key_uses_category_when_no_memo(self, minimal_secrets_toml):
        path = minimal_secrets_toml("""
[[expense_tracker.transaction_tab.presets]]
category = "Housing"
""")
        result = get_transaction_tab_presets(path)
        assert result is not None
        assert "Housing" in result

    def test_missing_file_returns_none(self, tmp_path):
        result = get_transaction_tab_presets(str(tmp_path / "nonexistent.toml"))
        assert result is None

    def test_empty_presets_returns_none(self, minimal_secrets_toml):
        path = minimal_secrets_toml("[expense_tracker.transaction_tab]\n")
        result = get_transaction_tab_presets(path)
        assert result is None
