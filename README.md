# Coletor XML Fiscal

Este repositório contém o **Coletor XML Fiscal**, um utilitário Python que:

- Varre diretórios em busca de arquivos XML de notas fiscais (NF‑e 55 e NFC‑e 65).
- Filtra por CNPJ, data de autorização da SEFAZ e modelo.
- Audita quebras de sequência numérica e inclui informações de inutilizações.
- Gera um relatório de texto e um relatório Excel (baseado no modelo fornecido).
- Empacota tudo em um único arquivo **ZIP** contendo:
  - Pasta `Arquivos/` com todos os XMLs coletados.
  - Subpasta `Arquivos/Relatório/` com o Excel.
  - Relatório de texto (`relatorio_coleta.txt`).
- Possui um script `build_exe.py` que usa **PyInstaller** para gerar o executável `ColetorXMLFiscal.exe`.

## Estrutura de pastas

```
Coletor XML pastas FiscaMan/
├── src/                     # código fonte
│   ├── collector.py         # engine de coleta
│   ├── xml_parser.py        # parsing de XMLs
│   ├── exporter.py          # geração de relatório txt
│   └── ...
├── tests/                   # testes unitários
├── build_exe.py             # script de compilação com PyInstaller
├── requirements.txt         # dependências
├── README.md                # este arquivo
├── LICENSE                  # licença MIT
└── .gitignore               # arquivos a serem ignorados
```

## Como usar

### 1. Preparar o ambiente

```bash
# Clone o repositório (quando estiver no GitHub)
# git clone <url>
cd "Coletor XML pastas FiscaMan"

# Crie e ative um virtualenv
python3 -m venv .venv
source .venv/bin/activate

# Instale as dependências
pip install --upgrade pip
pip install -r requirements.txt
```

### 2. Executar a coleta

O programa principal está em `main.py`. Ele abre a interface gráfica (CustomTkinter). Você pode rodar:

```bash
python main.py
```

### 3. Gerar o executável (opcional)

```bash
python build_exe.py   # o .exe será colocado em ./dist/
```

### 4. Resultados

Após a execução, o ZIP será criado no diretório de destino configurado na interface. O ZIP conterá a estrutura descrita acima.

## Contribuição

1. Fork o repositório.
2. Crie uma branch para sua feature (`git checkout -b feature/XYZ`).
3. Commit suas mudanças (`git commit -m "Add XYZ"`).
4. Abra um Pull Request.

## Licença

Este projeto está licenciado sob a licença MIT – veja o arquivo `LICENSE` para detalhes.
