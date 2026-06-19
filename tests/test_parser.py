"""Tests for the ISO 20022 parser."""

from pathlib import Path

import pytest

from camt54_converter.parser import (
    CSV_FIELDS,
    detect_format,
    parse,
    parse_camt054,
    to_csv_string,
)


SAMPLES = Path(__file__).parent
CAMT054 = SAMPLES / "sample_camt054.xml"
CAMT053 = SAMPLES / "sample_camt053.xml"
PAIN001 = SAMPLES / "sample_pain001.xml"
PAIN008 = SAMPLES / "sample_pain008.xml"


# --- format detection -------------------------------------------------------

@pytest.mark.parametrize(
    "path,expected",
    [
        (CAMT054, "camt.054"),
        (CAMT053, "camt.053"),
        (PAIN001, "pain.001"),
        (PAIN008, "pain.008"),
    ],
)
def test_detect_format(path, expected):
    assert detect_format(path.read_bytes()) == expected


def test_rejects_non_iso20022_document():
    with pytest.raises(ValueError, match="ISO 20022 Document"):
        detect_format(b"<foo/>")


def test_rejects_unknown_iso20022_format():
    xml = (
        b'<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.054.001.02">'
        b"<Other/></Document>"
    )
    with pytest.raises(ValueError, match="Unknown ISO 20022 format"):
        detect_format(xml)


# --- camt.054 ---------------------------------------------------------------

@pytest.fixture
def camt054_txs():
    return parse(CAMT054.read_bytes())


def test_camt054_parses_two_transactions(camt054_txs):
    assert len(camt054_txs) == 2
    assert all(tx.source_format == "camt.054" for tx in camt054_txs)


def test_camt054_credit_fields(camt054_txs):
    credit = camt054_txs[0]
    assert credit.statement_id == "NTF-20260115-0001"
    assert credit.account_iban == "DE89370400440532013000"
    assert credit.credit_debit == "CRDT"
    assert credit.amount == "150.75"
    assert credit.counterparty_name == "Max Mustermann GmbH"
    assert credit.counterparty_iban == "DE12500105170648489890"
    assert credit.counterparty_bic == "INGDDEFFXXX"
    assert credit.end_to_end_id == "RECHNUNG-2026-001"
    assert credit.bank_tx_code == "PMNT/RCDT/ESCT"


def test_camt054_debit_fields(camt054_txs):
    debit = camt054_txs[1]
    assert debit.credit_debit == "DBIT"
    assert debit.amount == "42.00"
    assert debit.counterparty_name == "Stadtwerke Beispielheim"
    assert debit.mandate_id == "MANDAT-12345"
    assert debit.creditor_id == "DE98ZZZ09999999999"


def test_legacy_parse_camt054_helper():
    txs = parse_camt054(CAMT054.read_bytes())
    assert len(txs) == 2


def test_legacy_parse_camt054_rejects_other_formats():
    with pytest.raises(ValueError, match="Expected camt.054"):
        parse_camt054(PAIN001.read_bytes())


def test_camt054_namespace_variants():
    xml = CAMT054.read_text().replace("camt.054.001.02", "camt.054.001.08")
    txs = parse(xml.encode("utf-8"))
    assert len(txs) == 2


# --- camt.053 ---------------------------------------------------------------

def test_camt053_parses_one_transaction():
    txs = parse(CAMT053.read_bytes())
    assert len(txs) == 1
    tx = txs[0]
    assert tx.source_format == "camt.053"
    assert tx.statement_id == "STM-2026-01"
    assert tx.account_iban == "DE89370400440532013000"
    assert tx.amount == "980.00"
    assert tx.credit_debit == "CRDT"
    assert tx.counterparty_name == "ACME Beispiel AG"
    assert tx.end_to_end_id == "GEHALT-2026-01"
    assert tx.remittance_info == "Gehalt Januar 2026"


# --- pain.001 ---------------------------------------------------------------

def test_pain001_parses_two_transfers():
    txs = parse(PAIN001.read_bytes())
    assert len(txs) == 2
    assert all(tx.source_format == "pain.001" for tx in txs)
    assert all(tx.credit_debit == "DBIT" for tx in txs)


def test_pain001_first_transfer_fields():
    txs = parse(PAIN001.read_bytes())
    miete = txs[0]
    assert miete.statement_id == "SEPA-CT-20260115-0001"
    assert miete.account_iban == "DE89370400440532013000"
    assert miete.account_currency == "EUR"
    assert miete.value_date == "2026-01-16"
    assert miete.amount == "250.00"
    assert miete.currency == "EUR"
    assert miete.counterparty_name == "Hausverwaltung GmbH"
    assert miete.counterparty_iban == "DE02300209000106531065"
    assert miete.counterparty_bic == "INGDDEFFXXX"
    assert miete.end_to_end_id == "MIETE-2026-01"
    assert miete.remittance_info == "Miete Januar 2026"
    assert miete.bank_tx_code == "SEPA"


def test_pain001_second_transfer_has_no_creditor_bic():
    txs = parse(PAIN001.read_bytes())
    taschengeld = txs[1]
    assert taschengeld.counterparty_name == "Anna Mustermann"
    assert taschengeld.counterparty_bic == ""
    assert taschengeld.amount == "25.50"


# --- pain.008 ---------------------------------------------------------------

def test_pain008_parses_one_direct_debit():
    txs = parse(PAIN008.read_bytes())
    assert len(txs) == 1
    tx = txs[0]
    assert tx.source_format == "pain.008"
    assert tx.statement_id == "SEPA-DD-20260115-0001"
    assert tx.account_iban == "DE02300209000106531065"
    assert tx.value_date == "2026-02-01"
    assert tx.amount == "12.99"
    assert tx.credit_debit == "CRDT"
    assert tx.counterparty_name == "Max Mustermann"
    assert tx.counterparty_iban == "DE89370400440532013000"
    assert tx.counterparty_bic == "INGDDEFFXXX"
    assert tx.mandate_id == "MNDT-4711"
    assert tx.creditor_id == "DE98ZZZ09999999999"
    assert tx.end_to_end_id == "MITGLIED-2026-Q1"
    assert tx.bank_tx_code == "SEPA/RCUR"


# --- CSV --------------------------------------------------------------------

def test_csv_header_includes_source_format():
    csv_data = to_csv_string([], delimiter=";")
    assert csv_data.strip() == ";".join(CSV_FIELDS)
    assert "source_format" in CSV_FIELDS


def test_csv_round_trip_mixed_formats():
    txs = (
        parse(CAMT054.read_bytes())
        + parse(PAIN001.read_bytes())
        + parse(PAIN008.read_bytes())
    )
    csv_data = to_csv_string(txs, delimiter=";")
    lines = csv_data.strip().splitlines()
    assert len(lines) == 1 + 2 + 2 + 1  # header + camt + pain001 + pain008
    assert lines[0].startswith("source_format;")
    assert "camt.054" in lines[1]
    assert "pain.001" in lines[3]
    assert "pain.008" in lines[5]
