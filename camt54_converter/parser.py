"""Parse ISO 20022 XML files (camt.054, camt.053, pain.001, pain.008) to CSV."""

from __future__ import annotations

import csv
import io
import re
import xml.etree.ElementTree as ET
from dataclasses import dataclass, asdict
from typing import IO, Iterable, Iterator


CSV_FIELDS = [
    "source_format",
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
    source_format: str = ""
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


# ---------------------------------------------------------------------------
# Generic XML helpers
# ---------------------------------------------------------------------------

_NS_RE = re.compile(r"^\{([^}]+)\}")


def _strip_ns(tag: str) -> str:
    return tag.split("}", 1)[1] if "}" in tag else tag


def _find_ns(root: ET.Element) -> str:
    m = _NS_RE.match(root.tag)
    return m.group(1) if m else ""


class _Q:
    """Build namespaced ElementTree query strings."""

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


def _bic(agt_el: ET.Element | None, ns: str) -> str:
    if agt_el is None:
        return ""
    return _text(agt_el, "FinInstnId", "BIC", ns=ns) or _text(
        agt_el, "FinInstnId", "BICFI", ns=ns
    )


def _date(el: ET.Element | None, *path: str, ns: str = "") -> str:
    """Return a date or datetime from a camt/pain date element.

    Handles both ``<Dt>YYYY-MM-DD</Dt>`` and ``<DtTm>...</DtTm>`` child
    elements, as well as elements that carry the date directly as text
    (used in older pain schemas, e.g. ``<ReqdExctnDt>2026-01-15</ReqdExctnDt>``).
    """
    if el is None:
        return ""
    q = _Q(ns)
    container = el.find(q(*path)) if path else el
    if container is None:
        return ""
    dt = container.find(q("Dt"))
    if dt is not None and dt.text:
        return dt.text.strip()
    dttm = container.find(q("DtTm"))
    if dttm is not None and dttm.text:
        return dttm.text.strip()
    return container.text.strip() if container.text else ""


def _load(source: str | bytes | IO[bytes] | IO[str]) -> ET.Element:
    """Load XML from filename, bytes, or file-like object."""
    if isinstance(source, (bytes, bytearray)):
        return ET.fromstring(source)
    if isinstance(source, str):
        if source.lstrip().startswith("<"):
            return ET.fromstring(source)
        return ET.parse(source).getroot()
    return ET.parse(source).getroot()


# ---------------------------------------------------------------------------
# Format detection
# ---------------------------------------------------------------------------

_ROOT_TO_FORMAT = {
    "BkToCstmrDbtCdtNtfctn": "camt.054",
    "BkToCstmrStmt": "camt.053",
    "CstmrCdtTrfInitn": "pain.001",
    "CstmrDrctDbtInitn": "pain.008",
}


def detect_format(source: str | bytes | IO[bytes] | IO[str]) -> str:
    """Return the ISO 20022 short name for ``source`` (e.g. ``'camt.054'``)."""
    return _detect_format(_load(source))


def _detect_format(root: ET.Element) -> str:
    if _strip_ns(root.tag) != "Document":
        raise ValueError(
            f"Expected ISO 20022 Document root element, got '{_strip_ns(root.tag)}'"
        )
    for child in root:
        fmt = _ROOT_TO_FORMAT.get(_strip_ns(child.tag))
        if fmt:
            return fmt
    raise ValueError(
        "Unknown ISO 20022 format — expected one of: "
        + ", ".join(_ROOT_TO_FORMAT.values())
    )


# ---------------------------------------------------------------------------
# camt.054 / camt.053 (Bank-to-Customer Notification / Statement)
# ---------------------------------------------------------------------------

def _bank_tx_code(ntry: ET.Element, ns: str) -> str:
    domain = _text(ntry, "BkTxCd", "Domn", "Cd", ns=ns)
    family = _text(ntry, "BkTxCd", "Domn", "Fmly", "Cd", ns=ns)
    sub = _text(ntry, "BkTxCd", "Domn", "Fmly", "SubFmlyCd", ns=ns)
    propr = _text(ntry, "BkTxCd", "Prtry", "Cd", ns=ns)
    structured = "/".join(p for p in (domain, family, sub) if p)
    return _join([structured, propr])


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


def _extract_camt_tx(
    ntry: ET.Element,
    tx_dtls: ET.Element,
    ns: str,
    *,
    source_format: str,
    statement_id: str,
    account_iban: str,
    account_currency: str,
) -> Transaction:
    amount, currency = _parse_amount(ntry.find(_Q(ns)("Amt")))
    tx_amount, tx_currency = _parse_amount(tx_dtls.find(_Q(ns)("Amt")))
    if tx_amount:
        amount, currency = tx_amount, tx_currency or currency

    cdt_dbt = _text(tx_dtls, "CdtDbtInd", ns=ns) or _text(ntry, "CdtDbtInd", ns=ns)

    booking = _date(ntry, "BookgDt", ns=ns)
    value = _date(ntry, "ValDt", ns=ns)

    reversal = _text(tx_dtls, "RvslInd", ns=ns) or _text(ntry, "RvslInd", ns=ns)
    status = _text(ntry, "Sts", "Cd", ns=ns) or _text(ntry, "Sts", ns=ns)

    is_credit = cdt_dbt == "CRDT"
    rltd_pties = tx_dtls.find(_Q(ns)("RltdPties"))
    counterparty_el: ET.Element | None = None
    counterparty_acct_el: ET.Element | None = None
    if rltd_pties is not None:
        if is_credit:
            counterparty_el = rltd_pties.find(_Q(ns)("Dbtr"))
            counterparty_acct_el = rltd_pties.find(_Q(ns)("DbtrAcct"))
        else:
            counterparty_el = rltd_pties.find(_Q(ns)("Cdtr"))
            counterparty_acct_el = rltd_pties.find(_Q(ns)("CdtrAcct"))
        if counterparty_el is not None:
            inner = counterparty_el.find(_Q(ns)("Pty")) or counterparty_el.find(
                _Q(ns)("Agt")
            )
            if inner is not None:
                counterparty_el = inner

    rltd_agts = tx_dtls.find(_Q(ns)("RltdAgts"))
    counterparty_bic = ""
    if rltd_agts is not None:
        agt_tag = "DbtrAgt" if is_credit else "CdtrAgt"
        counterparty_bic = _bic(rltd_agts.find(_Q(ns)(agt_tag)), ns)

    refs = tx_dtls.find(_Q(ns)("Refs"))
    creditor_id = _text(
        tx_dtls, "RltdPties", "Cdtr", "Id", "PrvtId", "Othr", "Id", ns=ns
    ) or _text(
        tx_dtls, "RltdPties", "Cdtr", "Id", "OrgId", "Othr", "Id", ns=ns
    )

    return Transaction(
        source_format=source_format,
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
        end_to_end_id=_text(refs, "EndToEndId", ns=ns),
        mandate_id=_text(refs, "MndtId", ns=ns),
        creditor_id=creditor_id,
        counterparty_name=_related_party_name(counterparty_el, ns),
        counterparty_iban=_iban_or_other(counterparty_acct_el, ns),
        counterparty_bic=counterparty_bic,
        remittance_info=_remittance(tx_dtls, ns),
        additional_info=_join(
            [_text(ntry, "AddtlNtryInf", ns=ns), _text(tx_dtls, "AddtlTxInf", ns=ns)]
        ),
    )


def _parse_camt(
    root: ET.Element, wrapper: str, container: str, source_format: str
) -> list[Transaction]:
    ns = _find_ns(root)
    q = _Q(ns)
    elements = root.findall(q(wrapper, container))
    if not elements:
        raise ValueError(
            f"No <{container}> element found inside <{wrapper}> — "
            f"does not look like a {source_format} file"
        )

    transactions: list[Transaction] = []
    for stmt in elements:
        statement_id = _text(stmt, "Id", ns=ns)
        acct = stmt.find(q("Acct"))
        account_iban = _iban_or_other(acct, ns)
        account_currency = _text(acct, "Ccy", ns=ns) if acct is not None else ""

        for ntry in stmt.findall(q("Ntry")):
            for tx_dtls in _iter_tx_details(ntry, ns):
                transactions.append(
                    _extract_camt_tx(
                        ntry,
                        tx_dtls,
                        ns,
                        source_format=source_format,
                        statement_id=statement_id,
                        account_iban=account_iban,
                        account_currency=account_currency,
                    )
                )

    return transactions


# ---------------------------------------------------------------------------
# pain.001 / pain.008 (Customer Credit Transfer / Direct Debit Initiation)
# ---------------------------------------------------------------------------

def _pain_remittance(tx: ET.Element, ns: str) -> str:
    q = _Q(ns)
    parts: list[str] = _all_texts(tx, "RmtInf", "Ustrd", ns=ns)
    for strd in tx.findall(q("RmtInf", "Strd")):
        parts.extend(_all_texts(strd, "AddtlRmtInf", ns=ns))
        ref = _text(strd, "CdtrRefInf", "Ref", ns=ns)
        if ref:
            parts.append(f"Ref: {ref}")
    return _join(parts)


def _parse_pain001(root: ET.Element) -> list[Transaction]:
    ns = _find_ns(root)
    q = _Q(ns)
    initn = root.find(q("CstmrCdtTrfInitn"))
    if initn is None:
        raise ValueError("Missing <CstmrCdtTrfInitn> — not a pain.001 file")

    message_id = _text(initn, "GrpHdr", "MsgId", ns=ns)
    transactions: list[Transaction] = []

    for pmt in initn.findall(q("PmtInf")):
        debtor = pmt.find(q("Dbtr"))
        debtor_acct = pmt.find(q("DbtrAcct"))
        debtor_iban = _iban_or_other(debtor_acct, ns)
        debtor_currency = _text(debtor_acct, "Ccy", ns=ns)
        exec_date = _date(pmt, "ReqdExctnDt", ns=ns)
        service_level = _text(pmt, "PmtTpInf", "SvcLvl", "Cd", ns=ns)

        for tx in pmt.findall(q("CdtTrfTxInf")):
            amount, currency = _parse_amount(tx.find(q("Amt", "InstdAmt")))
            transactions.append(
                Transaction(
                    source_format="pain.001",
                    statement_id=message_id,
                    account_iban=debtor_iban,
                    account_currency=debtor_currency,
                    value_date=exec_date,
                    amount=amount,
                    currency=currency,
                    credit_debit="DBIT",
                    bank_tx_code=service_level,
                    end_to_end_id=_text(tx, "PmtId", "EndToEndId", ns=ns),
                    counterparty_name=_related_party_name(tx.find(q("Cdtr")), ns),
                    counterparty_iban=_iban_or_other(tx.find(q("CdtrAcct")), ns),
                    counterparty_bic=_bic(tx.find(q("CdtrAgt")), ns),
                    remittance_info=_pain_remittance(tx, ns),
                    additional_info=_join(
                        [
                            _related_party_name(debtor, ns),
                            _text(pmt, "PmtInfId", ns=ns),
                        ]
                    ),
                )
            )

    return transactions


def _parse_pain008(root: ET.Element) -> list[Transaction]:
    ns = _find_ns(root)
    q = _Q(ns)
    initn = root.find(q("CstmrDrctDbtInitn"))
    if initn is None:
        raise ValueError("Missing <CstmrDrctDbtInitn> — not a pain.008 file")

    message_id = _text(initn, "GrpHdr", "MsgId", ns=ns)
    transactions: list[Transaction] = []

    for pmt in initn.findall(q("PmtInf")):
        creditor = pmt.find(q("Cdtr"))
        creditor_acct = pmt.find(q("CdtrAcct"))
        creditor_iban = _iban_or_other(creditor_acct, ns)
        creditor_currency = _text(creditor_acct, "Ccy", ns=ns)
        coll_date = _date(pmt, "ReqdColltnDt", ns=ns)
        service_level = _text(pmt, "PmtTpInf", "SvcLvl", "Cd", ns=ns)
        seq_type = _text(pmt, "PmtTpInf", "SeqTp", ns=ns)
        creditor_id = _text(
            pmt, "CdtrSchmeId", "Id", "PrvtId", "Othr", "Id", ns=ns
        ) or _text(pmt, "CdtrSchmeId", "Id", "OrgId", "Othr", "Id", ns=ns)

        for tx in pmt.findall(q("DrctDbtTxInf")):
            amount, currency = _parse_amount(tx.find(q("InstdAmt")))
            transactions.append(
                Transaction(
                    source_format="pain.008",
                    statement_id=message_id,
                    account_iban=creditor_iban,
                    account_currency=creditor_currency,
                    value_date=coll_date,
                    amount=amount,
                    currency=currency,
                    credit_debit="CRDT",
                    bank_tx_code=_join([service_level, seq_type], sep="/"),
                    end_to_end_id=_text(tx, "PmtId", "EndToEndId", ns=ns),
                    mandate_id=_text(
                        tx, "DrctDbtTx", "MndtRltdInf", "MndtId", ns=ns
                    ),
                    creditor_id=creditor_id,
                    counterparty_name=_related_party_name(tx.find(q("Dbtr")), ns),
                    counterparty_iban=_iban_or_other(tx.find(q("DbtrAcct")), ns),
                    counterparty_bic=_bic(tx.find(q("DbtrAgt")), ns),
                    remittance_info=_pain_remittance(tx, ns),
                    additional_info=_join(
                        [
                            _related_party_name(creditor, ns),
                            _text(pmt, "PmtInfId", ns=ns),
                        ]
                    ),
                )
            )

    return transactions


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def parse(source: str | bytes | IO[bytes] | IO[str]) -> list[Transaction]:
    """Parse any supported ISO 20022 XML document.

    Auto-detects the format (camt.054, camt.053, pain.001, pain.008) by
    inspecting the document root. Returns a flat list of transactions.
    """
    root = _load(source)
    fmt = _detect_format(root)
    if fmt == "camt.054":
        return _parse_camt(root, "BkToCstmrDbtCdtNtfctn", "Ntfctn", "camt.054")
    if fmt == "camt.053":
        return _parse_camt(root, "BkToCstmrStmt", "Stmt", "camt.053")
    if fmt == "pain.001":
        return _parse_pain001(root)
    if fmt == "pain.008":
        return _parse_pain008(root)
    raise ValueError(f"Unsupported format: {fmt}")


def parse_camt054(source: str | bytes | IO[bytes] | IO[str]) -> list[Transaction]:
    """Parse a camt.054 document specifically. Errors if ``source`` is another format."""
    root = _load(source)
    fmt = _detect_format(root)
    if fmt != "camt.054":
        raise ValueError(f"Expected camt.054, got {fmt}")
    return _parse_camt(root, "BkToCstmrDbtCdtNtfctn", "Ntfctn", "camt.054")


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
