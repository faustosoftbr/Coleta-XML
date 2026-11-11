from typing import List, Dict, Any, Tuple, Optional

def format_number_ranges(numbers: List[int]) -> str:
    """
    Formata uma lista de números faltantes em intervalos legíveis.
    Ex: [3, 4, 5, 8, 10, 11] -> '3 a 5, 8, 10 a 11'
    """
    if not numbers:
        return ""
    
    ranges = []
    start = numbers[0]
    prev = numbers[0]
    
    for n in numbers[1:]:
        if n == prev + 1:
            prev = n
        else:
            if start == prev:
                ranges.append(str(start))
            else:
                ranges.append(f"{start} a {prev}")
            start = n
            prev = n
            
    if start == prev:
        ranges.append(str(start))
    else:
        ranges.append(f"{start} a {prev}")
        
    return ", ".join(ranges)

def analyze_sequences(
    notes: List[Dict[str, Any]],
    inut_records: Optional[List[Dict[str, Any]]] = None
) -> List[Dict[str, Any]]:
    """
    Agrupa as notas por (CNPJ Emitente, Modelo, Série) e identifica quebras na numeração.
    Leva em conta eventos de inutilização (ProcInutNFe) para regularizar números faltantes.
    """
    inut_records = inut_records or []
    groups: Dict[Tuple[str, str, str], Dict[str, Any]] = {}
    
    # 1. Agrupa notas fiscais regulares
    for note in notes:
        cnpj = note.get("emit_cnpj", "")
        modelo = note.get("modelo", "")
        serie = str(note.get("serie", "0"))
        
        group_key = (cnpj, modelo, serie)
        if group_key not in groups:
            groups[group_key] = {
                "cnpj": cnpj,
                "modelo": modelo,
                "modelo_nome": "NF-e (55)" if modelo == "55" else ("NFC-e (65)" if modelo == "65" else f"Mod {modelo}"),
                "serie": serie,
                "emit_nome": note.get("emit_nome", ""),
                "numeros_set": set(),
                "notas": []
            }
            
        groups[group_key]["numeros_set"].add(note["numero"])
        groups[group_key]["notas"].append(note)
        if not groups[group_key]["emit_nome"] and note.get("emit_nome"):
            groups[group_key]["emit_nome"] = note.get("emit_nome")

    # Mapeia inutilizações por grupo (cnpj, modelo, serie)
    inuts_by_group: Dict[Tuple[str, str, str], List[Dict[str, Any]]] = {}
    for inut in inut_records:
        k = (inut.get("emit_cnpj", ""), inut.get("modelo", ""), str(inut.get("serie", "0")))
        if k not in inuts_by_group:
            inuts_by_group[k] = []
        inuts_by_group[k].append(inut)

    results = []
    for (cnpj, modelo, serie), data in groups.items():
        numeros = sorted(list(data["numeros_set"]))
        if not numeros:
            continue
            
        min_num = numeros[0]
        max_num = numeros[-1]
        qtd_encontradas = len(numeros)
        
        # Identifica todos os saltos numéricos brutos
        numeros_set = data["numeros_set"]
        saltos_brutos = []
        for n in range(min_num, max_num + 1):
            if n not in numeros_set:
                saltos_brutos.append(n)
                
        # Verifica quais saltos são cobertos por Inutilizações
        inuts_do_grupo = inuts_by_group.get((cnpj, modelo, serie), [])
        numeros_inutilizados = []
        detalhes_inutilizados = []
        numeros_faltantes_reais = []
        
        for n in saltos_brutos:
            inut_match = None
            for item in inuts_do_grupo:
                if item["nnf_ini"] <= n <= item["nnf_fin"]:
                    inut_match = item
                    break
            
            if inut_match:
                numeros_inutilizados.append(n)
                detalhes_inutilizados.append({
                    "numero": n,
                    "arquivo": inut_match["filename"],
                    "justificativa": inut_match.get("justificativa", ""),
                    "motivo": inut_match.get("motivo", "")
                })
            else:
                numeros_faltantes_reais.append(n)

        tem_quebra_real = len(numeros_faltantes_reais) > 0
        teve_inutilizacao = len(numeros_inutilizados) > 0
        
        if tem_quebra_real:
            status = "QUEBRA PENDENTE"
        elif teve_inutilizacao:
            status = "REGULARIZADA (Com Inutilizações)"
        else:
            status = "OK (Contínua)"

        results.append({
            "cnpj": cnpj,
            "emit_nome": data["emit_nome"],
            "modelo": modelo,
            "modelo_nome": data["modelo_nome"],
            "serie": serie,
            "primeiro_numero": min_num,
            "ultimo_numero": max_num,
            "total_encontradas": qtd_encontradas,
            "total_esperadas": (max_num - min_num + 1),
            "status": status,
            "tem_quebra": tem_quebra_real,
            "teve_inutilizacao": teve_inutilizacao,
            "qtd_faltantes_reais": len(numeros_faltantes_reais),
            "numeros_faltantes": numeros_faltantes_reais,
            "resumo_faltantes": format_number_ranges(numeros_faltantes_reais) if tem_quebra_real else "Nenhuma quebra pendente",
            "qtd_inutilizados": len(numeros_inutilizados),
            "numeros_inutilizados": numeros_inutilizados,
            "detalhes_inutilizados": detalhes_inutilizados
        })
        
    results.sort(key=lambda x: (x["cnpj"], x["modelo"], x["serie"]))
    return results
