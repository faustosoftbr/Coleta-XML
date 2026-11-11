import os
import sys
import tkinter as tk
from tkinter import filedialog, messagebox
import customtkinter as ctk
from datetime import datetime, date
from pathlib import Path
from typing import List, Optional

from src.config import load_config, save_config
from src.collector import CollectorEngine
from src.xml_parser import clean_digits

ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

MESES_NOMES = [
    "01 - Janeiro",
    "02 - Fevereiro",
    "03 - Março",
    "04 - Abril",
    "05 - Maio",
    "06 - Junho",
    "07 - Julho",
    "08 - Agosto",
    "09 - Setembro",
    "10 - Outubro",
    "11 - Novembro",
    "12 - Dezembro"
]

class FoldersConfigWindow(ctk.CTkToplevel):
    """Janela modal para gerenciamento das pastas de busca locais e da intranet."""
    def __init__(self, parent, current_folders: List[str], on_save_callback):
        super().__init__(parent)
        self.title("Configurações das Pastas de Busca (Locais e Intranet)")
        self.geometry("720x460")
        self.minsize(620, 380)
        self.parent = parent
        self.on_save_callback = on_save_callback
        self.folders = list(current_folders)

        # Torna modal
        self.transient(parent)
        self.grab_set()

        self._build_ui()

    def _build_ui(self):
        # Cabeçalho da Janela Modal
        header = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray80", "gray20"))
        header.pack(fill="x", padx=0, pady=0)

        ctk.CTkLabel(
            header,
            text="Pastas de Busca de Arquivos XML",
            font=ctk.CTkFont(size=16, weight="bold")
        ).pack(anchor="w", padx=20, pady=(12, 2))

        ctk.CTkLabel(
            header,
            text="Adicione pastas locais ou caminhos de rede UNC da intranet (Ex: \\\\192.168.1.100\\Notas ou \\\\ServidorPDV\\XML).",
            font=ctk.CTkFont(size=12),
            text_color="gray60"
        ).pack(anchor="w", padx=20, pady=(0, 12))

        container = ctk.CTkFrame(self, fg_color="transparent")
        container.pack(fill="both", expand=True, padx=20, pady=15)

        # Barra de Botões Superiores
        btn_bar = ctk.CTkFrame(container, fg_color="transparent")
        btn_bar.pack(fill="x", pady=(0, 10))

        ctk.CTkButton(btn_bar, text="+ Pasta Local", width=120, command=self._add_local_folder).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_bar, text="+ Intranet (UNC)", width=130, command=self._add_unc_folder).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_bar, text="- Remover Selecionada", width=140, fg_color="#b33939", hover_color="#8b2626", command=self._remove_folder).pack(side="left", padx=(0, 8))
        ctk.CTkButton(btn_bar, text="Limpar Tudo", width=100, fg_color="gray40", hover_color="gray30", command=self._clear_folders).pack(side="left")

        # Lista de Pastas
        self.listbox = tk.Listbox(
            container,
            bg="#2b2b2b",
            fg="#ffffff",
            selectbackground="#1f6aa5",
            selectforeground="#ffffff",
            highlightthickness=0,
            font=("Consolas", 10),
            borderwidth=1,
            relief="flat"
        )
        self.listbox.pack(fill="both", expand=True, pady=(0, 15))

        for f in self.folders:
            self.listbox.insert(tk.END, f)

        # Barra Inferior com botão Concluir
        bottom_bar = ctk.CTkFrame(container, fg_color="transparent")
        bottom_bar.pack(fill="x")

        self.lbl_count = ctk.CTkLabel(bottom_bar, text=f"Total configurado: {len(self.folders)} pasta(s)", text_color="gray70")
        self.lbl_count.pack(side="left")

        ctk.CTkButton(
            bottom_bar,
            text="✔ Salvar e Fechar",
            width=150,
            height=34,
            fg_color="#2e7d32",
            hover_color="#1b5e20",
            font=ctk.CTkFont(weight="bold"),
            command=self._save_and_close
        ).pack(side="right")

    def _update_count(self):
        items = list(self.listbox.get(0, tk.END))
        self.lbl_count.configure(text=f"Total configurado: {len(items)} pasta(s)")

    def _add_local_folder(self):
        folder = filedialog.askdirectory(title="Selecione a Pasta Local para Busca")
        if folder:
            norm_folder = str(Path(folder))
            if norm_folder not in self.listbox.get(0, tk.END):
                self.listbox.insert(tk.END, norm_folder)
                self._update_count()

    def _add_unc_folder(self):
        dialog = ctk.CTkInputDialog(
            text="Digite o caminho de rede UNC da intranet:\n(Exemplo: \\\\192.168.1.100\\Pastas\\XML ou \\\\ServidorPDV\\Notas)",
            title="Adicionar Pasta da Intranet"
        )
        unc_path = dialog.get_input()
        if unc_path:
            unc_path = unc_path.strip()
            if unc_path not in self.listbox.get(0, tk.END):
                self.listbox.insert(tk.END, unc_path)
                self._update_count()

    def _remove_folder(self):
        selected = self.listbox.curselection()
        if selected:
            for idx in reversed(selected):
                self.listbox.delete(idx)
            self._update_count()

    def _clear_folders(self):
        self.listbox.delete(0, tk.END)
        self._update_count()

    def _save_and_close(self):
        updated_folders = list(self.listbox.get(0, tk.END))
        self.on_save_callback(updated_folders)
        self.destroy()

class App(ctk.CTk):
    def __init__(self):
        super().__init__()

        self.title("Coletor & Auditor de XML Fiscal (NF-e / NFC-e)")
        self.geometry("1020x720")
        self.minsize(920, 640)

        # Estado e Configuração
        self.config_data = load_config()
        self.source_folders: List[str] = self.config_data.get("source_folders", [])
        self.engine: Optional[CollectorEngine] = None

        self._build_ui()
        self._load_saved_values()

        self.protocol("WM_DELETE_WINDOW", self._on_closing)

    def _build_ui(self):
        # 1. Cabeçalho com Botão de Configuração de Pastas
        self.header_frame = ctk.CTkFrame(self, corner_radius=0, fg_color=("gray85", "gray17"))
        self.header_frame.pack(fill="x", padx=0, pady=0)

        header_top = ctk.CTkFrame(self.header_frame, fg_color="transparent")
        header_top.pack(fill="x", padx=20, pady=(12, 4))

        self.title_label = ctk.CTkLabel(
            header_top,
            text="Coletor & Auditor de XML Fiscal (NF-e / NFC-e)",
            font=ctk.CTkFont(size=20, weight="bold")
        )
        self.title_label.pack(side="left")

        # Botão de Configurações de Pastas no canto superior direito
        self.btn_config_folders = ctk.CTkButton(
            header_top,
            text="⚙ Configurar Pastas de Busca",
            width=210,
            height=32,
            font=ctk.CTkFont(size=12, weight="bold"),
            fg_color="#37474f",
            hover_color="#263238",
            command=self._open_folders_config
        )
        self.btn_config_folders.pack(side="right")

        # Subtítulo com status das pastas configuradas
        self.sub_label = ctk.CTkLabel(
            self.header_frame,
            text="",
            font=ctk.CTkFont(size=12),
            text_color="gray60"
        )
        self.sub_label.pack(anchor="w", padx=20, pady=(0, 10))
        self._update_folders_label()

        # Container Principal com scroll
        self.main_container = ctk.CTkScrollableFrame(self, corner_radius=0, fg_color="transparent")
        self.main_container.pack(fill="both", expand=True, padx=20, pady=10)

        # 2. Seção de Filtros & Destino (agora no topo)
        self._build_filters_section()

        # 3. Painel de Execução & Progresso
        self._build_action_section()

        # 4. Painel de Resultados & Auditoria
        self._build_results_section()

    def _update_folders_label(self):
        qtd = len(self.source_folders)
        if qtd == 0:
            txt = "Nenhuma pasta de busca configurada. Clique em 'Configurar Pastas de Busca' acima para adicionar."
            color = "#e57373"
        elif qtd == 1:
            txt = f"1 pasta de busca configurada: {self.source_folders[0]}"
            color = "gray60"
        else:
            txt = f"{qtd} pastas de busca configuradas (locais e intranet). Clique em 'Configurar Pastas' para gerenciar."
            color = "gray60"
        self.sub_label.configure(text=txt, text_color=color)

    def _open_folders_config(self):
        FoldersConfigWindow(self, self.source_folders, self._on_folders_updated)

    def _on_folders_updated(self, new_folders: List[str]):
        self.source_folders = new_folders
        self.config_data["source_folders"] = new_folders
        save_config(self.config_data)
        self._update_folders_label()

    def _build_filters_section(self):
        filter_box = ctk.CTkFrame(self.main_container)
        filter_box.pack(fill="x", pady=(0, 10))

        # Linha 1: Mês/Ano e Modelos
        row1 = ctk.CTkFrame(filter_box, fg_color="transparent")
        row1.pack(fill="x", padx=15, pady=(12, 6))

        ctk.CTkLabel(row1, text="Mês de Emissão:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")

        self.combo_mes = ctk.CTkComboBox(row1, values=MESES_NOMES, width=160)
        self.combo_mes.pack(side="left", padx=(5, 15))

        ctk.CTkLabel(row1, text="Ano:", font=ctk.CTkFont(weight="bold")).pack(side="left", padx=(0, 5))
        
        ano_atual = date.today().year
        anos_opcoes = [str(a) for a in range(ano_atual - 3, ano_atual + 4)]
        self.combo_ano = ctk.CTkComboBox(row1, values=anos_opcoes, width=100)
        self.combo_ano.pack(side="left", padx=(0, 25))

        self.chk_nfe = ctk.CTkCheckBox(row1, text="NF-e (Mod 55)")
        self.chk_nfe.pack(side="left", padx=10)
        self.chk_nfe.select()

        self.chk_nfce = ctk.CTkCheckBox(row1, text="NFC-e (Mod 65)")
        self.chk_nfce.pack(side="left", padx=10)
        self.chk_nfce.select()

        # Linha 2: CNPJ
        row2 = ctk.CTkFrame(filter_box, fg_color="transparent")
        row2.pack(fill="x", padx=15, pady=6)

        ctk.CTkLabel(row2, text="CNPJ(s) Emitente:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.entry_cnpj = ctk.CTkEntry(
            row2,
            placeholder_text="Ex: 12.345.678/0001-90, 98.765.432/0001-10 (opcional, deixe vazio para todos)",
            font=ctk.CTkFont(size=12)
        )
        self.entry_cnpj.pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Linha 3: Pasta de Destino & Opções
        row3 = ctk.CTkFrame(filter_box, fg_color="transparent")
        row3.pack(fill="x", padx=15, pady=(6, 12))

        ctk.CTkLabel(row3, text="Pasta Destino:", width=130, anchor="w", font=ctk.CTkFont(weight="bold")).pack(side="left")
        self.entry_dest = ctk.CTkEntry(row3, placeholder_text="Selecione o diretório onde o ZIP ou XMLs serão gravados...")
        self.entry_dest.pack(side="left", fill="x", expand=True, padx=(5, 10))

        ctk.CTkButton(row3, text="Procurar...", width=100, command=self._select_dest_folder).pack(side="left", padx=(0, 15))

        self.chk_zip = ctk.CTkCheckBox(row3, text="Gerar pacote .ZIP com relatório incluso")
        self.chk_zip.pack(side="left")
        self.chk_zip.select()

    def _build_action_section(self):
        act_box = ctk.CTkFrame(self.main_container)
        act_box.pack(fill="x", pady=(0, 10))

        row = ctk.CTkFrame(act_box, fg_color="transparent")
        row.pack(fill="x", padx=15, pady=12)

        self.btn_start = ctk.CTkButton(
            row,
            text="▶  Iniciar Coleta e Auditoria",
            height=38,
            width=230,
            font=ctk.CTkFont(size=14, weight="bold"),
            fg_color="#2e7d32",
            hover_color="#1b5e20",
            command=self._start_process
        )
        self.btn_start.pack(side="left", padx=(0, 10))

        self.btn_cancel = ctk.CTkButton(
            row,
            text="⏹ Cancelar",
            height=38,
            width=120,
            font=ctk.CTkFont(size=13),
            fg_color="#c62828",
            hover_color="#8e0000",
            state="disabled",
            command=self._cancel_process
        )
        self.btn_cancel.pack(side="left", padx=(0, 20))

        self.lbl_stats = ctk.CTkLabel(
            row,
            text="Pronto para iniciar.",
            font=ctk.CTkFont(size=13, weight="bold"),
            text_color="gray70"
        )
        self.lbl_stats.pack(side="left", fill="x", expand=True, anchor="w")

        self.progress_bar = ctk.CTkProgressBar(act_box)
        self.progress_bar.pack(fill="x", padx=15, pady=(0, 12))
        self.progress_bar.set(0)

    def _build_results_section(self):
        self.banner_alert = ctk.CTkFrame(self.main_container, fg_color="transparent")
        self.banner_alert.pack(fill="x", pady=(0, 10))

        self.banner_label = ctk.CTkLabel(
            self.banner_alert,
            text="",
            font=ctk.CTkFont(size=14, weight="bold"),
            corner_radius=6,
            height=36
        )

        self.tabview = ctk.CTkTabview(self.main_container, height=320)
        self.tabview.pack(fill="both", expand=True)

        self.tab_audit = self.tabview.add("Auditoria de Sequência")
        self.tab_notes = self.tabview.add("XMLs Coletados")
        self.tab_inut = self.tabview.add("Inutilizações Localizadas")
        self.tab_logs = self.tabview.add("Logs")

        self.txt_audit = ctk.CTkTextbox(self.tab_audit, font=ctk.CTkFont(family="Consolas", size=12))
        self.txt_audit.pack(fill="both", expand=True, padx=5, pady=5)

        self.txt_notes = ctk.CTkTextbox(self.tab_notes, font=ctk.CTkFont(family="Consolas", size=11))
        self.txt_notes.pack(fill="both", expand=True, padx=5, pady=5)

        self.txt_inut = ctk.CTkTextbox(self.tab_inut, font=ctk.CTkFont(family="Consolas", size=11))
        self.txt_inut.pack(fill="both", expand=True, padx=5, pady=5)

        self.txt_logs = ctk.CTkTextbox(self.tab_logs, font=ctk.CTkFont(family="Consolas", size=11))
        self.txt_logs.pack(fill="both", expand=True, padx=5, pady=5)

    def _load_saved_values(self):
        if self.config_data.get("destination_folder"):
            self.entry_dest.insert(0, self.config_data["destination_folder"])

        if self.config_data.get("cnpjs"):
            self.entry_cnpj.insert(0, self.config_data["cnpjs"])

        saved_month = self.config_data.get("selected_month", f"{date.today().month:02d}")
        for opt in MESES_NOMES:
            if opt.startswith(saved_month):
                self.combo_mes.set(opt)
                break

        saved_year = self.config_data.get("selected_year", f"{date.today().year}")
        self.combo_ano.set(saved_year)

        if not self.config_data.get("filter_nfe", True):
            self.chk_nfe.deselect()

        if not self.config_data.get("filter_nfce", True):
            self.chk_nfce.deselect()

        if not self.config_data.get("generate_zip", True):
            self.chk_zip.deselect()

    def _save_current_values(self):
        self.config_data["source_folders"] = self.source_folders
        self.config_data["destination_folder"] = self.entry_dest.get().strip()
        self.config_data["cnpjs"] = self.entry_cnpj.get().strip()
        self.config_data["selected_month"] = self.combo_mes.get()[:2]
        self.config_data["selected_year"] = self.combo_ano.get().strip()
        self.config_data["filter_nfe"] = bool(self.chk_nfe.get())
        self.config_data["filter_nfce"] = bool(self.chk_nfce.get())
        self.config_data["generate_zip"] = bool(self.chk_zip.get())
        save_config(self.config_data)

    def _select_dest_folder(self):
        folder = filedialog.askdirectory(title="Selecione a Pasta de Destino")
        if folder:
            self.entry_dest.delete(0, tk.END)
            self.entry_dest.insert(0, str(Path(folder)))
            self._save_current_values()

    def _log_message(self, message: str):
        now = datetime.now().strftime("%H:%M:%S")
        self.txt_logs.insert(tk.END, f"[{now}] {message}\n")
        self.txt_logs.see(tk.END)

    def _update_progress(self, scanned: int, matched: int, cur_file: str):
        self.lbl_stats.configure(
            text=f"Varrendo: {scanned} verificados | {matched} arquivos casaram com o mês | {cur_file[:35]}"
        )

    def _start_process(self):
        if not self.source_folders:
            messagebox.showwarning(
                "Pastas não configuradas",
                "Nenhuma pasta de busca configurada!\nClique no botão '⚙ Configurar Pastas de Busca' no topo para adicionar as pastas locais ou caminhos de intranet."
            )
            self._open_folders_config()
            return

        dest_path = self.entry_dest.get().strip()
        if not dest_path:
            messagebox.showwarning("Aviso", "Selecione a pasta de destino.")
            return

        filter_nfe = bool(self.chk_nfe.get())
        filter_nfce = bool(self.chk_nfce.get())
        if not filter_nfe and not filter_nfce:
            messagebox.showwarning("Aviso", "Selecione ao menos um modelo fiscal (NF-e ou NFC-e).")
            return

        target_month = self.combo_mes.get()[:2]
        target_year = self.combo_ano.get().strip()

        raw_cnpjs = self.entry_cnpj.get().replace(";", ",").split(",")
        cnpjs_list = [clean_digits(c) for c in raw_cnpjs if clean_digits(c)]

        self._save_current_values()

        self.txt_audit.delete("1.0", tk.END)
        self.txt_notes.delete("1.0", tk.END)
        self.txt_inut.delete("1.0", tk.END)
        self.txt_logs.delete("1.0", tk.END)
        self.banner_label.pack_forget()

        self.btn_start.configure(state="disabled")
        self.btn_cancel.configure(state="normal")
        self.progress_bar.set(0)
        self.progress_bar.start()

        self._log_message(f"Iniciando coleta do mês {target_month}/{target_year}...")

        self.engine = CollectorEngine(
            source_paths=self.source_folders,
            destination_path=dest_path,
            cnpjs=cnpjs_list,
            target_month=target_month,
            target_year=target_year,
            filter_nfe=filter_nfe,
            filter_nfce=filter_nfce,
            generate_zip=bool(self.chk_zip.get()),
            on_progress=lambda s, m, f: self.after(0, self._update_progress, s, m, f),
            on_log=lambda m: self.after(0, self._log_message, m),
            on_finished=lambda res: self.after(0, self._process_finished, res)
        )
        self.engine.start()

    def _cancel_process(self):
        if self.engine:
            self.engine.cancel()
            self.btn_cancel.configure(state="disabled")
            self._log_message("Cancelamento solicitado. Aguardando interrupção...")

    def _process_finished(self, result: dict):
        self.progress_bar.stop()
        self.progress_bar.set(1.0)
        self.btn_start.configure(state="normal")
        self.btn_cancel.configure(state="disabled")

        if result.get("cancelled"):
            self.lbl_stats.configure(text="Operação cancelada pelo usuário.")
            self.banner_label.configure(
                text="  Operação Cancelada  ",
                fg_color="#555555",
                text_color="#ffffff"
            )
            self.banner_label.pack(fill="x")
            return

        total_scanned = result.get("total_scanned", 0)
        total_matched = result.get("total_matched", 0)
        total_inut = result.get("total_inut", 0)
        has_break = result.get("has_sequence_break", False)
        notes = result.get("notes", [])
        inut_records = result.get("inut_records", [])
        audit_list = result.get("audit", [])
        zip_path = result.get("zip_path")

        self.lbl_stats.configure(
            text=f"Concluído! Verificados: {total_scanned} | Notas: {total_matched} | Inutilizações: {total_inut}"
        )

        # Banner de Quebra / Regularização
        if has_break:
            q_count = result.get("quebras_count", 1)
            self.banner_label.configure(
                text=f"  ⚠ ATENÇÃO: Detectada QUEBRA DE SEQUÊNCIA pendente em {q_count} série(s)! Verifique a aba de Auditoria.  ",
                fg_color="#c0392b",
                text_color="#ffffff"
            )
            self.banner_label.pack(fill="x")
            self.tabview.set("Auditoria de Sequência")
        elif total_inut > 0:
            self.banner_label.configure(
                text=f"  ✔ SUCESSO: Sequência regularizada! ({total_inut} arquivo(s) de Inutilização anexados ao pacote).  ",
                fg_color="#1e88e5",
                text_color="#ffffff"
            )
            self.banner_label.pack(fill="x")
        else:
            self.banner_label.configure(
                text="  ✔ SUCESSO: Nenhuma quebra de sequência detectada no mês! Numeração 100% contínua.  ",
                fg_color="#27ae60",
                text_color="#ffffff"
            )
            self.banner_label.pack(fill="x")

        # Preenche Tab Auditoria
        audit_text_lines = []
        for a in audit_list:
            audit_text_lines.append(f"[{a['status']}] CNPJ: {a['cnpj']} | Modelo: {a['modelo_nome']} | Série: {a['serie']}")
            audit_text_lines.append(f"   Faixa: Nota {a['primeiro_numero']} até {a['ultimo_numero']} | Notas Emitidas: {a['total_encontradas']} | Esperadas: {a['total_esperadas']}")
            
            if a.get("teve_inutilizacao"):
                audit_text_lines.append(f"   ✔ Inutilizações encontradas no pacote ({a['qtd_inutilizados']}):")
                for d in a.get("detalhes_inutilizados", []):
                    audit_text_lines.append(f"     - Nota {d['numero']}: Justificativa: '{d['justificativa']}' (Arquivo: {d['arquivo']})")

            if a["tem_quebra"]:
                audit_text_lines.append(f"   ⚠ NÚMEROS FALTANTES SEM JUSTIFICATIVA ({a['qtd_faltantes_reais']}): {a['resumo_faltantes']}")
                if a['qtd_faltantes_reais'] <= 50:
                    audit_text_lines.append(f"   Lista completa: {a['numeros_faltantes']}")
            audit_text_lines.append("-" * 95)

        if not audit_text_lines:
            audit_text_lines.append("Nenhum documento fiscal encontrado para o mês selecionado.")

        self.txt_audit.insert(tk.END, "\n".join(audit_text_lines))

        # Preenche Tab Notas Coletadas
        notes_lines = []
        notes_lines.append(
            f"{'NÚMERO':<10} | {'SÉRIE':<6} | {'MOD':<5} | {'EMISSÃO':<16} | {'AUTORIZAÇÃO':<16} | {'VALOR (R$)':>14} | {'CHAVE DE ACESSO':<46}"
        )
        notes_lines.append("-" * 125)
        for n in notes:
            v_str = f"{n['valor_total']:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
            dt_emi = n.get("data_emissao_str", "")[:16]
            dt_aut = n.get("data_autorizacao_str", "")[:16] or dt_emi
            notes_lines.append(
                f"{n['numero']:<10} | {n['serie']:<6} | {n['modelo']:<5} | {dt_emi:<16} | {dt_aut:<16} | {v_str:>14} | {n['chave']:<46}"
            )
        self.txt_notes.insert(tk.END, "\n".join(notes_lines))

        # Preenche Tab Inutilizações
        inut_lines = []
        inut_lines.append(f"{'ARQUIVO':<40} | {'MOD':<5} | {'SÉRIE':<6} | {'FAIXA INUTILIZADA':<22} | {'CNPJ':<16} | {'JUSTIFICATIVA'}")
        inut_lines.append("-" * 110)
        for i in inut_records:
            faixa = f"Nota {i['nnf_ini']} até {i['nnf_fin']}"
            inut_lines.append(f"{i['filename']:<40} | {i['modelo']:<5} | {i['serie']:<6} | {faixa:<22} | {i['emit_cnpj']:<16} | {i.get('justificativa', '')}")
        if not inut_records:
            inut_lines.append("Nenhum arquivo de inutilização foi necessário ou localizado para este período.")
        self.txt_inut.insert(tk.END, "\n".join(inut_lines))

        # Mensagem final
        msg = f"Varredura finalizada!\n\n"
        msg += f"• Arquivos verificados: {total_scanned}\n"
        msg += f"• Notas fiscais gravadas: {total_matched}\n"
        msg += f"• Inutilizações localizadas e anexadas: {total_inut}\n"
        if has_break:
            msg += f"• ⚠ ALERTA: Permanecem quebras de sequência pendentes!\n"
        elif total_inut > 0:
            msg += f"• Sequência regularizada: os saltos foram cobertos pelas Inutilizações!\n"
        else:
            msg += f"• Sequência numérica: 100% contínua no mês.\n"

        if zip_path:
            msg += f"\nPacote ZIP gerado em:\n{zip_path}"

        if has_break:
            messagebox.showwarning("Aviso de Quebra de Sequência", msg)
        else:
            messagebox.showinfo("Sucesso", msg)

    def _on_closing(self):
        if self.engine and not self.engine.is_cancelled():
            self.engine.cancel()
        self._save_current_values()
        self.destroy()

def main():
    app = App()
    app.mainloop()

if __name__ == "__main__":
    main()
