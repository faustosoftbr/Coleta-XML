from collections import Counter
from pathlib import Path
from typing import List, Dict, Any

from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment, Border, Side
from openpyxl.utils import get_column_letter


XML_HEADERS = [
    "CNPJ Emitente",
    "Razão Social Emitente",
    "Tipo Documento",
    "Modelo",
    "Número",
    "Série",
    "Data Emissão",
    "Hora Emissão",
    "Data Autorização",
    "Hora Autorização",
    "Chave de Acesso",
    "Protocolo",
    "Status",
    "Código Status",
    "Motivo",
    "CPF/CNPJ Destinatário",
    "Nome Destinatário",
    "Valor Total",
    "Valor Produtos",
    "Valor ICMS",
    "Base ICMS",
    "Desconto",
    "ICMS Desonerado (vICMSDeson)",
    "Frete",
    "Tipo Emissão",
    "Ambiente",
    "Origem",
    "Nome do Arquivo",
    "Observações",
]

QUEBRAS_HEADERS = [
    "CNPJ Emitente",
    "Tipo Documento",
    "Série",
    "Número Inicial",
    "Número Final",
    "Número Faltante",
    "Quantidade de Quebras",
    "Observação",
]


def _style_header_row(ws, num_cols: int) -> None:
    header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
    header_font = Font(color="FFFFFF", bold=True, size=10)
    thin = Side(border_style="thin", color="D9D9D9")
    border = Border(left=thin, right=thin, top=thin, bottom=thin)

    ws.row_dimensions[1].height = 24
    for col_idx in range(1, num_cols + 1):
        cell = ws.cell(row=1, column=col_idx)
        cell.fill = header_fill
        cell.font = header_font
        cell.alignment = Alignment(horizontal="center", vertical="center")
        cell.border = border
    ws.freeze_panes = "A2"


def _auto_fit_columns(ws, max_width: int = 48) -> None:
    for col_cells in ws.columns:
        col_letter = get_column_letter(col_cells[0].column)
        max_len = 0
        for cell in col_cells[:200]:  # amostra rápida para planilhas grandes
            val_str = str(cell.value) if cell.value is not None else ""
            if len(val_str) > max_len:
                max_len = len(val_str)
        ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), max_width)


def _modelo_to_tipo_doc(modelo: str) -> str:
    if modelo == "55":
        return "NF-e"
    if modelo == "65":
        return "NFC-e"
    return modelo or ""


def generate_excel_report(
    notes: List[Dict[str, Any]],
    inut_records: List[Dict[str, Any]],
    audit_list: List[Dict[str, Any]],
    output_file: Path,
    total_xml_read: int = 0,
    duplicates_removed: int = 0,
) -> Path:
    """
    Gera o relatório Excel (.xlsx) no modelo de 3 abas: 'XMLs', 'Quebras' e 'Resumo',
    incluindo as colunas 'Data Autorização' e 'Hora Autorização' na aba 'XMLs'.
    """
    wb = Workbook()

    # ------------------------------------------------------------------
    # 1. ABA "XMLs"
    # ------------------------------------------------------------------
    ws_xmls = wb.active
    ws_xmls.title = "XMLs"
    ws_xmls.append(XML_HEADERS)
    _style_header_row(ws_xmls, len(XML_HEADERS))

    # Ordena notas por série e número
    sorted_notes = sorted(
        notes,
        key=lambda n: (n.get("emit_cnpj", ""), n.get("modelo", ""), str(n.get("serie", "")), int(n.get("numero", 0))),
    )

    total_docs = 0
    total_autorizados = 0
    total_cancelados = 0
    soma_autorizados = 0.0
    soma_cancelados = 0.0
    soma_desonerado = 0.0
    soma_geral = 0.0

    status_counter: Counter = Counter()
    tipo_doc_counter: Counter = Counter()
    cnpj_counter: Counter = Counter()
    origem_counter: Counter = Counter()

    text_cols = {1, 4, 9, 10, 11, 12, 14, 16}  # mantém CNPJs, chaves, datas/horas como texto
    money_cols = {18, 19, 20, 21, 22, 23, 24}

    row_idx = 2
    for n in sorted_notes:
        tipo_doc = _modelo_to_tipo_doc(n.get("modelo", ""))
        status = n.get("status", "AUTORIZADA")
        v_total = float(n.get("valor_total", 0.0) or 0.0)
        v_deson = float(n.get("icms_desonerado", 0.0) or 0.0)
        origem = n.get("origem", "") or "Local"
        fname = n["path"].name if isinstance(n.get("path"), Path) else str(n.get("filename", ""))

        row_data = [
            n.get("emit_cnpj", ""),
            n.get("emit_nome", ""),
            tipo_doc,
            n.get("modelo", ""),
            n.get("numero", 0),
            int(n["serie"]) if str(n.get("serie", "")).isdigit() else n.get("serie", ""),
            n.get("data_emissao_only_str") or n.get("data_emissao_str", "").split(" ")[0],
            n.get("hora_emissao_str", ""),
            n.get("data_autorizacao_only_str") or n.get("data_autorizacao_str", "").split(" ")[0],
            n.get("hora_autorizacao_str", ""),
            n.get("chave", ""),
            n.get("protocolo", ""),
            status,
            n.get("codigo_status", ""),
            n.get("motivo", ""),
            n.get("dest_doc", ""),
            n.get("dest_nome", ""),
            v_total,
            float(n.get("valor_produtos", 0.0) or 0.0),
            float(n.get("valor_icms", 0.0) or 0.0),
            float(n.get("base_icms", 0.0) or 0.0),
            float(n.get("desconto", 0.0) or 0.0),
            v_deson,
            float(n.get("frete", 0.0) or 0.0),
            n.get("tipo_emissao", "NORMAL"),
            n.get("ambiente", ""),
            origem,
            fname,
            n.get("observacoes", ""),
        ]
        ws_xmls.append(row_data)

        for col_i in text_cols:
            ws_xmls.cell(row=row_idx, column=col_i).number_format = "@"
        for col_i in money_cols:
            ws_xmls.cell(row=row_idx, column=col_i).number_format = "#,##0.00"

        row_idx += 1

        total_docs += 1
        if status == "CANCELADA":
            total_cancelados += 1
            soma_cancelados += v_total
        else:
            soma_geral += v_total
            soma_desonerado += v_deson
            if status == "AUTORIZADA":
                total_autorizados += 1
                soma_autorizados += v_total

        status_counter[status] += 1
        tipo_doc_counter[tipo_doc] += 1
        cnpj_counter[n.get("emit_cnpj", "")] += 1
        origem_counter[origem] += 1

    # Inutilizações também entram no totalizador e na aba XMLs como INUTILIZAÇÃO
    for inut in inut_records:
        origem = inut.get("origem", "") or "Local"
        faixa_num = f"{inut.get('nnf_ini', '')}-{inut.get('nnf_fin', '')}" if inut.get("nnf_ini") != inut.get("nnf_fin") else inut.get("nnf_ini", "")
        fname = inut.get("filename", "")
        row_data = [
            inut.get("emit_cnpj", ""),
            "",
            "INUTILIZAÇÃO",
            inut.get("modelo", ""),
            faixa_num,
            int(inut["serie"]) if str(inut.get("serie", "")).isdigit() else inut.get("serie", ""),
            "",
            "",
            "",
            "",
            "",
            "",
            "INUTILIZADA",
            "",
            inut.get("motivo", ""),
            "",
            "",
            0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0,
            "",
            "",
            origem,
            fname,
            inut.get("justificativa", ""),
        ]
        ws_xmls.append(row_data)
        for col_i in text_cols:
            ws_xmls.cell(row=row_idx, column=col_i).number_format = "@"
        row_idx += 1

        total_docs += 1
        status_counter["INUTILIZADA"] += 1
        tipo_doc_counter["INUTILIZAÇÃO"] += 1
        cnpj_counter[inut.get("emit_cnpj", "")] += 1
        origem_counter[origem] += 1

    # Linhas de totalizadores no rodapé da aba XMLs (conforme modelo)
    ws_xmls.append([])
    bold_font = Font(bold=True)
    summary_footer = [
        ("Quantidade total de documentos", total_docs, False),
        ("Total de documentos autorizados", total_autorizados, False),
        ("Total de documentos cancelados", total_cancelados, False),
        ("Soma total dos valores autorizados", soma_autorizados, True),
        ("Valor total desonerado", soma_desonerado, True),
        ("Valor final (autorizado − desonerado)", soma_autorizados - soma_desonerado, True),
        ("Soma total geral", soma_geral, True),
    ]
    for label, val, is_money in summary_footer:
        r = ws_xmls.max_row + 1
        c1 = ws_xmls.cell(row=r, column=1, value=label)
        c2 = ws_xmls.cell(row=r, column=2, value=val)
        c1.font = bold_font
        c2.font = bold_font
        if is_money:
            c2.number_format = "#,##0.00"

    _auto_fit_columns(ws_xmls)

    # ------------------------------------------------------------------
    # 2. ABA "Quebras"
    # ------------------------------------------------------------------
    ws_quebras = wb.create_sheet(title="Quebras")
    ws_quebras.append(QUEBRAS_HEADERS)
    _style_header_row(ws_quebras, len(QUEBRAS_HEADERS))

    quebras_reais = [a for a in audit_list if a.get("tem_quebra")]
    for a in quebras_reais:
        faltantes = a.get("numeros_faltantes", [])
        faltantes_str = a.get("resumo_faltantes") or ", ".join(str(x) for x in faltantes)
        obs = ""
        if a.get("teve_inutilizacao"):
            obs = f"{a.get('qtd_inutilizados', 0)} número(s) cobertos por inutilização"
        ws_quebras.append([
            a.get("cnpj", ""),
            a.get("modelo_nome", ""),
            int(a["serie"]) if str(a.get("serie", "")).isdigit() else a.get("serie", ""),
            a.get("primeiro_numero", 0),
            a.get("ultimo_numero", 0),
            faltantes_str,
            a.get("qtd_faltantes_reais", len(faltantes)),
            obs,
        ])
        r = ws_quebras.max_row
        ws_quebras.cell(row=r, column=1).number_format = "@"
        ws_quebras.cell(row=r, column=6).number_format = "@"

    _auto_fit_columns(ws_quebras)

    # ------------------------------------------------------------------
    # 3. ABA "Resumo"
    # ------------------------------------------------------------------
    ws_resumo = wb.create_sheet(title="Resumo")
    ws_resumo.append(["Métrica", "Valor"])
    _style_header_row(ws_resumo, 2)

    xml_lidos = total_xml_read if total_xml_read > 0 else total_docs
    resumo_rows = [
        ("Total de XML lidos", xml_lidos, False),
        ("Total válidos", total_docs, False),
        ("Total duplicados removidos", duplicates_removed, False),
        ("Total de séries", len(audit_list), False),
        ("Total de quebras encontradas", len(quebras_reais), False),
        ("Valor total autorizado", soma_autorizados, True),
        ("Valor total desonerado", soma_desonerado, True),
        ("Valor final (autorizado − desonerado)", soma_autorizados - soma_desonerado, True),
        ("Valor total cancelado", soma_cancelados, True),
    ]

    for label, val, is_money in resumo_rows:
        r = ws_resumo.max_row + 1
        ws_resumo.cell(row=r, column=1, value=label)
        c2 = ws_resumo.cell(row=r, column=2, value=val)
        if is_money:
            c2.number_format = "#,##0.00"

    def _add_breakdown(title: str, counter: Counter):
        ws_resumo.append([])
        r_title = ws_resumo.max_row + 1
        c = ws_resumo.cell(row=r_title, column=1, value=title)
        c.font = bold_font
        for k, v in counter.items():
            r_item = ws_resumo.max_row + 1
            c_k = ws_resumo.cell(row=r_item, column=1, value=str(k))
            c_k.number_format = "@"
            ws_resumo.cell(row=r_item, column=2, value=v)

    _add_breakdown("Total por status", status_counter)
    _add_breakdown("Total por tipo de documento", tipo_doc_counter)
    _add_breakdown("Total por CNPJ emitente", cnpj_counter)
    _add_breakdown("Total por origem", origem_counter)

    ws_resumo.append([])
    r_obs = ws_resumo.max_row + 1
    ws_resumo.cell(row=r_obs, column=1, value="Observações gerais").font = bold_font
    obs_text = (
        f'{len(quebras_reais)} quebra(s) de sequência numérica identificada(s) — ver aba "Quebras" para detalhes.'
        if quebras_reais
        else "Nenhuma quebra de sequência numérica identificada."
    )
    ws_resumo.cell(row=r_obs + 1, column=1, value=obs_text)

    _auto_fit_columns(ws_resumo, max_width=70)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    wb.save(str(output_file))
    return output_file
