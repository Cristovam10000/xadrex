# Arena

Partidas automáticas entre o xadrex e o programa antigo da Bea (notebook do chess-challenge), com relógio, atraso humano simulado e as regras de fim de jogo do edital. Serve para comparar versões com evidência em vez de impressão.

## Como rodar

Da raiz do repositório, com o ambiente do xadrex (precisa do `python-chess`):

```
python3 arena/arena.py --games 10 --base-min 10 --inc-s 0 --seed 2026 --nome match_10min
```

No Windows, troque `python3` por `.venv\Scripts\python.exe`. O Stockfish é procurado nesta ordem: `--stockfish CAMINHO`, variável `ARENA_STOCKFISH`, `stockfish` no PATH e, por último, o `.exe` em `engines/`. O `--help` mostra qual caminho vai ser usado.

Teste rápido (2 partidas de 1 min, sem atraso, cerca de 3 min):

```
python3 arena/arena.py --games 2 --base-min 1 --delay-max 0 --nome smoke
```

## O que gera

Em `arena/resultados/<nome>/`:

- `partidas.pgn`: as partidas, com tempo de cada lance (`%emt`), relógio (`%clk`) e eventos do xadrex nos comentários.
- `partidas.jsonl`: uma linha por partida (resultado, motivo, estatísticas de tempo de cada lado).
- `resumo.json`: placar do ponto de vista do xadrex, Elo com intervalo de 95%, separado por cor, e contagem dos motivos de fim.

Só `arena/resultados/match_10min/` vai para o Git (evidência do match de 03/11/2026). Os outros runs são ignorados.

## O que cada adaptador reproduz (`modelos.py`)

- `Bea`: reimplementa a célula 0 de `chess-challenge/code/index.ipynb` (o notebook não pode ser importado). Um processo do Stockfish por partida, a cada lance Skill Level 20, Move Overhead 15, Hash 5120 e busca fixa de 2 s.
- `Xadrex`: chama o código real (`xadrex.pensar`, `tempo.py`) e espelha a contagem de relógio de `jogar_nosso_lance`. A leitura do relógio físico é simulada com o relógio da arena truncado em segundos. Nada é gravado em `partida_atual.json` nem em `logs/`.

Os dois usam o mesmo binário do Stockfish.

## Limites conhecidos

- A seed fixa as aberturas e o atraso humano, mas não o tempo de busca de cada lance. Rodar de novo com a mesma seed não repete as partidas.
- O adaptador `Xadrex` ainda replica a contagem de relógio antiga, de antes do commit f091a20 (relógio automático). Ele não mede o relógio automático. A seção "Arena" de `docs/diario-de-bordo.md` diz o que mudar.
- O atraso humano é sorteado de forma uniforme entre `--delay-min` e `--delay-max` (padrão 3–8 s), não medido de uma equipe real.
- As partidas começam depois de aberturas fixas (10 linhas, cada uma jogada com as duas cores), fora do relógio.
