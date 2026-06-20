import calendar
from gspread import service_account_from_dict
from gspread.spreadsheet import Spreadsheet, Worksheet
import logging
from pathlib import Path
import toml
import pandas as pd

month_labels = {m: calendar.month_abbr[m] for m in range(1,13)}

def get_transaction_tab_presets(
        config_file_path: str = ".streamlit/secrets.toml"
    ) -> (dict[str, dict[str, str|bool|int]] | None):
    """
    Gets transaction presets for the Add Transaction tab.
    """
    try:
        presets: list[dict[str, str|bool|int]] = toml.loads(
            Path(config_file_path).read_text(encoding="utf-8")
        )['expense_tracker']['transaction_tab']['presets']
        if len(presets) > 0:
            def get_key(p_dict):
                key = ""
                if 'memo' in p_dict:
                    key = f"{p_dict['memo']}"
                elif 'category' in p_dict:
                    key = f"{p_dict['category']}"
                if 'owner' in p_dict:
                    return f"{key} ({p_dict['owner']})"
                return key
            return {get_key(p): p for p in presets}
        else:
            return None
    except (FileNotFoundError, toml.decoder.TomlDecodeError, KeyError):
        logging.info("No config specified, continuing without presets")
    return None

def get_transaction_tab_shared_default(
        config_file_path: str = ".streamlit/secrets.toml",
        fallback_val: bool = False
) -> bool:
    """
    Gets transaction tab default for shared field.
    """
    try:
        secrets_config: list[dict[str, str]] = toml.loads(
            Path(config_file_path).read_text(encoding="utf-8")
        )
        if 'expense_tracker' in secrets_config and \
            'transaction_tab' in secrets_config['expense_tracker'] and \
            'defaults' in secrets_config['expense_tracker']['transaction_tab'] and \
            'shared' in secrets_config['expense_tracker']['transaction_tab']['defaults']:
            return secrets_config['expense_tracker']['transaction_tab']['defaults']['shared']
        else:
            return fallback_val
    except (FileNotFoundError, toml.decoder.TomlDecodeError, KeyError):
        logging.info("No config file found")
    return fallback_val

def get_worksheet(
        config_file_path: str = ".streamlit/secrets.toml"
) -> str | None:
    """
    Gets worksheet value from secrets config file.
    This is needed to specify a worksheet for service accounts.
    """
    try:
        secrets_config: list[dict[str, str]] = toml.loads(
            Path(config_file_path).read_text(encoding="utf-8")
        )
        if 'connections' in secrets_config and \
            'gsheets' in secrets_config['connections'] and \
            'worksheet' in secrets_config['connections']['gsheets'] and \
            'type' in secrets_config['connections']['gsheets'] and \
            secrets_config['connections']['gsheets']['type'] == 'service_account':
            return secrets_config['connections']['gsheets']['worksheet']
        else:
            return None
    except (FileNotFoundError, toml.decoder.TomlDecodeError, KeyError):
        logging.info("No config file found, continuing without owner color map")
    return None

def get_spreadsheet_client(config_file_path: str = ".streamlit/secrets.toml") -> Spreadsheet | None:
    """
    Get spreadsheet client using service account
    """
    try:
        secrets_config: list[dict[str, str]] = toml.loads(
            Path(config_file_path).read_text(encoding="utf-8")
        )
        if 'connections' in secrets_config and \
            'gsheets' in secrets_config['connections'] and \
            'type' in secrets_config['connections']['gsheets'] and \
            secrets_config['connections']['gsheets']['type'] == 'service_account':
            config = secrets_config['connections']['gsheets']
            client = service_account_from_dict(config)
            spreadsheet = client.open_by_url(config['spreadsheet'])
            return spreadsheet
        else:
            return None
    except (FileNotFoundError, toml.decoder.TomlDecodeError, KeyError):
        logging.info("No config file found")
    return None

def get_worksheet_client(config_file_path: str = ".streamlit/secrets.toml",
                          check_write_perms: bool = True) -> Worksheet | None:
    """
    Get worksheet client using service account.
    """
    try:
        secrets_config: list[dict[str, str]] = toml.loads(
            Path(config_file_path).read_text(encoding="utf-8")
        )
        if 'connections' in secrets_config and \
            'gsheets' in secrets_config['connections']:
            config = secrets_config['connections']['gsheets']
            spreadsheet = get_spreadsheet_client()
            if spreadsheet:
                if check_write_perms:
                    permissions = [ p for p in spreadsheet.list_permissions() \
                        if p.get('emailAddress') == config['client_email'] ]
                    if len(permissions) > 0:
                        for p in permissions:
                            if p.get('role') != 'writer' or \
                               p.get('deleted', False) or \
                               p.get('pendingOwner', False):
                                return None
                worksheet = spreadsheet.worksheet(config['worksheet'])
                return worksheet
    except (FileNotFoundError, toml.decoder.TomlDecodeError, KeyError):
        logging.info("No config file found")
        return None


def get_worksheet_dataframe(config_file_path: str = ".streamlit/secrets.toml") -> pd.DataFrame | None:
    """
    Read all data from the configured worksheet using the service account,
    shaped the same way pd.read_csv(csv_export_url) was (first row becomes
    the DataFrame header, matching the old conn.read() behavior).

    Rows that are entirely empty (e.g. phantom rows from an over-extended
    data validation range) are dropped before building the DataFrame.
    """
    worksheet = get_worksheet_client(config_file_path=config_file_path, check_write_perms=False)
    if worksheet:
        values = worksheet.get_all_values()
        if len(values) >= 1:
            header, *rows = values
            rows = [row for row in rows if any(cell.strip() for cell in row)]
            return pd.DataFrame(rows, columns=header)
    return None

def get_google_sheet_titles_and_url(
        config_file_path: str = ".streamlit/secrets.toml",
        default_title: str | None = "Google Sheet"
) -> tuple[str, str, str] | None:
    """
    Get spreadsheet & worsksheet titles and URL from secrets config file.
    """
    try:
        secrets_config: list[dict[str, str]] = toml.loads(
            Path(config_file_path).read_text(encoding="utf-8")
        )
        if 'connections' in secrets_config and \
            'gsheets' in secrets_config['connections'] and \
            'spreadsheet' in secrets_config['connections']['gsheets']:
            config = secrets_config['connections']['gsheets']
            url = config['spreadsheet']
            spreadsheet = get_spreadsheet_client()
            if spreadsheet:
                s_title = spreadsheet.title
                worksheet = spreadsheet.worksheet(config['worksheet'])
                w_title = worksheet.title
                return s_title, w_title, url
            elif default_title:
                return default_title, '', url
    except (FileNotFoundError, toml.decoder.TomlDecodeError, KeyError):
        logging.info("No config file found")
    return None
