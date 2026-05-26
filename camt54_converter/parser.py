"""Parse camt.054 (ISO 20022) XML files and emit per-transaction rows."""

from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict, fields
from typing import IO, Iterable, Iterator


CSV_FIELDS = [
    "statement_id",
    "account_iban",
    "account_currency",
    "booking_date",
    "value_date",
    "amount",
    "currency",
    "credit_debit",
    "reversal",
    "status",
    "bank_tx_code",
    "end_to_end_id",
    "mandate_id",
    "creditor_id",
    "counterparty_name",
    "counterparty_iban",
    "counterparty_bic",
    "remittance_info",
    "additional_info",
]


@dataclass
class Transaction:
    statement_id: str = ""
    account_iban: str = ""
    account_currency: str = ""
    booking_date: str = ""
    value_date: str = ""
    amount: str = ""
    currency: str = ""
    credit_debit: str = ""
    reversal: str = ""
    status: str = ""
    bank_tx_code: str = ""
    end_to_end_id: str = ""
    mandate_id: str = ""
    creditor_id: str = ""
    counterparty_name: str = ""
    counterparty_iban: str = ""
    counterparty_bic: str = ""
    remittance_info: str = ""
    additional_info: str = ""

    def as_row(self) -> dict[str, str]:
        return asdict(self)


_NS_RE = re.compile(r"^\{([^}]+)\}")


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _find_ns(root: ET.Element) -> str:
    m = _NS_RE.match(root.tag)
    return m.group(1) if m else ""


class _Q:
    """Small helper to build namespaced ElementTree queries."""

    def __init__(self, ns: str) -> None:
        self.ns = f"{{{ns}}}" if ns else ""

    def __call__(self, *parts: str) -> str:
        return "/".join(f"{self.ns}{p}" for p in parts)


def _text(el: ET.Element | None, *path: str, ns: str = "") -> str:
    if el is None:
        return ""
    q = _Q(ns)
    found = el.find(q(*path)) if path else el
    if found is None or found.text is None:
        return ""
    return found.text.strip()


def _all_texts(el: ET.Element | None, *path: str, ns: str = "") -> list[str]:
    if el is None:
        return []
    q = _Q(ns)
    return [e.text.strip() for e in el.findall(q(*path)) if e.text]


def _join(parts: Iterable[str], sep: str = " | ") -> str:
    return sep.join(p for p in parts if p)


def _parse_amount(el: ET.Element | None) -> tuple[str, str]:
    if el is None or el.text is None:
        return "", ""
    return el.text.strip(), el.attrib.get("Ccy", "")


def _bank_tx_code(ntry: ET.Element, ns: str) -> str:
    q = _Q(ns)
    domain = _text(ntry, "BkTxCd", "Domn", "Cd", ns=ns)
    family = _text(ntry, "BkTxCd", "Domn", "Fmly", "Cd", ns=ns)
    sub = _text(ntry, "BkTxCd", "Domn", "Fmly", "SubFmlyCd", ns=ns)
    propr = _text(ntry, "BkTxCd", "Prtry", "Cd", ns=ns)
    structured = "/".join(p for p in (domain, family, sub) if p)
    return _join([structured, propr])


def _related_party_name(party_el: ET.Element | None, ns: str) -> str:
    if party_el is None:
        return ""
    name = _text(party_el, "Nm", ns=ns)
    if name:
        return name
    parts = _all_texts(party_el, "PstlAdr", "AdrLine", ns=ns)
    return _join(parts, sep=", ")


def _iban_or_other(acct_el: ET.Element | None, ns: str) -> str:
    if acct_el is None:
        return ""
    iban = _text(acct_el, "Id", "IBAN", ns=ns)
    if iban:
        return iban
    return _text(acct_el, "Id", "Othr", "Id", ns=ns)


def _remittance(tx_dtls: ET.Element | None, ns: str) -> str:
    if tx_dtls is None:
        return ""
    q = _Q(ns)
    parts: list[str] = []
    parts.extend(_all_texts(tx_dtls, "RmtInf", "Ustrd", ns=ns))
    for strd in tx_dtls.findall(q("RmtInf", "Strd")):
        parts.extend(_all_texts(strd, "AddtlRmtInf", ns=ns))
        ref = _text(strd, "CdtrRefInf", "Ref", ns=ns)
        if ref:
            parts.append(f"Ref: {ref}")
    return _join(parts)


def _iter_tx_details(ntry: ET.Element, ns: str) -> Iterator[ET.Element]:
    q = _Q(ns)
    found = list(ntry.findall(q("NtryDtls", "TxDtls")))
    if found:
        yield from found
    else:
        yield ET.Element("EmptyTxDtls")


def _extract_tx(
    ntry: ET.Element,
    tx_dtls: ET.Element,
    ns: str,
    *,
    statement_id: str,
    account_iban: str,
    account_currency: str,
) -> Transaction:
    amount, currency = _parse_amount(ntry.find(_Q(ns)("Amt")))
    tx_amount, tx_currency = _parse_amount(tx_dtls.find(_Q(ns)("Amt")))
    if tx_amount:
        amount, currency = tx_amount, tx_currency or currency

    cdt_dbt = _text(ntry, "CdtDbtInd", ns=ns)
    tx_cdt_dbt = _text(tx_dtls, "CdtDbtInd", ns=ns)
    if tx_cdt_dbt:
        cdt_dbt = tx_cdt_dbt

    booking = _text(ntry, "BookgDt", "Dt", ns=ns) or _text(ntry, "BookgDt", "DtTm", ns=ns)
    value = _text(ntry, "ValDt", "Dt", ns=ns) or _text(ntry, "ValDt", "DtTm", ns=ns)

    reversal = _text(tx_dtls, "RvslInd", ns=ns) or _text(ntry, "RvslInd", ns=ns)
    status = _text(ntry, "Sts", "Cd", ns=ns) or _text(ntry, "Sts", ns=ns)

    is_credit = cdt_dbt == "CRDT"
    rltd_pties = tx_dtls.find(_Q(ns)("RltdPties"))
    counterparty_el = None
    counterparty_acct_el = None
    if rltd_pties is not None:
        if is_credit:
            counterparty_el = rltd_pties.find(_Q(ns)("Dbtr"))
            counterparty_acct_el = rltd_pties.find(_Q(ns)("DbtrAcct"))
        else:
            counterparty_el = rltd_pties.find(_Q(ns)("Cdtr"))
            counterparty_acct_el = rltd_pties.find(_Q(ns)("CdtrAcct"))
        if counterparty_el is not None:
            inner = counterparty_el.find(_Q(ns)("Pty")) or counterparty_el.find(_Q(ns)("Agt"))
            if inner is not None:
                counterparty_el = inner

    counterparty_name = _related_party_name(counterparty_el, ns)
    counterparty_iban = _iban_or_other(counterparty_acct_el, ns)

    rltd_agts = tx_dtls.find(_Q(ns)("RltdAgts"))
    counterparty_bic = ""
    if rltd_agts is not None:
        agt_tag = "DbtrAgt" if is_credit else "CdtrAgt"
        agt = rltd_agts.find(_Q(ns)(agt_tag))
        if agt is not None:
            counterparty_bic = _text(agt, "FinInstnId", "BIC", ns=ns) or _text(
                agt, "FinInstnId", "BICFI", ns=ns
            )

    refs = tx_dtls.find(_Q(ns)("Refs"))
    end_to_end = _text(refs, "EndToEndId", ns=ns)
    mandate_id = _text(refs, "MndtId", ns=ns)

    creditor_id = _text(
        tx_dtls, "RltdPties", "Cdtr", "Id", "PrvtId", "Othr", "Id", ns=ns
    ) or _text(
        tx_dtls, "RltdPties", "Cdtr", "Id", "OrgId", "Othr", "Id", ns=ns
    )

    remittance = _remittance(tx_dtls, ns)
    addtl_ntry = _text(ntry, "AddtlNtryInf", ns=ns)
    addtl_tx = _text(tx_dtls, "AddtlTxInf", ns=ns)
    additional = _join([addtl_ntry, addtl_tx])

    return Transaction(
        statement_id=statement_id,
        account_iban=account_iban,
        account_currency=account_currency,
        booking_date=booking,
        value_date=value,
        amount=amount,
        currency=currency,
        credit_debit=cdt_dbt,
        reversal=reversal,
        status=status,
        bank_tx_code=_bank_tx_code(ntry, ns),
        end_to_end_id=end_to_end,
        mandate_id=mandate_id,
        creditor_id=creditor_id,
        counterparty_name=counterparty_name,
        counterparty_iban=counterparty_iban,
        counterparty_bic=counterparty_bic,
        remittance_info=remittance,
        additional_info=additional,
    )


def parse_camt054(source: str | bytes | IO[bytes] | IO[str]) -> list[Transaction]:
    """Parse a camt.054 XML document.

    Accepts a filename, bytes, or a file-like object. Returns a flat list of
    transactions, one per ``TxDtls`` entry (or one per ``Ntry`` if no details).
    """
    if isinstance(source, (bytes, bytearray)):
        root = ET.fromstring(source)
    elif isinstance(source, str):
        if source.lstrip().startswith("<"):
            root = ET.fromstring(source)
        else:
            root = ET.parse(source).getroot()
    else:
        root = ET.parse(source).getroot()

    ns = _find_ns(root)
    q = _Q(ns)

    if not _strip_ns(root.tag).startswith("Document"):
        raise ValueError(
            f"Expected ISO 20022 Document root element, got '{_strip_ns(root.tag)}'"
        )

    ntfctn_elems = root.findall(q("BkToCstmrDbtCdtNtfctn", "Ntfctn"))
    if not ntfctn_elems:
        raise ValueError(
            "No <Ntfctn> element found — this does not look like a camt.054 file"
        )

    transactions: list[Transaction] = []
    for ntfctn in ntfctn_elems:
        statement_id = _text(ntfctn, "Id", ns=ns)
        acct = ntfctn.find(q("Acct"))
        account_iban = _iban_or_other(acct, ns)
        account_currency = _text(acct, "Ccy", ns=ns) if acct is not None else ""

        for ntry in ntfctn.findall(q("Ntry")):
            for tx_dtls in _iter_tx_details(ntry, ns):
                transactions.append(
                    _extract_tx(
                        ntry,
                        tx_dtls,
                        ns,
                        statement_id=statement_id,
                        account_iban=account_iban,
                        account_currency=account_currency,
                    )
                )

    return transactions


def write_csv(
    transactions: Iterable[Transaction],
    target: IO[str],
    *,
    delimiter: str = ";",
) -> int:
    """Write transactions as CSV to ``target``. Returns the row count."""
    writer = csv.DictWriter(
        target, fieldnames=CSV_FIELDS, delimiter=delimiter, extrasaction="ignore"
    )
    writer.writeheader()
    count = 0
    for tx in transactions:
        writer.writerow(tx.as_row())
        count += 1
    return count


def to_csv_string(transactions: Iterable[Transaction], *, delimiter: str = ";") -> str:
    buf = io.StringIO()
    write_csv(transactions, buf, delimiter=delimiter)
    return buf.getvalue()
