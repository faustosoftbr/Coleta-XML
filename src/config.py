import json
import os
from pathlib import Path
from typing import Dict, Any
from datetime import date

CONFIG_FILE_NAME = "config.json"

def get_config_path() -> Path:
    """Retorna o caminho do arquivo de configuração na pasta do executável ou projeto."""
    return Path(os.getcwd()) / CONFIG_FILE_NAME

def load_config() -> Dict[str, Any]:
    """Carrega as configurações salvas ou retorna valores padrão."""
    hoje = date.today()
    default_config = {
        "source_folders": [],
        "destination_folder": "",
        "cnpjs": "",
        "filter_nfe": True,
        "filter_nfce": True,
        "generate_zip": True,
        "selected_month": f"{hoje.month:02d}",
        "selected_year": f"{hoje.year}"
    }
    
    cfg_path = get_config_path()
    if cfg_path.exists():
        try:
            with open(cfg_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                default_config.update(data)
        except Exception:
            pass
            
    return default_config

def save_config(config_data: Dict[str, Any]) -> None:
    """Salva as configurações do usuário."""
    cfg_path = get_config_path()
    try:
        with open(cfg_path, "w", encoding="utf-8") as f:
            json.dump(config_data, f, indent=4, ensure_ascii=False)
    except Exception:
        pass
