"""Tests for the camt.054 parser."""

from pathlib import Path

import pytest

from camt54_converter.parser import parse_camt054, to_csv_string, CSV_FIELDS


SAMPLE = Path(__file__).parent / "sample_camt054.xml"


@pytest.fixture
def transactions():
    return parse_camt054(SAMPLE.read_bytes())


def test_parses_two_transactions(transactions):
    assert len(transactions) == 2


def test_credit_transaction_fields(transactions):
    credit = transactions[0]
    assert credit.statement_id == "NTF-20260115-0001"
    assert credit.account_iban == "DE89370400440532013000"
    assert credit.account_currency == "EUR"
    assert credit.credit_debit == "CRDT"
    assert credit.amount == "150.75"
    assert credit.currency == "EUR"
    assert credit.booking_date == "2026-01-14"
    assert credit.value_date == "2026-01-14"
    assert credit.counterparty_name == "Max Mustermann GmbH"
    assert credit.counterparty_iban == "DE12500105170648489890"
    assert credit.counterparty_bic == "INGDDEFFXXX"
    assert credit.end_to_end_id == "RECHNUNG-2026-001"
    assert credit.remittance_info == "Zahlung Rechnung 2026-001"
    assert credit.bank_tx_code == "PMNT/RCDT/ESCT"


def test_debit_transaction_fields(transactions):
    debit = transactions[1]
    assert debit.credit_debit == "DBIT"
    assert debit.amount == "42.00"
    assert debit.counterparty_name == "Stadtwerke Beispielheim"
    assert debit.counterparty_iban == "DE02300209000106531065"
    assert debit.counterparty_bic == "CMCIDEDDXXX"
    assert debit.mandate_id == "MANDAT-12345"
    assert debit.creditor_id == "DE98ZZZ09999999999"
    assert debit.additional_info == "Lastschrift Strom"
    assert "Stromabschlag" in debit.remittance_info


def test_csv_round_trip(transactions):
    csv_data = to_csv_string(transactions, delimiter=";")
    lines = csv_data.strip().splitlines()
    assert lines[0] == ";".join(CSV_FIELDS)
    assert len(lines) == 3  # header + 2 rows
    assert "Max Mustermann GmbH" in lines[1]
    assert "Stadtwerke Beispielheim" in lines[2]


def test_rejects_non_iso20022_document():
    with pytest.raises(ValueError, match="ISO 20022"):
        parse_camt054(b"<foo/>")


def test_rejects_iso20022_without_notification():
    xml = (
        b'<Document xmlns="urn:iso:std:iso:20022:tech:xsd:camt.054.001.02">'
        b"<Other/></Document>"
    )
    with pytest.raises(ValueError, match="Ntfctn"):
        parse_camt054(xml)


def test_parses_namespace_variants():
    xml = SAMPLE.read_text().replace(
        "camt.054.001.02", "camt.054.001.08"
    )
    txs = parse_camt054(xml.encode("utf-8"))
    assert len(txs) == 2
