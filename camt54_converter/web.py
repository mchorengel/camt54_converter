"""Tiny Flask web app for camt.054 → CSV conversion."""

from __future__ import annotations

from pathlib import Path

from flask import Flask, Response, render_template, request

from camt54_converter.parser import parse_camt054, to_csv_string


MAX_UPLOAD_BYTES = 16 * 1024 * 1024  # 16 MB


def create_app() -> Flask:
    app = Flask(
        __name__,
        template_folder=str(Path(__file__).resolve().parent.parent / "templates"),
    )
    app.config["MAX_CONTENT_LENGTH"] = MAX_UPLOAD_BYTES

    @app.get("/")
    def index() -> str:
        return render_template("index.html")

    @app.post("/convert")
    def convert() -> Response:
        uploads = request.files.getlist("file")
        uploads = [f for f in uploads if f and f.filename]
        if not uploads:
            return render_template(
                "index.html", error="Bitte mindestens eine camt.054-Datei auswählen."
            ), 400

        delimiter = request.form.get("delimiter", ";")
        if delimiter not in (";", ",", "\t", "|"):
            delimiter = ";"

        all_tx = []
        try:
            for upload in uploads:
                data = upload.read()
                all_tx.extend(parse_camt054(data))
        except ValueError as exc:
            return render_template("index.html", error=str(exc)), 400
        except Exception as exc:  # noqa: BLE001 — surface parser errors to UI
            return render_template(
                "index.html", error=f"Fehler beim Parsen: {exc}"
            ), 400

        csv_data = to_csv_string(all_tx, delimiter=delimiter)
        download_name = (
            Path(uploads[0].filename).stem + ".csv" if len(uploads) == 1 else "camt054.csv"
        )
        return Response(
            csv_data,
            mimetype="text/csv; charset=utf-8",
            headers={
                "Content-Disposition": f'attachment; filename="{download_name}"',
            },
        )

    return app


app = create_app()


def main() -> None:
    import argparse

    parser = argparse.ArgumentParser(description="Run the camt.054 web converter.")
    parser.add_argument("--host", default="127.0.0.1")
    parser.add_argument("--port", type=int, default=5000)
    parser.add_argument("--debug", action="store_true")
    args = parser.parse_args()
    app.run(host=args.host, port=args.port, debug=args.debug)


if __name__ == "__main__":
    main()
