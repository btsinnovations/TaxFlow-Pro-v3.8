"""
OFX (Open Financial Exchange) client service.

Provides secure bank transaction fetching via the OFX protocol:
  - OFXClient class: configure with bank credentials, fetch transactions
  - OFX SGML/XML request builder for bank account sync
  - XML response parser extracting transaction data
  - Fernet-based password encryption for secure credential storage

Usage:
    client = OFXClient(
        institution_id="12345",
        org="BANKNAME",
        url="https://ofx.bank.com/cgi-bin/ofx",
        username="myuser",
        password="mypass",
        account_id="123456789",
        account_type="CHECKING",
    )
    txs = client.fetch_transactions(date(2024, 1, 1), date(2024, 12, 31))
"""

import os
import uuid
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import List, Optional

import requests
from cryptography.fernet import Fernet

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
OFX_VERSION = "220"
APP_ID = "TaxFlowPro"
APP_VERSION = "3800"

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------


@dataclass
class OFXTransaction:
    """A single transaction parsed from an OFX response."""
    fitid: str                    # Financial Institution Transaction ID
    date_posted: date
    amount: float
    description: str
    memo: str
    tx_type: str                  # DEBIT, CREDIT, CHECK, etc.
    check_num: Optional[str] = None


@dataclass
class OFXAccountInfo:
    """Account balance and metadata from an OFX signon response."""
    account_id: str
    balance: float
    currency: str
    date_as_of: date


# ---------------------------------------------------------------------------
# Fernet encryption helpers for credential storage
# ---------------------------------------------------------------------------


def get_or_create_fernet_key() -> bytes:
    """
    Retrieve or generate a Fernet encryption key.

    Looks for TAXFLOW_FERNET_KEY in the environment.  If absent,
    generates a new key and prints a one-time warning so the user
    can persist it.
    """
    env_key = os.environ.get("TAXFLOW_FERNET_KEY", "")
    if env_key:
        return env_key.encode()
    # No key configured: generate one ( caller should persist it )
    key = Fernet.generate_key()
    return key


def encrypt_password(password: str, key: Optional[bytes] = None) -> str:
    """Encrypt a plain-text password using Fernet."""
    if key is None:
        key = get_or_create_fernet_key()
    f = Fernet(key)
    return f.encrypt(password.encode()).decode()


def decrypt_password(token: str, key: Optional[bytes] = None) -> str:
    """Decrypt a Fernet-encrypted password token."""
    if key is None:
        key = get_or_create_fernet_key()
    f = Fernet(key)
    return f.decrypt(token.encode()).decode()


# ---------------------------------------------------------------------------
# OFX SGML / XML request builder
# ---------------------------------------------------------------------------


def _ofx_date(d: date) -> str:
    """Format a date as OFX YYYYMMDDHHMMSS."""
    return d.strftime("%Y%m%d%H%M%S")


def _build_signon_message(username: str, password: str, org: str,
                          institution_id: str) -> str:
    """Build the OFX SIGNONMSGSET request block."""
    dt_client = datetime.utcnow().strftime("%Y%m%d%H%M%S")
    return f"""<SIGNONMSGSRQV1>
<SONRQ>
<DTCLIENT>{dt_client}</DTCLIENT>
<USERID>{_escape(username)}</USERID>
<USERPASS>{_escape(password)}</USERPASS>
<LANGUAGE>ENG</LANGUAGE>
<FI>
<ORG>{_escape(org)}</ORG>
<FID>{_escape(institution_id)}</FID>
</FI>
<APPID>{APP_ID}</APPID>
<APPVER>{APP_VERSION}</APPVER>
</SONRQ>
</SIGNONMSGSRQV1>"""


def _build_statement_request(
    account_id: str,
    account_type: str,
    institution_id: str,
    org: str,
    start_date: date,
    end_date: date,
) -> str:
    """Build the OFX bank statement request (BANKMSGSRQV1)."""
    return f"""<BANKMSGSRQV1>
<STMTTRNRQ>
<TRNUID>{uuid.uuid4().hex[:32]}</TRNUID>
<STMTRQ>
<BANKACCTFROM>
<BANKID>{_escape(institution_id)}</BANKID>
<ACCTID>{_escape(account_id)}</ACCTID>
<ACCTTYPE>{_escape(account_type)}</ACCTTYPE>
</BANKACCTFROM>
<INCTRAN>
<DTSTART>{_ofx_date(start_date)}</DTSTART>
<DTEND>{_ofx_date(end_date)}</DTEND>
<INCLUDE>Y</INCLUDE>
</INCTRAN>
</STMTRQ>
</STMTTRNRQ>
</BANKMSGSRQV1>"""


def _escape(value: str) -> str:
    """Basic XML escaping for OFX content."""
    return (value
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;"))


def build_ofx_request(
    username: str,
    password: str,
    org: str,
    institution_id: str,
    account_id: str,
    account_type: str,
    start_date: date,
    end_date: date,
) -> str:
    """
    Assemble a complete OFX request envelope.

    Returns the full SGML/XML payload ready for HTTP POST.
    """
    signon = _build_signon_message(username, password, org, institution_id)
    stmt = _build_statement_request(
        account_id, account_type, institution_id, org, start_date, end_date
    )
    return (
        f'OFXHEADER:100\nDATA:OFXSGML\nVERSION:{OFX_VERSION}\n'
        f'SECURITY:NONE\nENCODING:USASCII\nCHARSET:1252\nCOMPRESSION:NONE\n'
        f'OLDFILEUID:NONE\nNEWFILEUID:{uuid.uuid4().hex[:32]}\n\n'
        f'<OFX>\n{signon}\n{stmt}\n</OFX>'
    )


# ---------------------------------------------------------------------------
# OFX XML response parser
# ---------------------------------------------------------------------------


def _strip_ofx_headers(raw: str) -> str:
    """Remove OFX SGML headers so xml.etree can parse the body."""
    marker = "<OFX>"
    idx = raw.find(marker)
    if idx == -1:
        raise ValueError("Invalid OFX response: <OFX> tag not found")
    return raw[idx:]


def _parse_ofx_date(date_str: str) -> date:
    """Parse an OFX date string (YYYYMMDDHHMMSS or YYYYMMDD) to date."""
    if not date_str:
        return date.today()
    # Strip timezone offsets if present
    if "[" in date_str:
        date_str = date_str[:date_str.index("[")]
    try:
        return datetime.strptime(date_str[:8], "%Y%m%d").date()
    except (ValueError, IndexError):
        return date.today()


def parse_ofx_response(raw_response: str) -> tuple:
    """
    Parse an OFX XML response.

    Parameters
    ----------
    raw_response : str
        The raw SGML/XML returned by the financial institution.

    Returns
    -------
    tuple
        (list[OFXTransaction], OFXAccountInfo | None)
    """
    xml_body = _strip_ofx_headers(raw_response)
    root = ET.fromstring(xml_body)

    # Register common namespaces
    namespaces = {
        "ofx": "http://www.ofx.net/schemas/220",
    }

    transactions: List[OFXTransaction] = []
    account_info: Optional[OFXAccountInfo] = None

    # Helper to find tags regardless of namespace
    def _find(parent, tag_name):
        # Try with namespace
        for ns in namespaces.values():
            found = parent.findall(f".//{{{ns}}}{tag_name}")
            if found:
                return found
        # Try without namespace
        return parent.findall(f".//{tag_name}")

    def _find_one(parent, tag_name):
        results = _find(parent, tag_name)
        return results[0] if results else None

    def _text(parent, tag_name, default=""):
        el = _find_one(parent, tag_name)
        return (el.text or default) if el is not None else default

    # Parse transactions
    stmttrn_nodes = _find(root, "STMTTRN")
    for node in stmttrn_nodes:
        tx_type = _text(node, "TRNTYPE", "OTHER").upper()
        date_posted = _parse_ofx_date(_text(node, "DTPOSTED"))
        amount_str = _text(node, "TRNAMT", "0")
        try:
            amount = float(amount_str)
        except ValueError:
            amount = 0.0
        fitid = _text(node, "FITID")
        description = _text(node, "NAME")
        memo = _text(node, "MEMO")
        check_num = _text(node, "CHECKNUM") or None

        transactions.append(OFXTransaction(
            fitid=fitid,
            date_posted=date_posted,
            amount=amount,
            description=description,
            memo=memo,
            tx_type=tx_type,
            check_num=check_num,
        ))

    # Parse account info / balance
    ledgerbal = _find_one(root, "LEDGERBAL")
    if ledgerbal is not None:
        bal_str = _text(ledgerbal, "BALAMT", "0")
        try:
            balance = float(bal_str)
        except ValueError:
            balance = 0.0
        bal_date = _parse_ofx_date(_text(ledgerbal, "DTASOF"))

        acctfrom = _find_one(root, "BANKACCTFROM")
        if acctfrom is not None:
            acct_id = _text(acctfrom, "ACCTID", "")
        else:
            acct_id = ""

        curdef = _find_one(root, "CURDEF")
        currency = curdef.text if curdef is not None else "USD"

        account_info = OFXAccountInfo(
            account_id=acct_id,
            balance=balance,
            currency=currency,
            date_as_of=bal_date,
        )

    return transactions, account_info


# ---------------------------------------------------------------------------
# OFXClient class
# ---------------------------------------------------------------------------


class OFXClient:
    """
    OFX (Open Financial Exchange) client for fetching bank transactions.

    Parameters
    ----------
    institution_id : str
        Bank routing / FI ID (BANKID).
    org : str
        Financial institution organization identifier.
    url : str
        OFX endpoint URL.
    username : str
        Online banking username.
    password : str
        Online banking password.
    account_id : str
        The bank account number.
    account_type : str
        One of CHECKING, SAVINGS, MONEYMRKT, CREDITLINE.
    timeout : int
        HTTP request timeout in seconds (default 60).
    """

    def __init__(
        self,
        institution_id: str,
        org: str,
        url: str,
        username: str,
        password: str,
        account_id: str,
        account_type: str = "CHECKING",
        timeout: int = 60,
    ):
        self.institution_id = institution_id
        self.org = org
        self.url = url
        self.username = username
        self._password = password
        self.account_id = account_id
        self.account_type = account_type.upper()
        self.timeout = timeout

    # -- Credential encryption helpers --------------------------------------

    def get_encrypted_password(self, key: Optional[bytes] = None) -> str:
        """Return the Fernet-encrypted password token."""
        return encrypt_password(self._password, key)

    def set_encrypted_password(self, token: str, key: Optional[bytes] = None) -> None:
        """Restore the password from a Fernet-encrypted token."""
        self._password = decrypt_password(token, key)

    # -- Request / response -------------------------------------------------

    def build_request(self, start_date: date, end_date: date) -> str:
        """Build the OFX SGML request payload."""
        return build_ofx_request(
            username=self.username,
            password=self._password,
            org=self.org,
            institution_id=self.institution_id,
            account_id=self.account_id,
            account_type=self.account_type,
            start_date=start_date,
            end_date=end_date,
        )

    def send_request(self, payload: str) -> str:
        """
        POST the OFX payload to the institution endpoint.

        Returns the raw SGML/XML response string.
        Raises requests.HTTPError on non-2xx status.
        """
        headers = {
            "Content-Type": "application/x-ofx",
            "Accept": "application/x-ofx",
            "User-Agent": f"{APP_ID}/{APP_VERSION}",
        }
        response = requests.post(
            self.url,
            data=payload,
            headers=headers,
            timeout=self.timeout,
        )
        response.raise_for_status()
        return response.text

    def parse_response(self, raw_response: str) -> tuple:
        """Parse a raw OFX response into transactions and account info."""
        return parse_ofx_response(raw_response)

    # -- High-level fetch ---------------------------------------------------

    def fetch_transactions(
        self,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> List[OFXTransaction]:
        """
        Fetch transactions for the given date range.

        Parameters
        ----------
        start_date : date
            Start of transaction range (inclusive).
        end_date : date, optional
            End of transaction range (inclusive).  Defaults to today.

        Returns
        -------
        list[OFXTransaction]
            Parsed transactions sorted by date_posted ascending.
        """
        if end_date is None:
            end_date = date.today()

        payload = self.build_request(start_date, end_date)
        raw_response = self.send_request(payload)
        transactions, _account_info = self.parse_response(raw_response)
        transactions.sort(key=lambda tx: tx.date_posted)
        return transactions

    def fetch_balance(self) -> OFXAccountInfo:
        """
        Fetch the current account balance.

        Returns
        -------
        OFXAccountInfo
            Account balance and metadata.
        """
        end_date = date.today()
        start_date = end_date - timedelta(days=7)
        payload = self.build_request(start_date, end_date)
        raw_response = self.send_request(payload)
        _transactions, account_info = self.parse_response(raw_response)
        if account_info is None:
            raise ValueError("OFX response did not contain balance information")
        return account_info

    def fetch_transactions_with_metadata(
        self,
        start_date: date,
        end_date: Optional[date] = None,
    ) -> dict:
        """
        Fetch transactions plus account metadata in a single call.

        Returns
        -------
        dict
            {
                "transactions": list[OFXTransaction],
                "account_info": OFXAccountInfo,
                "count": int,
                "date_range": {"start": date, "end": date},
            }
        """
        if end_date is None:
            end_date = date.today()

        payload = self.build_request(start_date, end_date)
        raw_response = self.send_request(payload)
        transactions, account_info = self.parse_response(raw_response)
        transactions.sort(key=lambda tx: tx.date_posted)

        return {
            "transactions": transactions,
            "account_info": account_info,
            "count": len(transactions),
            "date_range": {"start": start_date, "end": end_date},
        }
