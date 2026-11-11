import re
import xml.etree.ElementTree as ET
from datetime import datetime, date
from pathlib import Path
from typing import Optional, Dict, Any, Tuple

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

def parse_iso_datetime(dt_str: Optional[str]) -> Tuple[Optional[date], str, str, str]:
    """
    Analisa string de data ISO (ex: 2026-10-31T23:30:03-04:00 ou 2026-10-31).
    Retorna (date_obj, formatada_str 'dd/mm/aaaa hh:mm', ano_mes 'aaaa-mm', aamm 'aamm')
    """
    if not dt_str:
        return None, "", "", ""
    dt_str = dt_str.strip()
    try:
        # Se contiver 'T', tenta fromisoformat
        if "T" in dt_str:
            dt = datetime.fromisoformat(dt_str)
            d_obj = dt.date()
            fmt = dt.strftime("%d/%m/%Y %H:%M")
            ano_mes = dt.strftime("%Y-%m")
            aamm = f"{str(dt.year)[-2:]}{dt.month:02d}"
            return d_obj, fmt, ano_mes, aamm
        elif len(dt_str) >= 10:
            partes = dt_str[:10].split("-")
            if len(partes) == 3:
                ano, mes, dia = int(partes[0]), int(partes[1]), int(partes[2])
                d_obj = date(ano, mes, dia)
                fmt = f"{dia:02d}/{mes:02d}/{ano:04d}"
                ano_mes = f"{ano:04d}-{mes:02d}"
                aamm = f"{str(ano)[-2:]}{mes:02d}"
                return d_obj, fmt, ano_mes, aamm
    except Exception:
        pass
    return None, "", "", ""

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
        "data_emissao_str": f"01/{mes}/{ano}",
        "data_autorizacao_str": "",
        "data_emissao_obj": None,
        "data_autorizacao_obj": None,
        "ano_mes_autorizacao": ano_mes
    }

def quick_read_xml_details(file_path: Path, note_data: Dict[str, Any]) -> None:
    """
    Lê rapidamente o valor total (<vNF>), nome do emitente (<xNome>),
    data de emissão exata (<dhEmi>) e data de autorização na SEFAZ (<dhRecbto>).
    """
    try:
        content = ""
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                with open(file_path, "r", encoding=enc) as f:
                    content = f.read()
                    break
            except UnicodeDecodeError:
                continue

        if not content:
            return

        # Valor Total vNF
        vnf_match = VNF_REGEX.search(content)
        if vnf_match:
            try:
                note_data["valor_total"] = float(vnf_match.group(1).strip().replace(",", "."))
            except ValueError:
                pass

        # Nome do Emitente
        xnome_match = XNOME_EMIT_REGEX.search(content)
        if xnome_match:
            note_data["emit_nome"] = xnome_match.group(1).strip()

        # Data Exata de Emissão (<dhEmi> ou <dEmi>)
        dhemi_match = DHEMI_REGEX.search(content)
        if dhemi_match:
            raw_emi = dhemi_match.group(1).strip()
            d_obj, fmt_str, ano_mes, aamm = parse_iso_datetime(raw_emi)
            if d_obj:
                note_data["data_emissao_obj"] = d_obj
                note_data["data_emissao_str"] = fmt_str

        # Data de Autorização na SEFAZ (<dhRecbto>)
        dhrecbto_match = DHRECBTO_REGEX.search(content)
        if dhrecbto_match:
            raw_recbto = dhrecbto_match.group(1).strip()
            d_obj_aut, fmt_str_aut, ano_mes_aut, aamm_aut = parse_iso_datetime(raw_recbto)
            if d_obj_aut:
                note_data["data_autorizacao_obj"] = d_obj_aut
                note_data["data_autorizacao_str"] = fmt_str_aut
                note_data["ano_mes_autorizacao"] = ano_mes_aut
        else:
            # Fallback se não houver dhRecbto: usa os dados da emissão
            note_data["data_autorizacao_obj"] = note_data.get("data_emissao_obj")
            note_data["data_autorizacao_str"] = note_data.get("data_emissao_str", "")
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
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                with open(file_path, "r", encoding=enc) as f:
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
            "justificativa": x_just,
            "motivo": x_motivo
        }
    except Exception:
        return None

def parse_regular_xml_fallback(file_path: Path) -> Optional[Dict[str, Any]]:
    """
    Fallback para ler notas fiscais regulares que porventura não tenham a chave no nome.
    """
    try:
        content = None
        for enc in ("utf-8", "latin-1", "cp1252"):
            try:
                with open(file_path, "r", encoding=enc) as f:
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
        d_obj, data_emissao_str, ano_mes, aamm = parse_iso_datetime(d_str)

        dhrecbto_elem = find_first(root, "dhRecbto")
        recbto_str = dhrecbto_elem.text.strip() if dhrecbto_elem is not None and dhrecbto_elem.text else ""
        d_obj_aut, data_aut_str, ano_mes_aut, _ = parse_iso_datetime(recbto_str)
        if not d_obj_aut:
            d_obj_aut = d_obj
            data_aut_str = data_emissao_str
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

        return {
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
            "data_autorizacao_str": data_aut_str,
            "data_emissao_obj": d_obj,
            "data_autorizacao_obj": d_obj_aut,
            "ano_mes_autorizacao": ano_mes_aut
        }
    except Exception:
        return None
