import os
import re
import xml.etree.ElementTree as ET
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, Any, Tuple


def to_long_path(file_path: Path) -> str:
    """No Windows, aplica prefixo \\\\?\\ para suportar caminhos acima de 260 caracteres."""
    path_str = str(file_path)
    if os.name != "nt":
        return path_str
    abs_path = os.path.abspath(path_str)
    if abs_path.startswith("\\\\?\\"):
        return abs_path
    if abs_path.startswith("\\\\"):
        return "\\\\?\\UNC\\" + abs_path[2:]
    return "\\\\?\\" + abs_path

KEY_REGEX = re.compile(r"(\d{44})")
VNF_REGEX = re.compile(r"<vNF>([^<]+)</vNF>")
XNOME_EMIT_REGEX = re.compile(r"<emit>.*?<xNome>([^<]+)</xNome>", re.DOTALL)
DHEMI_REGEX = re.compile(r"<(?:dhEmi|dEmi)>([^<]+)</(?:dhEmi|dEmi)>")
DHRECBTO_REGEX = re.compile(r"<dhRecbto>([^<]+)</dhRecbto>")

def clean_digits(value: Optional[str]) -> str:
    """Remove caracteres não numéricos."""
    if not value:
        return ""
    return re.sub(r"\D", "", value)

def extract_key_from_filename(filename: str) -> Optional[str]:
    """Extrai a chave de 44 dígitos a partir do nome do arquivo."""
    match = KEY_REGEX.search(filename)
    if match:
        return match.group(1)
    return None

def parse_iso_datetime_parts(dt_str: Optional[str]) -> Tuple[Optional[date], str, str, str, str, str]:
    """
    Analisa string de data ISO (ex: 2026-10-31T23:30:03-04:00 ou 2026-10-31).
    Retorna (date_obj, 'dd/mm/aaaa hh:mm', 'dd/mm/aaaa', 'HH:MM:SS', 'aaaa-mm', 'aamm')
    """
    if not dt_str:
        return None, "", "", "", "", ""
    dt_str = dt_str.strip()
    try:
        if "T" in dt_str:
            dt = datetime.fromisoformat(dt_str)
            d_obj = dt.date()
            fmt = dt.strftime("%d/%m/%Y %H:%M")
            d_only = dt.strftime("%d/%m/%Y")
            t_only = dt.strftime("%H:%M:%S")
            ano_mes = dt.strftime("%Y-%m")
            aamm = f"{str(dt.year)[-2:]}{dt.month:02d}"
            return d_obj, fmt, d_only, t_only, ano_mes, aamm
        elif len(dt_str) >= 10:
            partes = dt_str[:10].split("-")
            if len(partes) == 3:
                ano, mes, dia = int(partes[0]), int(partes[1]), int(partes[2])
                d_obj = date(ano, mes, dia)
                fmt = f"{dia:02d}/{mes:02d}/{ano:04d}"
                ano_mes = f"{ano:04d}-{mes:02d}"
                aamm = f"{str(ano)[-2:]}{mes:02d}"
                return d_obj, fmt, fmt, "", ano_mes, aamm
    except Exception:
        pass
    return None, "", "", "", "", ""


def parse_iso_datetime(dt_str: Optional[str]) -> Tuple[Optional[date], str, str, str]:
    """
    Analisa string de data ISO (ex: 2026-10-31T23:30:03-04:00 ou 2026-10-31).
    Retorna (date_obj, formatada_str 'dd/mm/aaaa hh:mm', ano_mes 'aaaa-mm', aamm 'aamm')
    """
    d_obj, fmt, _, _, ano_mes, aamm = parse_iso_datetime_parts(dt_str)
    return d_obj, fmt, ano_mes, aamm

def parse_key_metadata(key_44: str) -> Optional[Dict[str, Any]]:
    """
    Decodifica os dados fiscais a partir da chave de 44 dígitos da SEFAZ:
    • 2 dígitos: Código da UF
    • 4 dígitos: Ano e Mês de emissão (AAMM)
    • 14 dígitos: CNPJ do emitente
    • 2 dígitos: Modelo do documento (55 = NF-e, 65 = NFC-e)
    • 3 dígitos: Série do documento
    • 9 dígitos: Número do documento fiscal
    • 1 dígito: Tipo de emissão
    • 8 dígitos: Código numérico
    • 1 dígito: Dígito verificador
    """
    if not key_44 or len(key_44) != 44 or not key_44.isdigit():
        return None

    uf = key_44[0:2]
    aamm = key_44[2:6]
    cnpj = key_44[6:20]
    modelo = key_44[20:22]
    serie_raw = key_44[22:25]
    serie = str(int(serie_raw)) if serie_raw.isdigit() else serie_raw
    numero_raw = key_44[25:34]
    numero = int(numero_raw) if numero_raw.isdigit() else 0
    
    ano = "20" + aamm[0:2]
    mes = aamm[2:4]
    ano_mes = f"{ano}-{mes}"

    tp_emis = key_44[34:35]
    return {
        "tipo": "NFE",
        "chave": key_44,
        "uf": uf,
        "aamm": aamm,
        "ano": ano,
        "mes": mes,
        "ano_mes": ano_mes,
        "emit_cnpj": cnpj,
        "emit_nome": "",
        "modelo": modelo,
        "serie": serie,
        "numero": numero,
        "valor_total": 0.0,
        "valor_produtos": 0.0,
        "valor_icms": 0.0,
        "base_icms": 0.0,
        "desconto": 0.0,
        "icms_desonerado": 0.0,
        "frete": 0.0,
        "data_emissao_str": f"01/{mes}/{ano}",
        "data_emissao_only_str": f"01/{mes}/{ano}",
        "hora_emissao_str": "",
        "data_autorizacao_str": "",
        "data_autorizacao_only_str": "",
        "hora_autorizacao_str": "",
        "data_emissao_obj": None,
        "data_autorizacao_obj": None,
        "ano_mes_autorizacao": ano_mes,
        "protocolo": "",
        "status": "AUTORIZADA" if tp_emis == "1" else "CONTINGENCIA",
        "codigo_status": "",
        "motivo": "",
        "dest_doc": "",
        "dest_nome": "",
        "tipo_emissao": "NORMAL" if tp_emis == "1" else "CONTINGENCIA",
        "ambiente": "",
        "origem": "",
        "observacoes": "",
        "is_cancellation": False,
    }


def _find_child(element: Optional[ET.Element], local_tag: str) -> Optional[ET.Element]:
    if element is None:
        return None
    target = local_tag.lower()
    for child in element:
        tag_name = child.tag.split("}")[-1] if "}" in child.tag else child.tag
        if tag_name.lower() == target:
            return child
    return None


def _find_first(element: Optional[ET.Element], local_tag: str) -> Optional[ET.Element]:
    if element is None:
        return None
    target = local_tag.lower()
    for elem in element.iter():
        tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
        if tag_name.lower() == target:
            return elem
    return None


def _get_float(element: Optional[ET.Element], local_tag: str, default: float = 0.0) -> float:
    child = _find_child(element, local_tag)
    if child is not None and child.text:
        try:
            return float(child.text.strip().replace(",", "."))
        except ValueError:
            pass
    return default


def _get_text(element: Optional[ET.Element], local_tag: str, default: str = "") -> str:
    child = _find_child(element, local_tag)
    if child is not None and child.text:
        return child.text.strip()
    return default


def quick_read_xml_details(file_path: Path, note_data: Dict[str, Any]) -> None:
    """
    Lê os detalhes fiscais completos do XML (<vNF>, <xNome>, <dhEmi>, <dhRecbto>,
    protocolo, status, destinatário, totais, tipo de emissão e ambiente).
    """
    try:
        content = ""
        safe_path = to_long_path(file_path)
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                with open(safe_path, "r", encoding=enc) as f:
                    content = f.read()
                    break
            except UnicodeDecodeError:
                continue

        if not content:
            return

        parsed_ok = False
        try:
            root = ET.fromstring(content)
            inf_nfe = _find_first(root, "infNFe")
            ide = _find_child(inf_nfe, "ide")
            emit = _find_child(inf_nfe, "emit")
            dest = _find_child(inf_nfe, "dest")
            total = _find_child(inf_nfe, "total")
            icms_tot = _find_child(total, "ICMSTot")
            inf_prot = _find_first(root, "infProt")

            if emit is not None:
                xnome = _get_text(emit, "xNome")
                if xnome:
                    note_data["emit_nome"] = xnome

            if dest is not None:
                note_data["dest_doc"] = _get_text(dest, "CNPJ") or _get_text(dest, "CPF")
                note_data["dest_nome"] = _get_text(dest, "xNome")

            if icms_tot is not None:
                note_data["valor_total"] = _get_float(icms_tot, "vNF", note_data.get("valor_total", 0.0))
                note_data["valor_produtos"] = _get_float(icms_tot, "vProd", 0.0)
                note_data["valor_icms"] = _get_float(icms_tot, "vICMS", 0.0)
                note_data["base_icms"] = _get_float(icms_tot, "vBC", 0.0)
                note_data["desconto"] = _get_float(icms_tot, "vDesc", 0.0)
                note_data["icms_desonerado"] = _get_float(icms_tot, "vICMSDeson", 0.0)
                note_data["frete"] = _get_float(icms_tot, "vFrete", 0.0)

            tp_emis = _get_text(ide, "tpEmis")
            if tp_emis:
                note_data["tipo_emissao"] = "NORMAL" if tp_emis == "1" else "CONTINGENCIA"

            tp_amb = _get_text(ide, "tpAmb")
            if tp_amb == "1":
                note_data["ambiente"] = "Produção"
            elif tp_amb == "2":
                note_data["ambiente"] = "Homologação"

            raw_emi = _get_text(ide, "dhEmi") or _get_text(ide, "dEmi")
            if raw_emi:
                d_obj, fmt_str, d_only, t_only, _, _ = parse_iso_datetime_parts(raw_emi)
                if d_obj:
                    note_data["data_emissao_obj"] = d_obj
                    note_data["data_emissao_str"] = fmt_str
                    note_data["data_emissao_only_str"] = d_only
                    note_data["hora_emissao_str"] = t_only

            raw_recbto = _get_text(inf_prot, "dhRecbto")
            if not raw_recbto:
                rec_elem = _find_first(root, "dhRecbto")
                raw_recbto = rec_elem.text.strip() if rec_elem is not None and rec_elem.text else ""

            if raw_recbto:
                d_obj_aut, fmt_str_aut, d_only_aut, t_only_aut, ano_mes_aut, _ = parse_iso_datetime_parts(raw_recbto)
                if d_obj_aut:
                    note_data["data_autorizacao_obj"] = d_obj_aut
                    note_data["data_autorizacao_str"] = fmt_str_aut
                    note_data["data_autorizacao_only_str"] = d_only_aut
                    note_data["hora_autorizacao_str"] = t_only_aut
                    note_data["ano_mes_autorizacao"] = ano_mes_aut
            else:
                note_data["data_autorizacao_obj"] = note_data.get("data_emissao_obj")
                note_data["data_autorizacao_str"] = note_data.get("data_emissao_str", "")
                note_data["data_autorizacao_only_str"] = note_data.get("data_emissao_only_str", "")
                note_data["hora_autorizacao_str"] = note_data.get("hora_emissao_str", "")
                note_data["ano_mes_autorizacao"] = note_data.get("ano_mes")

            n_prot = _get_text(inf_prot, "nProt")
            c_stat = _get_text(inf_prot, "cStat")
            x_motivo = _get_text(inf_prot, "xMotivo")
            note_data["protocolo"] = n_prot
            note_data["codigo_status"] = c_stat
            note_data["motivo"] = x_motivo

            # Verifica se há evento de cancelamento vinculado (<retEvento> ou <procEventoNFe>)
            is_cancel_event = False
            inf_evento = _find_first(root, "infEvento")
            if inf_evento is not None:
                tp_evento = _get_text(inf_evento, "tpEvento")
                x_evento = _get_text(inf_evento, "xEvento")
                ev_cstat = _get_text(inf_evento, "cStat")
                ev_motivo = _get_text(inf_evento, "xMotivo")
                ev_nprot = _get_text(inf_evento, "nProt")
                if tp_evento == "110111" or "cancel" in x_evento.lower():
                    # Considera cancelado se evento registrado (135/136/155) ou sem cStat de rejeição
                    if not ev_cstat or ev_cstat in ("135", "136", "155", "101", "151"):
                        is_cancel_event = True
                        if ev_nprot:
                            note_data["protocolo"] = ev_nprot
                        if ev_cstat:
                            note_data["codigo_status"] = ev_cstat
                        if ev_motivo:
                            note_data["motivo"] = f"{x_evento}: {ev_motivo}" if x_evento else ev_motivo

            if is_cancel_event or c_stat in ("101", "151", "155") or "cancelad" in x_motivo.lower():
                note_data["status"] = "CANCELADA"
                note_data["is_cancellation"] = True
            elif c_stat in ("100", "150") or n_prot:
                note_data["status"] = "AUTORIZADA"
            elif tp_emis and tp_emis != "1":
                note_data["status"] = "CONTINGENCIA"
            elif not n_prot and not c_stat:
                note_data["status"] = "CONTINGENCIA" if note_data.get("tipo_emissao") == "CONTINGENCIA" else "AUTORIZADA"

            parsed_ok = True
        except Exception:
            parsed_ok = False

        if parsed_ok:
            return

        # Fallback por regex caso o XML esteja malformado
        vnf_match = VNF_REGEX.search(content)
        if vnf_match:
            try:
                note_data["valor_total"] = float(vnf_match.group(1).strip().replace(",", "."))
            except ValueError:
                pass

        xnome_match = XNOME_EMIT_REGEX.search(content)
        if xnome_match:
            note_data["emit_nome"] = xnome_match.group(1).strip()

        dhemi_match = DHEMI_REGEX.search(content)
        if dhemi_match:
            raw_emi = dhemi_match.group(1).strip()
            d_obj, fmt_str, d_only, t_only, _, _ = parse_iso_datetime_parts(raw_emi)
            if d_obj:
                note_data["data_emissao_obj"] = d_obj
                note_data["data_emissao_str"] = fmt_str
                note_data["data_emissao_only_str"] = d_only
                note_data["hora_emissao_str"] = t_only

        dhrecbto_match = DHRECBTO_REGEX.search(content)
        if dhrecbto_match:
            raw_recbto = dhrecbto_match.group(1).strip()
            d_obj_aut, fmt_str_aut, d_only_aut, t_only_aut, ano_mes_aut, _ = parse_iso_datetime_parts(raw_recbto)
            if d_obj_aut:
                note_data["data_autorizacao_obj"] = d_obj_aut
                note_data["data_autorizacao_str"] = fmt_str_aut
                note_data["data_autorizacao_only_str"] = d_only_aut
                note_data["hora_autorizacao_str"] = t_only_aut
                note_data["ano_mes_autorizacao"] = ano_mes_aut
        else:
            note_data["data_autorizacao_obj"] = note_data.get("data_emissao_obj")
            note_data["data_autorizacao_str"] = note_data.get("data_emissao_str", "")
            note_data["data_autorizacao_only_str"] = note_data.get("data_emissao_only_str", "")
            note_data["hora_autorizacao_str"] = note_data.get("hora_emissao_str", "")
            note_data["ano_mes_autorizacao"] = note_data.get("ano_mes")

    except Exception:
        pass

def parse_inut_xml(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Analisa arquivos de Inutilização de NF-e/NFC-e (ProcInutNFe ou inutNFe).
    Extrai CNPJ, Modelo, Série, nNFIni, nNFFin, Ano e Justificativa.
    """
    try:
        content = None
        safe_path = to_long_path(file_path)
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                with open(safe_path, "r", encoding=enc) as f:
                    content = f.read()
                    break
            except UnicodeDecodeError:
                continue

        if not content or ("inutNFe" not in content and "ProcInutNFe" not in content):
            return None

        root = ET.fromstring(content)
        
        def find_first(element, local_tag):
            for elem in element.iter():
                tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag_name.lower() == local_tag.lower():
                    return elem
            return None

        inf_inut = find_first(root, "infInut")
        if inf_inut is None:
            return None

        cnpj_elem = find_first(inf_inut, "CNPJ")
        mod_elem = find_first(inf_inut, "mod")
        serie_elem = find_first(inf_inut, "serie")
        ini_elem = find_first(inf_inut, "nNFIni")
        fin_elem = find_first(inf_inut, "nNFFin")
        ano_elem = find_first(inf_inut, "ano")
        just_elem = find_first(inf_inut, "xJust")
        motivo_elem = find_first(root, "xMotivo")

        cnpj = clean_digits(cnpj_elem.text) if cnpj_elem is not None and cnpj_elem.text else ""
        mod = mod_elem.text.strip() if mod_elem is not None and mod_elem.text else ""
        serie_raw = serie_elem.text.strip() if serie_elem is not None and serie_elem.text else "0"
        serie = str(int(serie_raw)) if serie_raw.isdigit() else serie_raw
        
        nnf_ini = int(ini_elem.text.strip()) if ini_elem is not None and ini_elem.text and ini_elem.text.strip().isdigit() else 0
        nnf_fin = int(fin_elem.text.strip()) if fin_elem is not None and fin_elem.text and fin_elem.text.strip().isdigit() else nnf_ini
        ano = ano_elem.text.strip() if ano_elem is not None and ano_elem.text else ""
        x_just = just_elem.text.strip() if just_elem is not None and just_elem.text else ""
        x_motivo = motivo_elem.text.strip() if motivo_elem is not None and motivo_elem.text else ""

        if not cnpj or not mod or nnf_ini == 0:
            return None

        dhrecbto_elem = find_first(root, "dhRecbto")
        rec_str = dhrecbto_elem.text.strip() if dhrecbto_elem is not None and dhrecbto_elem.text else ""
        _, _, d_aut_only, t_aut_only, ano_mes_inut, _ = parse_iso_datetime_parts(rec_str)
        if not ano_mes_inut:
            m_date = re.search(r"(20\d{2})[_-](\d{2})[_-](\d{2})", file_path.name)
            if m_date:
                ano_mes_inut = f"{m_date.group(1)}-{m_date.group(2)}"
                d_aut_only = f"{m_date.group(3)}/{m_date.group(2)}/{m_date.group(1)}"

        return {
            "tipo": "INUT",
            "path": file_path,
            "filename": file_path.name,
            "emit_cnpj": cnpj,
            "modelo": mod,
            "serie": serie,
            "nnf_ini": nnf_ini,
            "nnf_fin": nnf_fin,
            "ano": ano,
            "ano_mes": ano_mes_inut,
            "data_autorizacao_only_str": d_aut_only,
            "hora_autorizacao_str": t_aut_only,
            "justificativa": x_just,
            "motivo": x_motivo,
            "origem": "",
        }
    except Exception:
        return None


def parse_cancel_event_xml(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Analisa arquivos avulsos de evento de cancelamento (procEventoNFe / retEvento)
    que não possuem a tag <infNFe>, retornando chNFe, protocolo, código, motivo e data.
    """
    try:
        content = None
        safe_path = to_long_path(file_path)
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                with open(safe_path, "r", encoding=enc) as f:
                    content = f.read()
                    break
            except UnicodeDecodeError:
                continue

        if not content or "infNFe" in content or "110111" not in content:
            return None

        root = ET.fromstring(content)
        inf_evento = _find_first(root, "infEvento")
        if inf_evento is None:
            return None

        tp_evento = _get_text(inf_evento, "tpEvento")
        x_evento = _get_text(inf_evento, "xEvento")
        if tp_evento != "110111" and "cancel" not in x_evento.lower():
            return None

        ch_nfe = clean_digits(_get_text(inf_evento, "chNFe"))
        if len(ch_nfe) != 44:
            return None

        c_stat = _get_text(inf_evento, "cStat")
        if c_stat and c_stat not in ("135", "136", "155", "101", "151"):
            return None

        dh_reg = _get_text(inf_evento, "dhRegEvento")
        _, _, d_aut_only, t_aut_only, _, _ = parse_iso_datetime_parts(dh_reg)
        return {
            "chave": ch_nfe,
            "path": file_path,
            "protocolo": _get_text(inf_evento, "nProt"),
            "codigo_status": c_stat,
            "motivo": f"{x_evento}: {_get_text(inf_evento, 'xMotivo')}".strip(": "),
            "data_autorizacao_only_str": d_aut_only,
            "hora_autorizacao_str": t_aut_only,
        }
    except Exception:
        return None

def parse_regular_xml_fallback(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Fallback para ler notas fiscais regulares que porventura não tenham a chave no nome.
    """
    try:
        content = None
        safe_path = to_long_path(file_path)
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                with open(safe_path, "r", encoding=enc) as f:
                    content = f.read()
                    break
            except UnicodeDecodeError:
                continue

        if not content or "infNFe" not in content:
            return None

        root = ET.fromstring(content)
        def find_first(element, local_tag):
            for elem in element.iter():
                tag_name = elem.tag.split("}")[-1] if "}" in elem.tag else elem.tag
                if tag_name.lower() == local_tag.lower():
                    return elem
            return None

        inf_nfe = find_first(root, "infNFe")
        if inf_nfe is None:
            return None

        ide = find_first(inf_nfe, "ide")
        if ide is None:
            return None

        mod_elem = find_first(ide, "mod")
        serie_elem = find_first(ide, "serie")
        nnf_elem = find_first(ide, "nNF")
        dhemi_elem = find_first(ide, "dhEmi")
        demi_elem = find_first(ide, "dEmi")

        modelo = mod_elem.text.strip() if mod_elem is not None and mod_elem.text else ""
        serie = str(int(serie_elem.text.strip())) if serie_elem is not None and serie_elem.text and serie_elem.text.strip().isdigit() else "0"
        numero = int(nnf_elem.text.strip()) if nnf_elem is not None and nnf_elem.text and nnf_elem.text.strip().isdigit() else 0

        # Emitente
        emit = find_first(inf_nfe, "emit")
        emit_cnpj = ""
        emit_nome = ""
        if emit is not None:
            cnpj_elem = find_first(emit, "CNPJ")
            if cnpj_elem is not None and cnpj_elem.text:
                emit_cnpj = clean_digits(cnpj_elem.text)
            xnome_elem = find_first(emit, "xNome")
            if xnome_elem is not None and xnome_elem.text:
                emit_nome = xnome_elem.text.strip()

        # Datas
        d_str = dhemi_elem.text if (dhemi_elem is not None and dhemi_elem.text) else (demi_elem.text if (demi_elem is not None and demi_elem.text) else "")
        d_obj, data_emissao_str, data_emi_only, hora_emi, ano_mes, aamm = parse_iso_datetime_parts(d_str)

        dhrecbto_elem = find_first(root, "dhRecbto")
        recbto_str = dhrecbto_elem.text.strip() if dhrecbto_elem is not None and dhrecbto_elem.text else ""
        d_obj_aut, data_aut_str, data_aut_only, hora_aut, ano_mes_aut, _ = parse_iso_datetime_parts(recbto_str)
        if not d_obj_aut:
            d_obj_aut = d_obj
            data_aut_str = data_emissao_str
            data_aut_only = data_emi_only
            hora_aut = hora_emi
            ano_mes_aut = ano_mes

        # Valor
        valor_total = 0.0
        total_elem = find_first(inf_nfe, "total")
        if total_elem is not None:
            vnf_elem = find_first(total_elem, "vNF")
            if vnf_elem is not None and vnf_elem.text:
                try:
                    valor_total = float(vnf_elem.text.strip().replace(",", "."))
                except ValueError:
                    pass

        chave = ""
        inf_id = inf_nfe.attrib.get("Id", "")
        if inf_id.startswith("NFe"):
            chave = inf_id[3:]

        result = {
            "tipo": "NFE",
            "path": file_path,
            "chave": chave,
            "modelo": modelo,
            "serie": serie,
            "numero": numero,
            "ano_mes": ano_mes,
            "emit_cnpj": emit_cnpj,
            "emit_nome": emit_nome,
            "valor_total": valor_total,
            "data_emissao_str": data_emissao_str,
            "data_emissao_only_str": data_emi_only,
            "hora_emissao_str": hora_emi,
            "data_autorizacao_str": data_aut_str,
            "data_autorizacao_only_str": data_aut_only,
            "hora_autorizacao_str": hora_aut,
            "data_emissao_obj": d_obj,
            "data_autorizacao_obj": d_obj_aut,
            "ano_mes_autorizacao": ano_mes_aut,
        }
        quick_read_xml_details(file_path, result)
        return result
    except Exception:
        return None
