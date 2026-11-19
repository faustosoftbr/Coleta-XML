import os
import sys
import subprocess
from pathlib import Path

def build():
    print("Iniciando compilação do executável ColetorXMLFiscal.exe...")
    
    cmd = [
        sys.executable,
        "-m",
        "PyInstaller",
        "--noconfirm",
        "--onedir", # we'll first verify onedir or onefile; onefile is requested
        "--onefile",
        "--windowed", # sem janela preta de console
        "--name=ColetorXMLFiscal",
        "--collect-all=customtkinter",
        "--hidden-import=xml.etree.ElementTree",
        "--hidden-import=src",
        "main.py"
    ]
    
    print(f"Executando: {' '.join(cmd)}")
    result = subprocess.run(cmd)
    
    if result.returncode == 0:
        exe_path = Path("dist") / "ColetorXMLFiscal.exe"
        if exe_path.exists():
            size_mb = exe_path.stat().st_size / (1024 * 1024)
            print("\n" + "=" * 60)
            print(">>> SUCESSO: Executável compilado com sucesso!")
            print(f">>> Localização: {exe_path.resolve()}")
            print(f">>> Tamanho: {size_mb:.2f} MB")
            print("=" * 60)
        else:
            print("PyInstaller finalizou, mas o executável não foi encontrado em dist/")
    else:
        print(f"Erro na compilação. Código de saída: {result.returncode}")

if __name__ == "__main__":
    build()
