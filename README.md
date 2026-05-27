# camt54_converter

Konvertiert **camt.054** (ISO 20022 *Bank-to-Customer Debit/Credit Notification*)
XML-Dateien nach **CSV** — als Kommandozeilen-Tool **und** als Mini-Webanwendung.

Unterstützt die gängigen camt.054-Varianten (`camt.054.001.02` bis
`camt.054.001.08+`); der XML-Namespace wird automatisch erkannt.

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

# Mehrere Dateien zusammenführen
python -m camt54_converter.cli jan/*.xml -o januar.csv

# Auf stdout ausgeben, mit Komma als Trennzeichen
python -m camt54_converter.cli avis.xml -d ,

# Aus stdin lesen
cat avis.xml | python -m camt54_converter.cli -

# Wenn als Paket installiert:
camt54-to-csv avis.xml -o avis.csv
```

### Windows: Drag & Drop

Im Repo-Ordner liegt `convert.bat`. Eine oder mehrere camt.054-XML-Dateien
einfach mit der Maus auf diese Datei ziehen — neben jeder XML-Datei wird
eine CSV mit gleichem Namen erzeugt. Voraussetzung: einmalig
`call setup.bat` ausführen, damit `.venv` existiert.

### Optionen

| Flag                | Bedeutung                                                |
| ------------------- | -------------------------------------------------------- |
| `input`             | Pfade zu camt.054-XML-Dateien (oder `-` für stdin)       |
| `-o`, `--output`    | Ziel-CSV-Datei (Default: stdout)                         |
| `-d`, `--delimiter` | Spaltentrennzeichen (Default: `;`)                       |
| `--encoding`        | Ausgabe-Kodierung (Default: `utf-8`)                     |

## Webanwendung

```bash
python -m camt54_converter.web
# oder, wenn installiert:
camt54-web --host 0.0.0.0 --port 5000
```

Anschließend im Browser <http://127.0.0.1:5000> öffnen, eine oder mehrere
camt.054-Dateien hochladen, Trennzeichen wählen — und die CSV wird direkt
zurückgegeben.

## CSV-Spalten

Jede Zeile entspricht einer Transaktion (`TxDtls`); enthält eine Buchung
keine Details, wird der Eintrag (`Ntry`) selbst als Zeile abgebildet.

| Spalte                | Quelle in camt.054                                                  |
| --------------------- | ------------------------------------------------------------------- |
| `statement_id`        | `Ntfctn/Id`                                                         |
| `account_iban`        | `Ntfctn/Acct/Id/IBAN` (oder `Othr/Id`)                              |
| `account_currency`    | `Ntfctn/Acct/Ccy`                                                   |
| `booking_date`        | `Ntry/BookgDt/Dt`                                                   |
| `value_date`          | `Ntry/ValDt/Dt`                                                     |
| `amount`              | `TxDtls/Amt` (fallback `Ntry/Amt`)                                  |
| `currency`            | Attribut `Ccy` des Betrags                                          |
| `credit_debit`        | `CRDT` / `DBIT`                                                     |
| `reversal`            | `RvslInd`                                                           |
| `status`              | `Ntry/Sts`                                                          |
| `bank_tx_code`        | `BkTxCd/Domn/Cd` `/Fmly/Cd` `/SubFmlyCd` + `Prtry/Cd`               |
| `end_to_end_id`       | `TxDtls/Refs/EndToEndId`                                            |
| `mandate_id`          | `TxDtls/Refs/MndtId`                                                |
| `creditor_id`         | `RltdPties/Cdtr/Id/PrvtId|OrgId/Othr/Id`                            |
| `counterparty_name`   | Bei `CRDT`: `Dbtr/Nm`, bei `DBIT`: `Cdtr/Nm`                        |
| `counterparty_iban`   | Konto der Gegenpartei                                               |
| `counterparty_bic`    | `RltdAgts/.../FinInstnId/BIC` (oder `BICFI`)                        |
| `remittance_info`     | `RmtInf/Ustrd` + `RmtInf/Strd/...`                                  |
| `additional_info`     | `Ntry/AddtlNtryInf` + `TxDtls/AddtlTxInf`                           |

## Als Bibliothek

```python
from camt54_converter import parse_camt054, write_csv

with open("avis.xml", "rb") as fh:
    txs = parse_camt054(fh)

with open("avis.csv", "w", encoding="utf-8", newline="") as out:
    write_csv(txs, out, delimiter=";")
```
