# Coletor & Auditor de XML Fiscal (NF-e / NFC-e) - Alta Performance

Aplicativo executável desktop para coleta inteligente, validação e auditoria fiscal de arquivos XML de **NF-e (Modelo 55)** e **NFC-e (Modelo 65)**.

---

## ⚡ Por que é ultrarrápido?

Ao varrer pastas locais ou na **Intranet / Rede compartilhada**, o aplicativo não precisa abrir nem ler milhares de arquivos XML na rede:
- O sistema decodifica instantaneamente a **Chave de Acesso SEFAZ de 44 dígitos** presente no próprio nome do arquivo:
  - `[AAMM]` (Ano e Mês de Emissão)
  - `[CNPJ]` (CNPJ do Emitente)
  - `[Modelo]` (55 para NF-e, 65 para NFC-e)
  - `[Série]` e `[Número]` da nota
- Arquivos de outros meses distantes, outros CNPJs ou outros modelos são **descartados instantaneamente em microssegundos (Zero-IO na rede)**.
- Somente as notas que atendem aos filtros são lidas e empacotadas no ZIP.

---

## 🚀 Principais Recursos

1. **Enquadramento pelo Mês de Autorização SEFAZ (`<dhRecbto>`)**:
   - O aplicativo considera a data real em que a nota foi homologada e autorizada na SEFAZ.
   - **Varredura inteligente de borda**: Para manter a eficiência máxima, o sistema avalia os arquivos de virada de mês (dia 01 do mês seguinte e último dia do mês anterior). Assim, notas emitidas por exemplo em `01/11` às `00:30`, mas autorizadas pela SEFAZ em `31/10` às `23:30`, são **automaticamente identificadas e incluídas no mês de outubro**.
   - Ambas as datas (**Emissão** e **Autorização**) são detalhadas na tabela visual e no relatório em texto.

2. **Interface Limpa e Direta**:
   - A listagem de pastas fica acessível através do botão **`⚙ Configurar Pastas de Busca`** no topo. Uma vez configuradas, as pastas permanecem salvas em `config.json`.
   - A tela principal foca diretamente na operação: **Mês/Ano**, **CNPJ**, **Modelos**, **Pasta Destino** e **Iniciar Coleta**.

3. **Varredura Local & Intranet (Rede UNC)**:
   - Suporte a pastas locais e caminhos de rede UNC da intranet (Ex: `\\192.168.1.50\Pastas\XML` ou `\\ServidorPDV\Notas`).
   - Busca recursiva em todas as subpastas.

4. **Auditoria com Busca Inteligente de Inutilizações (`ProcInutNFe`)**:
   - Agrupa as notas por `CNPJ Emitente + Modelo + Série`.
   - Detecta automaticamente qualquer salto na numeração (`<nNF>`).
   - **Se detectar quebra**: faz uma busca direcionada por arquivos de Inutilização que contenham o número faltante (ex: `Inut011-000017156-000017156-Proc.xml`).
   - Anexa o XML da Inutilização ao pacote ZIP e comprova a regularidade na SEFAZ.

5. **Pacote ZIP com Relatório Exclusivo**:
   - Organiza os XMLs em subpastas por `{CNPJ_Emitente}/{Ano-Mês-Autorizacao}/Modelo_{Mod}/`.
   - XMLs de inutilização são arquivados na pasta `Inutilizadas/`.
   - Gera o arquivo **`relatorio_coleta.txt`** exclusivamente dentro do `.zip`, contendo cabeçalho com totais, listagem de notas com datas de emissão e autorização, tabela de inutilizações e auditoria completa da sequência.

---

## 💻 Como Usar o Executável

1. Abra o arquivo **`dist/ColetorXMLFiscal.exe`**.
2. No botão **`⚙ Configurar Pastas de Busca`** (no canto superior direito):
   - Adicione suas pastas locais ou caminhos de intranet (salvo automaticamente).
3. Na tela principal:
   - Escolha o **Mês** e o **Ano** desejados.
   - Digite o(s) CNPJ(s) (opcional).
   - Marque os modelos (`NF-e` e/ou `NFC-e`).
   - Selecione a **Pasta Destino**.
4. Clique em **▶ Iniciar Coleta e Auditoria**.
