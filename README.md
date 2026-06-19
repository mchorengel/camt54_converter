# camt54_converter

Konvertiert **ISO-20022-XML-Dateien** nach **CSV** — als Kommandozeilen-Tool **und**
als Mini-Webanwendung. Das Quellformat wird automatisch am Document-Root erkannt.

| Format    | ISO-20022-Name                                | Inhalt                                |
| --------- | --------------------------------------------- | ------------------------------------- |
| camt.054  | Bank-to-Customer Debit/Credit Notification    | Bank-Avise (Eingänge/Ausgänge)        |
| camt.053  | Bank-to-Customer Statement                    | Tages-Kontoauszug                     |
| pain.001  | Customer Credit Transfer Initiation           | SEPA-Auftragsdatei: Überweisungen     |
| pain.008  | Customer Direct Debit Initiation              | SEPA-Auftragsdatei: Lastschriften     |

Der XML-Namespace wird ebenfalls automatisch erkannt — gängige Versionen
(`.001.02` bis `.001.08+`) funktionieren ohne Anpassung.

## Installation

Benötigt Python ≥ 3.10. Einzige externe Abhängigkeit ist `Flask` für die Webanwendung —
die CLI funktioniert auch ohne.

### Linux / macOS

```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# oder als Paket installieren:
pip install .
```

### Windows

Im Repo-Ordner liegen zwei Setup-Scripts, die `.venv` anlegen, aktivieren und
die Abhängigkeiten installieren:

**CMD (cmd.exe)** — mit `call` aufrufen, damit das venv aktiv bleibt:

```bat
call setup.bat
```

**PowerShell** — mit Punkt-Leerzeichen (dot-sourcen) aufrufen:

```powershell
. .\setup.ps1
```

Falls PowerShell das Ausführen von Scripts verweigert, einmalig erlauben mit:

```powershell
Set-ExecutionPolicy -Scope CurrentUser -ExecutionPolicy RemoteSigned
```

Bei späteren Sessions reicht es, das venv direkt zu aktivieren:

```bat
.venv\Scripts\activate.bat        :: CMD
.\.venv\Scripts\Activate.ps1      # PowerShell
```

## Kommandozeile

```bash
# Eine Datei in eine CSV umwandeln (Trennzeichen ";" als Default)
python -m camt54_converter.cli avis.xml -o avis.csv

# Mehrere Dateien zusammenführen — Formate dürfen gemischt werden
python -m camt54_converter.cli camt054/*.xml pain001/*.xml -o alles.csv

# Auf stdout ausgeben, mit Komma als Trennzeichen
python -m camt54_converter.cli avis.xml -d ,

# Aus stdin lesen
cat avis.xml | python -m camt54_converter.cli -

# Wenn als Paket installiert:
camt54-to-csv avis.xml -o avis.csv
```

### Windows: Drag & Drop

Im Repo-Ordner liegt `convert.bat`. Eine oder mehrere ISO-20022-XML-Dateien
einfach mit der Maus auf diese Datei ziehen — neben jeder XML-Datei wird
eine CSV mit gleichem Namen erzeugt. Voraussetzung: einmalig
`call setup.bat` ausführen, damit `.venv` existiert.

### Optionen

| Flag                | Bedeutung                                                |
| ------------------- | -------------------------------------------------------- |
| `input`             | Pfade zu ISO-20022-XML-Dateien (oder `-` für stdin)      |
| `-o`, `--output`    | Ziel-CSV-Datei (Default: stdout)                         |
| `-d`, `--delimiter` | Spaltentrennzeichen (Default: `;`)                       |
| `--encoding`        | Ausgabe-Kodierung (Default: `utf-8`)                     |

## Webanwendung

```bash
python -m camt54_converter.web
# oder, wenn installiert:
camt54-web --host 0.0.0.0 --port 5000
```

Im Browser <http://127.0.0.1:5000> öffnen, eine oder mehrere XML-Dateien
hochladen (Formate dürfen gemischt sein), Trennzeichen wählen — und die
CSV wird direkt zurückgegeben.

## CSV-Spalten

Die Spalten sind über alle vier Formate identisch; nicht zutreffende Felder
bleiben leer (z. B. hat eine pain.001-Auftragsdatei kein `booking_date`).
Die erste Spalte `source_format` zeigt, aus welchem Format eine Zeile stammt.

| Spalte               | camt.054 / camt.053                              | pain.001                          | pain.008                                |
| -------------------- | ------------------------------------------------ | --------------------------------- | --------------------------------------- |
| `source_format`      | `camt.054` / `camt.053`                          | `pain.001`                        | `pain.008`                              |
| `statement_id`       | `Ntfctn/Id` bzw. `Stmt/Id`                       | `GrpHdr/MsgId`                    | `GrpHdr/MsgId`                          |
| `account_iban`       | Konto-IBAN                                       | `Dbtr`-IBAN (Auftraggeber)        | `Cdtr`-IBAN (Auftraggeber)              |
| `account_currency`   | `Acct/Ccy`                                       | `DbtrAcct/Ccy`                    | `CdtrAcct/Ccy`                          |
| `booking_date`       | `Ntry/BookgDt/Dt`                                | —                                 | —                                       |
| `value_date`         | `Ntry/ValDt/Dt`                                  | `ReqdExctnDt`                     | `ReqdColltnDt`                          |
| `amount` / `currency`| `TxDtls/Amt` (fallback `Ntry/Amt`)               | `Amt/InstdAmt`                    | `InstdAmt`                              |
| `credit_debit`       | `CRDT` / `DBIT`                                  | `DBIT` (Auftraggebersicht)        | `CRDT` (Auftraggebersicht)              |
| `status`             | `Ntry/Sts`                                       | —                                 | —                                       |
| `bank_tx_code`       | `BkTxCd/Domn/...` + `Prtry/Cd`                   | `PmtTpInf/SvcLvl/Cd` (z. B. SEPA) | `SvcLvl/Cd` + `SeqTp` (z. B. SEPA/RCUR) |
| `end_to_end_id`      | `TxDtls/Refs/EndToEndId`                         | `PmtId/EndToEndId`                | `PmtId/EndToEndId`                      |
| `mandate_id`         | `TxDtls/Refs/MndtId`                             | —                                 | `MndtRltdInf/MndtId`                    |
| `creditor_id`        | `RltdPties/Cdtr/Id/...`                          | —                                 | `CdtrSchmeId/Id/...`                    |
| `counterparty_name`  | Bei `CRDT`: `Dbtr/Nm`, bei `DBIT`: `Cdtr/Nm`     | `Cdtr/Nm`                         | `Dbtr/Nm`                               |
| `counterparty_iban`  | Konto der Gegenpartei                            | `CdtrAcct`-IBAN                   | `DbtrAcct`-IBAN                         |
| `counterparty_bic`   | `RltdAgts/.../FinInstnId/BIC`                    | `CdtrAgt/FinInstnId/BIC`          | `DbtrAgt/FinInstnId/BIC`                |
| `remittance_info`    | `RmtInf/Ustrd` + `RmtInf/Strd/...`               | dito                              | dito                                    |
| `additional_info`    | `Ntry/AddtlNtryInf` + `TxDtls/AddtlTxInf`        | Auftraggeber-Name + `PmtInfId`    | Auftraggeber-Name + `PmtInfId`          |

## Als Bibliothek

```python
from camt54_converter import parse, write_csv, detect_format

with open("datei.xml", "rb") as fh:
    data = fh.read()

print(detect_format(data))   # 'camt.054' / 'camt.053' / 'pain.001' / 'pain.008'
txs = parse(data)            # automatische Format-Erkennung

with open("ausgabe.csv", "w", encoding="utf-8", newline="") as out:
    write_csv(txs, out, delimiter=";")
```

Wer ausdrücklich nur camt.054 akzeptieren möchte, kann weiterhin
`parse_camt054()` verwenden — andere Formate werden mit einem klaren Fehler
abgelehnt.
