# Testes e validações

Como rodar os testes do xadrex e as partidas da arena sem depender de ninguém. Tudo passa por um script na raiz, `rodar_testes.py`, que funciona no Windows e no macOS e só usa a biblioteca padrão do Python. Os detalhes da arena (adaptadores, limites do método) estão em `arena/README.md`.

## Pré-requisitos

- Python com o ambiente do projeto. No Windows: `py -m venv .venv` e `.venv\Scripts\python.exe -m pip install -r requirements.txt` (instala `chess==1.11.2`). No macOS, o `python3` precisa ter o `chess` 1.11.2 instalado.
- Stockfish, só para `smoke`, `match`, `lote` e `tudo`. A arena procura nesta ordem:
  1. `--stockfish CAMINHO` passado ao script;
  2. a variável de ambiente `ARENA_STOCKFISH`;
  3. `stockfish` no PATH;
  4. `engines\stockfish-windows-x86-64-universal.exe` (no Windows, basta extrair o `.exe` nessa pasta, como diz o README).

  Para conferir qual caminho vai ser usado: `python3 arena/arena.py --help` (linha do `--stockfish`).
- Para apontar a variável: no PowerShell, `$env:ARENA_STOCKFISH="C:\caminho\stockfish.exe"`; no cmd, `set ARENA_STOCKFISH=C:\caminho\stockfish.exe`; no macOS (fish), `set -x ARENA_STOCKFISH /opt/homebrew/bin/stockfish`; no bash/zsh, `export ARENA_STOCKFISH=/opt/homebrew/bin/stockfish`.

Rode tudo a partir da raiz do repositório.

## Subcomandos

No Windows use `.venv\Scripts\python.exe rodar_testes.py ...`; no macOS, `python3 rodar_testes.py ...`. A opção `--stockfish CAMINHO` vale para smoke, match, lote e tudo.

| subcomando | Windows | macOS | o que mede | duração | quando rodar |
|---|---|---|---|---|---|
| `unit` | `.venv\Scripts\python.exe rodar_testes.py unit` | `python3 rodar_testes.py unit` | `test_tempo.py`, `test_empate.py` e `test_xadrex.py`, cada um num processo; mostra ok ou FALHOU por arquivo | cerca de 10 s | a cada mudança no código |
| `smoke` | `.venv\Scripts\python.exe rodar_testes.py smoke` | `python3 rodar_testes.py smoke` | arena com xadrex x bea e xadrex+ae x fraco, 2 partidas de 1 min cada, sem atraso; confere que tudo abre, joga e termina | estimativa de 5 a 10 min (não medida) | antes de entregar e antes de jogar |
| `smoke --manter` | `.venv\Scripts\python.exe rodar_testes.py smoke --manter` | `python3 rodar_testes.py smoke --manter` | o mesmo, sem apagar `arena/resultados/smoke_<data-hora>/` no fim | idem | quando quiser abrir o PGN do smoke |
| `tudo` | `.venv\Scripts\python.exe rodar_testes.py tudo` | `python3 rodar_testes.py tudo` | `unit` e, se passar, `smoke` | unit + smoke | antes de entregar e antes de jogar |
| `match` | `.venv\Scripts\python.exe rodar_testes.py match` | `python3 rodar_testes.py match` | xadrex x bea em 10+0, atraso 3 a 8 s, seed 2026; `--games N` (padrão 10), `--nome PASTA` | cerca de 40 min para 10 partidas (142 a 271 s por partida no match de 03/11) | depois de mudar `tempo.py` ou a busca |
| `lote` | `.venv\Scripts\python.exe rodar_testes.py lote --nome lote_x` | `python3 rodar_testes.py lote --nome lote_x` | `arena/lote.py`: xadrex e xadrex+ae contra bea e contra fraco; `--games` (padrão 6 por combinação), `--seed` (padrão 2026), `--nome` e as opções do lote (`--base-min`, `--inc-s`, `--delay-min`, `--delay-max`, `--fraco-skill`, `--fraco-tempo`) | 1h30 a 2h30 para 24 partidas (6 por combinação) | para decidir se o anti-empate liga |
| `tabela` | `.venv\Scripts\python.exe rodar_testes.py tabela arena\resultados\lote_ae` | `python3 rodar_testes.py tabela arena/resultados/lote_ae` | monta a tabela do lote a partir das subpastas com `resumo.json`; só lê | instantâneo | lote interrompido ou ainda rodando |

`match` e `lote` mostram a saída na tela e gravam uma cópia em `arena/resultados/<nome>/console.log`. Enquanto o run não termina, a cópia fica ao lado da pasta, em `<nome>.console.log`, porque a arena se recusa a usar uma pasta que já existe. Se `--nome` já existir, o script para antes de começar.

Com o lote ainda rodando, a tabela compara combinações com números diferentes de partidas. Nesse caso a linha "xadrex+ae - xadrex" em pontos 3-1-0 não diz nada; olhe a porcentagem e espere o fim.

## Jogadores da arena

| nome | o que é |
|---|---|
| `xadrex` | o programa real (`xadrex.pensar` e `tempo.py`) com o anti-empate desligado |
| `xadrex+ae` | o mesmo, com `ANTIEMPATE = True` |
| `bea` | o notebook antigo da Bea reimplementado: Stockfish Skill 20, 2 s fixos por lance, Hash 5 GB (adversário forte) |
| `fraco` | Stockfish com Skill Level 5 e 1 s por lance, 1 thread (papel de equipe mais fraca) |

Combinações válidas: qualquer par com um xadrex de um lado e `bea` ou `fraco` do outro, além de `bea` x `fraco`. Inválidas: o mesmo jogador dos dois lados e `xadrex` x `xadrex+ae`. Essa última não roda porque o motor do xadrex e a chave `ANTIEMPATE` são globais no módulo `xadrex.py`: no mesmo processo os dois lados teriam o mesmo valor e jogariam igual. A comparação é indireta, cada variante contra o mesmo adversário e com a mesma seed, que é o que o `lote` faz.

## Como ler os resultados

Cada run grava em `arena/resultados/<nome>/` (no lote, uma subpasta por combinação):

- `partidas.pgn`: as partidas com tempo por lance (`%emt`), relógio (`%clk`) e eventos do xadrex nos comentários.
- `partidas.jsonl`: uma linha por partida, com resultado, motivo e estatísticas de tempo de cada lado.
- `resumo.json`: placar do ponto de vista do jogador A, pontos 3-1-0, Elo com intervalo de confiança e motivos de término. É regravado a cada partida, então um run interrompido guarda o que já foi jogado.
- `console.log` (só via `match` e `lote` deste script) e `tabela.txt` (só no lote completo).

Como ler cada campo:

- Placar `+V =E -D` e pontos 3-1-0: vitória vale 3, empate 1, derrota 0, como no torneio. `10 x 4` quer dizer 10 pontos para A e 4 para B.
- Elo com IC 95%: `+147 [+34, +304]` é a diferença estimada e o intervalo. Se o intervalo inclui zero, não dá para dizer quem é melhor. Com 6 a 10 partidas ele passa fácil de ±200. Com 100% ou 0% aparece `inf`, e só empates dá um intervalo de largura zero; nos dois casos é um limite do método, não precisão.
- Motivos de término: `tempo esgotado (nome)` é bandeira; `tripla repeticao`, `regra dos 50 lances` e `insufficient_material` são empates; `checkmate` é mate. `falha (...)` e `lance ilegal (...)` são derrota de quem falhou e precisam de investigação.

Critério do anti-empate: ligue `XADREX_ANTIEMPATE` no torneio se o `xadrex+ae` não tiver nenhuma derrota a mais que o `xadrex` contra o `bea` e fizer mais pontos 3-1-0 que ele contra o `fraco`. Qualquer derrota para o `fraco`, ou perda por tempo, lance ilegal ou falha que o `xadrex` não teve, é motivo para manter desligado. Uma diferença de 1 ou 2 resultados é ruído.

Antes de culpar o anti-empate por uma derrota, confira se ele desviou naquela partida. Hoje a arena não registra isso: o PGN e o `partidas.jsonl` não trazem a decisão do anti-empate. A marca `antiempate-desviou` só existe no log do programa real, em `logs/`, no campo `parada=` do lance, junto com `antiempate=...decisao:desviou`. Na arena dá para ver apenas indícios no PGN, como a partida sair de uma repetição. Registrar a decisão no PGN da arena fica como pendência.

## Checklist antes da partida

1. Rodar `tudo` no notebook da competição e ver `3/3 arquivos passaram` e o smoke sem `!!`.
2. Testar o leitor de teclas no Windows real, com `.venv\Scripts\python.exe xadrex.py` numa partida de teste:
   - backspace apaga o caractere na tela e no lance;
   - setas são ignoradas, sem aparecer lixo na linha;
   - Enter vazio logo depois do nosso lance marca o relógio e não quebra nada;
   - Ctrl+C no prompt mostra `(use 'sair' para fechar)` e, durante a busca, `Ctrl+C ignorado; recalculando`, sem fechar o programa;
   - esquecer o Enter depois do nosso lance e já digitar o lance do adversário: o lance tem que valer normalmente.
3. Se o leitor falhar em qualquer item, usar a entrada simples. PowerShell: `$env:XADREX_ENTRADA_SIMPLES=1; .venv\Scripts\python.exe xadrex.py`. cmd: `set XADREX_ENTRADA_SIMPLES=1` e depois `.venv\Scripts\python.exe xadrex.py`. Nesse modo a leitura do relógio (`e7e5 12:31`) volta a ser obrigatória a cada 8 lances nossos e abaixo de 2 min.
4. Decidir a chave do anti-empate pelo critério acima. Para ligar, no PowerShell: `$env:XADREX_ANTIEMPATE=1; .venv\Scripts\python.exe xadrex.py`; no cmd: `set XADREX_ANTIEMPATE=1`. Sem a variável, fica desligado.
5. As variáveis valem só para aquela janela do terminal. Abrir um terminal novo volta ao padrão.

## Histórico de execuções

| run | data | resultado | versão | onde |
|---|---|---|---|---|
| match_10min (xadrex x bea, 10 partidas, 10+0, atraso 3 a 8 s, seed 2026) | 03/11 | xadrex +4 =6 -0, Elo +147 [+34, +304]; 3-1-0: 18 x 6 | 5b2428f | `arena/resultados/match_10min/` |
| lote_ae (6 partidas por combinação, seed 2026) | 03/11 | em andamento | `competicao-ajustes` | `arena/resultados/lote_ae/` |
