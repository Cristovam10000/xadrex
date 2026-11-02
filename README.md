# Xadrex — III Chess Challenge (ICEV 2026)

Programa de linha de comando que joga xadrez offline: recebe os lances do adversário em UCI,
decide os próprios lances e grava o log exigido pela organização.

## Declaração de base (credenciamento)

| Item | Valor |
| --- | --- |
| Motor de busca/avaliação | Stockfish 19, tag `sf_19`, commit `edb0d9db6731067ec50ce619ff372b463bc4dd5d`, **sem modificações**, executado como processo separado via UCI |
| Binário | `stockfish-windows-x86-64-universal.exe` (release oficial) |
| Licença do motor | GPLv3 — `engines/STOCKFISH-LICENSE.txt`; código-fonte em https://github.com/official-stockfish/Stockfish/tree/sf_19 |
| Biblioteca de tabuleiro | `chess` (python-chess) 1.11.2 — representação e legalidade dos lances |
| Autoria da equipe | Gestão de tempo (em desenvolvimento) |
| Book / tablebase / GPU | Não utilizados |

## Instalação (feita antes do evento, com internet)

Requer Python 3.14 no Windows (`py`).

```powershell
py -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements.txt
```

Baixe o motor e confira o SHA-256 antes de extrair o `.exe` para `engines/`:

- URL: https://github.com/official-stockfish/Stockfish/releases/download/sf_19/stockfish-windows-x86-64-universal.zip
- SHA-256 do `.zip`: `3c8bf1f9ea66a09350a40df4f632288285ac206d99f33ab5842c408fc30b48a7`

```powershell
Get-FileHash .\stockfish-windows-x86-64-universal.zip -Algorithm SHA256
```

O `.exe` (103 MB) não fica no repositório porque excede o limite de arquivo do GitHub.
