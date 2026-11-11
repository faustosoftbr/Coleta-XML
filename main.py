import sys
import os

# Garante que o diretório raiz esteja no sys.path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from src.gui import main

if __name__ == "__main__":
    main()
