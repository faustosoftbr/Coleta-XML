import os
import shutil
import zipfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import List, Dict, Any, Set, Optional, Callable, Tuple

from src.xml_parser import (
    extract_key_from_filename,
    parse_key_metadata,
    quick_read_xml_details,
    parse_inut_xml,
    parse_regular_xml_fallback,
    clean_digits
)
from src.sequence import analyze_sequences
from src.exporter import generate_txt_report

def get_adjacent_month_bounds(year_int: int, month_int: int):
    """Calcula códigos AAMM e YYYY-MM para mês anterior e mês posterior."""
    if month_int == 1:
        prev_y, prev_m = year_int - 1, 12
    else:
        prev_y, prev_m = year_int, month_int - 1

    if month_int == 12:
        next_y, next_m = year_int + 1, 1
    else:
        next_y, next_m = year_int, month_int + 1

    prev_aamm = f"{str(prev_y)[-2:]}{prev_m:02d}"
    prev_ano_mes = f"{prev_y:04d}-{prev_m:02d}"

    next_aamm = f"{str(next_y)[-2:]}{next_m:02d}"
    next_ano_mes = f"{next_y:04d}-{next_m:02d}"

    return (prev_aamm, prev_ano_mes, prev_y, prev_m), (next_aamm, next_ano_mes, next_y, next_m)

class CollectorEngine:
    def __init__(
        self,
        source_paths: List[str],
        destination_path: str,
        cnpjs: List[str],
        target_month: str,
        target_year: str,
        filter_nfe: bool,
        filter_nfce: bool,
        generate_zip: bool,
        on_progress: Optional[Callable[[int, int, str], None]] = None,
        on_log: Optional[Callable[[str], None]] = None,
        on_finished: Optional[Callable[[Dict[str, Any]], None]] = None,
    ):
        self.source_paths = source_paths
        self.destination_path = destination_path
        self.cnpjs_set = {clean_digits(c) for c in cnpjs if clean_digits(c)}
        
        self.target_month_int = int(target_month)
        self.target_year_int = int(target_year)
        self.target_month = f"{self.target_month_int:02d}"
        self.target_year = f"{self.target_year_int:04d}"
        
        # Mês alvo
        self.target_aamm = f"{self.target_year[-2:]}{self.target_month}"
        self.target_ano_mes = f"{self.target_year}-{self.target_month}"

        # Meses vizinhos para análise de borda (virada de mês / autorização)
        prev_info, next_info = get_adjacent_month_bounds(self.target_year_int, self.target_month_int)
        self.prev_aamm, self.prev_ano_mes, self.prev_year, self.prev_month = prev_info
        self.next_aamm, self.next_ano_mes, self.next_year, self.next_month = next_info
        
        self.filter_nfe = filter_nfe
        self.filter_nfce = filter_nfce
        self.generate_zip = generate_zip
        
        self.on_progress = on_progress
        self.on_log = on_log
        self.on_finished = on_finished
        
        self._cancel_event = threading.Event()
        self.thread: Optional[threading.Thread] = None

    def cancel(self):
        """Sinaliza para cancelar o processo em andamento."""
        self._cancel_event.set()

    def is_cancelled(self) -> bool:
        return self._cancel_event.is_set()

    def start(self):
        """Inicia o processo em thread separada."""
        self._cancel_event.clear()
        self.thread = threading.Thread(target=self._run, daemon=True)
        self.thread.start()

    def _log(self, msg: str):
        if self.on_log:
            self.on_log(msg)

    def _report_progress(self, scanned: int, matched: int, cur_file: str):
        if self.on_progress:
            self.on_progress(scanned, matched, cur_file)

    def _run(self):
        self._log(
            f"Iniciando busca inteligente para o mês {self.target_month}/{self.target_year} "
            f"(com validação de autorização <dhRecbto> na virada de mês)..."
        )
        
        target_candidates: List[Dict[str, Any]] = []
        next_boundary_candidates: List[Dict[str, Any]] = []
        prev_boundary_candidates: List[Dict[str, Any]] = []
        non_key_files: List[Tuple[Path, str]] = []
        scanned_count = 0
        vistas_chaves: Set[str] = set()

        # 1. Primeira Passagem: Varredura ultrarrápida por chave SEFAZ (Zero-IO)
        for src in self.source_paths:
            if self.is_cancelled():
                break
            src_path = Path(src)
            if not src_path.exists():
                self._log(f"Aviso: Diretório não acessível: {src}")
                continue

            self._log(f"Varrendo diretório: {src}")
            try:
                for root, _, files in os.walk(src_path):
                    if self.is_cancelled():
                        break
                    for fname in files:
                        if self.is_cancelled():
                            break

                        if not fname.lower().endswith(".xml"):
                            continue

                        scanned_count += 1
                        if scanned_count % 100 == 0:
                            self._report_progress(scanned_count, len(target_candidates), fname)

                        key_44 = extract_key_from_filename(fname)
                        if not key_44:
                            non_key_files.append((Path(root), fname))
                            continue

                        # Filtro de Modelo
                        mod = key_44[20:22]
                        if mod == "55" and not self.filter_nfe:
                            continue
                        if mod == "65" and not self.filter_nfce:
                            continue
                        if mod not in ("55", "65"):
                            continue

                        # Filtro de CNPJ
                        cnpj_emit = key_44[6:20]
                        if self.cnpjs_set and cnpj_emit not in self.cnpjs_set:
                            continue

                        if key_44 in vistas_chaves:
                            continue
                        vistas_chaves.add(key_44)

                        key_aamm = key_44[2:6]
                        meta = parse_key_metadata(key_44)
                        if not meta:
                            continue
                        meta["path"] = Path(root) / fname

                        if key_aamm == self.target_aamm:
                            target_candidates.append(meta)
                        elif key_aamm == self.next_aamm:
                            next_boundary_candidates.append(meta)
                        elif key_aamm == self.prev_aamm:
                            prev_boundary_candidates.append(meta)

            except Exception as e:
                self._log(f"Erro ao acessar {src}: {str(e)}")

        if self.is_cancelled():
            self._log("Operação cancelada pelo usuário.")
            if self.on_finished:
                self.on_finished({"cancelled": True, "notes": [], "inut_records": [], "audit": []})
            return

        self._log(
            f"1ª etapa concluída: {scanned_count} arquivos verificados. "
            f"Candidatos do mês: {len(target_candidates)} | Bordas: +{len(next_boundary_candidates)} próx, +{len(prev_boundary_candidates)} ant."
        )

        # 2. Leitura rápida de detalhes (<vNF>, <xNome>, <dhEmi>, <dhRecbto>) em paralelo
        all_candidates_to_read = target_candidates + next_boundary_candidates + prev_boundary_candidates
        if all_candidates_to_read:
            def load_detail(note):
                quick_read_xml_details(note["path"], note)

            with ThreadPoolExecutor(max_workers=16) as executor:
                list(executor.map(load_detail, all_candidates_to_read))

        # 3. Filtragem Definitiva Pela Data de Autorização (<dhRecbto>)
        matched_notes: List[Dict[str, Any]] = []

        # A. Candidatos do próprio mês:
        for note in target_candidates:
            # Se dhRecbto estiver no mês alvo (ou fallback dhEmi)
            aut_mes = note.get("ano_mes_autorizacao", "")
            if aut_mes == self.target_ano_mes:
                matched_notes.append(note)
            elif not aut_mes and note.get("ano_mes") == self.target_ano_mes:
                matched_notes.append(note)
            else:
                # Foi emitida no mês alvo mas autorizada em outro mês (ex: virada)
                self._log(f"Nota {note['numero']} emitida em {note['data_emissao_str']} mas autorizada em {note['data_autorizacao_str']} (fora de {self.target_month}/{self.target_year}).")

        # B. Candidatos do mês seguinte (Borda: ex: emitida 01/11 mas autorizada 31/10):
        for note in next_boundary_candidates:
            d_emi = note.get("data_emissao_obj")
            aut_mes = note.get("ano_mes_autorizacao", "")
            # Se emitida no dia 1 (ou início) do mês seguinte, e autorizada no mês alvo
            if d_emi and d_emi.day == 1 and aut_mes == self.target_ano_mes:
                matched_notes.append(note)
                self._log(
                    f"✔ Enquadrada em {self.target_month}/{self.target_year}: Nota {note['numero']} (Mod {note['modelo']} Série {note['serie']}) "
                    f"emitida em {note['data_emissao_str']} com AUTORIZAÇÃO em {note['data_autorizacao_str']}!"
                )

        # C. Candidatos do mês anterior (Borda: ex: emitida no último dia do mês anterior mas autorizada no dia 01 do mês alvo):
        for note in prev_boundary_candidates:
            d_emi = note.get("data_emissao_obj")
            aut_mes = note.get("ano_mes_autorizacao", "")
            if aut_mes == self.target_ano_mes:
                matched_notes.append(note)
                self._log(
                    f"✔ Enquadrada em {self.target_month}/{self.target_year}: Nota {note['numero']} (Mod {note['modelo']} Série {note['serie']}) "
                    f"emitida em {note['data_emissao_str']} com AUTORIZAÇÃO em {note['data_autorizacao_str']}!"
                )

        self._log(f"Total de notas confirmadas para {self.target_month}/{self.target_year} por data de autorização: {len(matched_notes)}")

        # 4. Auditoria inicial da sequência
        initial_audit = analyze_sequences(matched_notes)
        quebras_iniciais = [a for a in initial_audit if a["tem_quebra"]]
        
        inut_records_found: List[Dict[str, Any]] = []
        vistos_inut_paths: Set[Path] = set()

        # 5. Segunda Passagem Direcionada: Busca de Inutilizações se houver quebra
        if quebras_iniciais and non_key_files:
            self._log("Detectada quebra na sequência inicial. Buscando arquivos de inutilização/faltantes pelo número...")
            
            faltantes_map = {}
            for q in quebras_iniciais:
                k = (q["cnpj"], q["modelo"], q["serie"])
                faltantes_map[k] = set(q["numeros_faltantes"])

            for root_dir, fname in non_key_files:
                if self.is_cancelled():
                    break
                full_path = root_dir / fname

                for (cnpj, modelo, serie), numeros_set in faltantes_map.items():
                    numero_achado = None
                    for num in list(numeros_set):
                        num_str = str(num)
                        num_padded = f"{num:09d}"
                        if num_str in fname or num_padded in fname:
                            numero_achado = num
                            break

                    if numero_achado is not None:
                        inut_data = parse_inut_xml(full_path)
                        if inut_data:
                            if (not self.cnpjs_set or inut_data["emit_cnpj"] in self.cnpjs_set) and \
                               inut_data["modelo"] == modelo and inut_data["serie"] == serie:
                                if inut_data["nnf_ini"] <= numero_achado <= inut_data["nnf_fin"]:
                                    if full_path not in vistos_inut_paths:
                                        vistos_inut_paths.add(full_path)
                                        inut_records_found.append(inut_data)
                                        self._log(f"✔ Inutilização localizada: {fname} (Cobre nota {numero_achado})")
                                        numeros_set.discard(numero_achado)
                        else:
                            regular_data = parse_regular_xml_fallback(full_path)
                            if regular_data and regular_data["numero"] == numero_achado:
                                if (not self.cnpjs_set or regular_data["emit_cnpj"] in self.cnpjs_set) and \
                                   regular_data["modelo"] == modelo and regular_data["serie"] == serie:
                                    # Verifica autorização
                                    aut_mes = regular_data.get("ano_mes_autorizacao", "")
                                    if aut_mes == self.target_ano_mes or not aut_mes:
                                        matched_notes.append(regular_data)
                                        self._log(f"✔ Nota com nome alternativo localizada: {fname} (Nota {numero_achado})")
                                        numeros_set.discard(numero_achado)

        # 6. Reavaliação da auditoria com as inutilizações/notas encontradas
        final_audit = analyze_sequences(matched_notes, inut_records_found)
        quebras_reais = [a for a in final_audit if a["tem_quebra"]]
        inut_resolvidas = [a for a in final_audit if a["teve_inutilizacao"]]

        if inut_resolvidas:
            self._log(f"Foram anexadas {len(inut_records_found)} inutilizações ao processo.")
        if quebras_reais:
            self._log(f"ALERTA: Permanecem {len(quebras_reais)} séries com quebra de numeração pendente!")
        else:
            self._log("Auditoria final: Todas as numerações estão contínuas ou regularizadas por Inutilização!")

        # 7. Gravação / Organização e Geração do ZIP
        dest_dir = Path(self.destination_path)
        dest_dir.mkdir(parents=True, exist_ok=True)

        search_params = {
            "cnpjs_str": ", ".join(sorted(self.cnpjs_set)) if self.cnpjs_set else "Todos (Sem restrição)",
            "data_ini": f"01/{self.target_month}/{self.target_year}",
            "data_fim": f"Fim de {self.target_month}/{self.target_year} (Autorização SEFAZ)",
            "modelos_str": "NF-e (55) e NFC-e (65)" if (self.filter_nfe and self.filter_nfce) else ("NF-e (55)" if self.filter_nfe else "NFC-e (65)")
        }

        txt_report_content = generate_txt_report(matched_notes, inut_records_found, final_audit, search_params)

        zip_file_path = None
        if self.generate_zip and (matched_notes or inut_records_found):
            primeiro_cnpj = sorted(self.cnpjs_set)[0] if self.cnpjs_set else "XMLs"
            zip_name = f"XML_Fiscal_{primeiro_cnpj}_{self.target_year}_{self.target_month}.zip"
            zip_file_path = dest_dir / zip_name

            counter = 1
            while zip_file_path.exists():
                zip_file_path = dest_dir / f"XML_Fiscal_{primeiro_cnpj}_{self.target_year}_{self.target_month}_{counter}.zip"
                counter += 1

            self._log(f"Gerando pacote ZIP com {len(matched_notes)} notas e {len(inut_records_found)} inutilizações...")
            with zipfile.ZipFile(zip_file_path, "w", zipfile.ZIP_DEFLATED) as zipf:
                # 1. Relatório em texto exclusivo dentro do ZIP
                zipf.writestr("relatorio_coleta.txt", txt_report_content.encode("utf-8"))

                # 2. XMLs de notas fiscais (organizados no mês de autorização)
                for note in matched_notes:
                    if self.is_cancelled():
                        break
                    src_file = note["path"]
                    cnpj_folder = note["emit_cnpj"] or "Sem_CNPJ"
                    ano_mes = note.get("ano_mes_autorizacao") or f"{self.target_year}-{self.target_month}"
                    mod_folder = f"Modelo_{note['modelo']}"
                    inner_path = f"{cnpj_folder}/{ano_mes}/{mod_folder}/{src_file.name}"
                    zipf.write(src_file, arcname=inner_path)

                # 3. XMLs de Inutilizações localizadas anexadas junto no ZIP
                for inut in inut_records_found:
                    if self.is_cancelled():
                        break
                    src_file = inut["path"]
                    cnpj_folder = inut["emit_cnpj"] or "Sem_CNPJ"
                    ano_mes = f"{self.target_year}-{self.target_month}"
                    mod_folder = f"Modelo_{inut['modelo']}"
                    inner_path = f"{cnpj_folder}/{ano_mes}/{mod_folder}/Inutilizadas/{src_file.name}"
                    zipf.write(src_file, arcname=inner_path)

            self._log("Pacote ZIP gerado com sucesso!")

        self._report_progress(scanned_count, len(matched_notes) + len(inut_records_found), "Processo Concluído.")

        result = {
            "cancelled": self.is_cancelled(),
            "total_scanned": scanned_count,
            "total_matched": len(matched_notes),
            "total_inut": len(inut_records_found),
            "notes": matched_notes,
            "inut_records": inut_records_found,
            "audit": final_audit,
            "has_sequence_break": len(quebras_reais) > 0,
            "quebras_count": len(quebras_reais),
            "inut_count": len(inut_records_found),
            "zip_path": str(zip_file_path) if zip_file_path else None
        }

        if self.on_finished:
            self.on_finished(result)
