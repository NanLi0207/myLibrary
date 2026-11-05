import marimo

__generated_with = "0.25.2"
app = marimo.App(width="full")


@app.cell
def _():
    import csv
    import re
    from pathlib import Path

    import marimo as mo

    ROOT = Path(__file__).resolve().parent.parent
    return Path, ROOT, csv, mo, re


@app.cell
def _(ROOT, csv, re):
    def progress(slug: str) -> str:
        """Chapters ticked off in notes/<slug>/README.md, e.g. '3/12'."""
        readme = ROOT / "notes" / slug / "README.md"
        if not readme.exists():
            return ""
        text = readme.read_text(encoding="utf-8")
        done = len(re.findall(r"^- \[x\]", text, re.MULTILINE | re.IGNORECASE))
        total = done + len(re.findall(r"^- \[ \]", text, re.MULTILINE))
        return f"{done}/{total}"

    catalog_file = ROOT / "catalog.csv"
    if catalog_file.exists():
        with catalog_file.open(newline="", encoding="utf-8-sig") as f:
            books = [row | {"progress": progress(row["slug"])} for row in csv.DictReader(f)]
    else:
        books = []
    return (books,)


@app.cell
def _(mo):
    query = mo.ui.text(
        placeholder="title, author, ISBN, subject, year…", label="Search", full_width=True
    )
    query
    return (query,)


@app.cell
def _(books, mo, query):
    words = query.value.lower().split()
    shown = [b for b in books if all(w in " ".join(b.values()).lower() for w in words)]
    columns = [
        "title",
        "authors",
        "year",
        "publisher",
        "isbn",
        "pages",
        "chapters",
        "progress",
        "subjects",
        "file",
    ]
    mo.vstack(
        [
            mo.md(f"**{len(shown)}** of {len(books)} books"),
            mo.ui.table([{c: b.get(c, "") for c in columns} for b in shown], page_size=25),
        ]
    )
    return


if __name__ == "__main__":
    app.run()
