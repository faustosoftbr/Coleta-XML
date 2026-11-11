from datetime import datetime
from typing import List, Dict, Any

def generate_txt_report(
    notes: List[Dict[str, Any]],
    inut_records: List[Dict[str, Any]],
    sequence_audit: List[Dict[str, Any]],
    search_params: Dict[str, Any]
) -> str:
    """
    Gera o conteúdo textual formatado do relatório de coleta fiscal e auditoria de sequência,
    incluindo notas emitidas, data de emissão e de autorização SEFAZ, e inutilizações.
    """
    agora_str = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
    total_notas = len(notes)
    total_inut = len(inut_records)
    valor_total_soma = sum(n.get("valor_total", 0.0) for n in notes)
    
    cnpjs_str = search_params.get("cnpjs_str", "Todos")
    periodo_str = search_params.get("data_ini", "Não informado")
    modelos_str = search_params.get("modelos_str", "NF-e e NFC-e")

    linhas = []
    linhas.append("=" * 130)
    linhas.append("                    RELATÓRIO DE COLETA E AUDITORIA FISCAL (XML NFe / NFCe)")
    linhas.append("=" * 130)
    linhas.append(f"Data e Hora da Coleta       : {agora_str}")
    linhas.append(f"CNPJ(s) Filtrados           : {cnpjs_str}")
    linhas.append(f"Mês de Referência (SEFAZ)   : {periodo_str} (Baseado na Data de Autorização <dhRecbto>)")
    linhas.append(f"Modelos Pesquisados         : {modelos_str}")
    linhas.append(f"Total de Notas Gravadas     : {total_notas}")
    linhas.append(f"Total de Inutilizações (XML): {total_inut}")
    linhas.append(f"Valor Total Acumulado       : R$ {valor_total_soma:,.2f}".replace(",", "X").replace(".", ",").replace("X", "."))
    linhas.append("=" * 130)
    linhas.append("")
    
    # 1. LISTAGEM DETALHADA DAS NOTAS
    linhas.append("-" * 130)
    linhas.append("1. LISTAGEM DAS NOTAS FISCAIS GRAVADAS NO PACOTE (ORDENADAS POR MODELO / SÉRIE / NÚMERO)")
    linhas.append("-" * 130)
    
    header_table = (
        f"{'NÚMERO':<10} | {'SÉRIE':<6} | {'MOD':<5} | {'EMISSÃO':<16} | {'AUTORIZAÇÃO':<16} | "
        f"{'VALOR (R$)':>14} | {'CHAVE DE ACESSO':<46} | {'CNPJ EMITENTE':<14}"
    )
    linhas.append(header_table)
    linhas.append("-" * 130)
    
    notas_ordenadas = sorted(notes, key=lambda x: (x.get("modelo", ""), str(x.get("serie", "")), x.get("numero", 0)))
    
    for n in notas_ordenadas:
        num = str(n.get("numero", ""))
        serie = str(n.get("serie", ""))
        mod = str(n.get("modelo", ""))
        dt_emi = n.get("data_emissao_str", "")[:16]
        dt_aut = n.get("data_autorizacao_str", "")[:16] or dt_emi
        v_str = f"{n.get('valor_total', 0.0):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        chave = n.get("chave", "")
        cnpj_emit = n.get("emit_cnpj", "")
        
        linha = f"{num:<10} | {serie:<6} | {mod:<5} | {dt_emi:<16} | {dt_aut:<16} | {v_str:>14} | {chave:<46} | {cnpj_emit:<14}"
        linhas.append(linha)
        
    linhas.append("-" * 130)
    linhas.append("")

    # 2. LISTAGEM DAS INUTILIZAÇÕES LOCALIZADAS
    if inut_records:
        linhas.append("-" * 130)
        linhas.append("2. ARQUIVOS DE INUTILIZAÇÃO (PROCINUTNFE) ANEXADOS AO PACOTE")
        linhas.append("-" * 130)
        linhas.append(f"{'ARQUIVO':<42} | {'MOD':<5} | {'SÉRIE':<6} | {'FAIXA INUTILIZADA':<22} | {'CNPJ':<16} | {'JUSTIFICATIVA'}")
        linhas.append("-" * 130)
        for i in inut_records:
            faixa = f"Nota {i['nnf_ini']} até {i['nnf_fin']}"
            arq = i["filename"][:40]
            just = i.get("justificativa", "")[:40]
            linhas.append(f"{arq:<42} | {i['modelo']:<5} | {i['serie']:<6} | {faixa:<22} | {i['emit_cnpj']:<16} | {just}")
        linhas.append("-" * 130)
        linhas.append("")

    # 3. AUDITORIA DE QUEBRAS DE SEQUÊNCIA NUMÉRICA
    linhas.append("=" * 130)
    linhas.append("3. AUDITORIA DE QUEBRA DE SEQUÊNCIA NUMÉRICA")
    linhas.append("=" * 130)
    
    quebras_reais = [audit for audit in sequence_audit if audit.get("tem_quebra")]
    regularizadas = [audit for audit in sequence_audit if audit.get("teve_inutilizacao")]

    if not sequence_audit:
        linhas.append("Nenhuma nota fiscal encontrada para auditar sequência.")
    else:
        if regularizadas:
            linhas.append(f">>> NOTA: Foram localizadas Inutilizações que regularizaram saltos de numeração:\n")
            for r in regularizadas:
                linhas.append(f"  • CNPJ {r['cnpj']} | Modelo {r['modelo_nome']} | Série {r['serie']}:")
                for d in r.get("detalhes_inutilizados", []):
                    linhas.append(f"    - Número {d['numero']}: INUTILIZADO (Arquivo: {d['arquivo']} | Justificativa: {d['justificativa']})")
            linhas.append("")

        if not quebras_reais:
            linhas.append(">>> SUCESSO: NENHUMA QUEBRA DE SEQUÊNCIA PENDENTE! Todas as numerações estão contínuas ou justificadas por Inutilização.")
        else:
            linhas.append(f">>> ATENÇÃO: FORAM DETECTADAS QUEBRAS PENDENTES EM {len(quebras_reais)} SÉRIE(S)/MODELO(S)!\n")
            for q in quebras_reais:
                linhas.append(f"* CNPJ: {q['cnpj']} ({q.get('emit_nome', 'Não identificado')})")
                linhas.append(f"  Modelo: {q['modelo_nome']} | Série: {q['serie']}")
                linhas.append(f"  Faixa Analisada: Nota {q['primeiro_numero']} até {q['ultimo_numero']}")
                linhas.append(f"  Encontradas: {q['total_encontradas']} notas | Esperadas: {q['total_esperadas']} notas")
                linhas.append(f"  Total de Números Faltantes Sem Justificativa: {q['qtd_faltantes_reais']}")
                linhas.append(f"  Intervalo(s) Ausente(s): {q['resumo_faltantes']}")
                
                if q['qtd_faltantes_reais'] <= 100:
                    faltantes_list = ", ".join(str(n) for n in q['numeros_faltantes'])
                    linhas.append(f"  Lista de Números Ausentes: {faltantes_list}")
                else:
                    faltantes_list = ", ".join(str(n) for n in q['numeros_faltantes'][:50])
                    linhas.append(f"  Primeiros 50 Números Ausentes: {faltantes_list} ... (verifique os intervalos acima)")
                linhas.append("-" * 90)
            
    linhas.append("\n" + "=" * 130)
    linhas.append("Fim do Relatório.")
    linhas.append("=" * 130)
    
    return "\n".join(linhas)
