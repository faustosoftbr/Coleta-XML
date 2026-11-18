from pathlib import Path
from typing import List, Dict, Any

try:
    # openpyxl may not be installed; ensure it's available in the environment.
    from openpyxl import load_workbook, Workbook
except ImportError as e:
    raise ImportError("openpyxl is required for Excel report generation. Install it via 'pip install openpyxl'.")


def generate_excel_report(
    notes: List[Dict[str, Any]],
    template_path: Path,
    output_path: Path,
    header_title: str = "Data de Autorização",
) -> None:
    """Generate an Excel report based on a user‑provided template.

    Parameters
    ----------
    notes: List[Dict[str, Any]]
        List of note dictionaries returned by the collector. Expected keys include
        ``numero``, ``serie``, ``modelo``, ``data_emissao_str``, ``data_autorizacao_str``,
        ``valor_total``, ``chave`` and ``emit_cnpj``.
    template_path: Path
        Path to the XLSX template supplied by the user.
    output_path: Path
        Destination directory where the generated Excel file will be saved. The file
        will be named ``Relatorio.xlsx`` inside this directory.
    header_title: str
        Column title for the authorization datetime. Defaults to the Portuguese
        label requested by the user.
    """
    # Load template workbook (preserve styles, formulas, etc.)
    wb: Workbook = load_workbook(filename=str(template_path))
    ws = wb.active  # Assume the first sheet is the target

    # Determine existing headers (first row). We'll append missing columns if needed.
    existing_headers = [cell.value for cell in next(ws.iter_rows(min_row=1, max_row=1))]

    # Desired columns (based on current txt report) – we will ensure they exist.
    desired_columns = [
        "NÚMERO",
        "SÉRIE",
        "MOD",
        "EMISSÃO",
        header_title,  # authorization column
        "VALOR (R$)",
        "CHAVE DE ACESSO",
        "CNPJ EMITENTE",
    ]

    # Append any missing columns to the header row.
    start_col = len(existing_headers) + 1
    for idx, col_name in enumerate(desired_columns, start=start_col):
        if col_name not in existing_headers:
            ws.cell(row=1, column=idx, value=col_name)

    # Map header name to column index for later writes.
    header_to_col = {cell.value: idx + 1 for idx, cell in enumerate(next(ws.iter_rows(min_row=1, max_row=1)))}

    # Start writing data after the header row.
    row_idx = ws.max_row + 1
    for note in notes:
        # Prepare values respecting the order defined in ``desired_columns``.
        row_values = {
            "NÚMERO": note.get("numero", ""),
            "SÉRIE": note.get("serie", ""),
            "MOD": note.get("modelo", ""),
            "EMISSÃO": note.get("data_emissao_str", "").split(" ")[0],  # keep date part
            header_title: note.get("data_autorizacao_str", ""),
            "VALOR (R$)": f"{note.get('valor_total', 0.0):,.2f}".replace(",", "X").replace(".", ",").replace("X", "."),
            "CHAVE DE ACESSO": note.get("chave", ""),
            "CNPJ EMITENTE": note.get("emit_cnpj", ""),
        }
        for col_name, value in row_values.items():
            col_idx = header_to_col.get(col_name)
            if col_idx is not None:
                ws.cell(row=row_idx, column=col_idx, value=value)
        row_idx += 1

    # Ensure output directory exists.
    output_path.mkdir(parents=True, exist_ok=True)
    output_file = output_path / "Relatorio.xlsx"
    wb.save(str(output_file))
