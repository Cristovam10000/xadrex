# Arena

Partidas automáticas entre dois jogadores, com relógio, atraso humano simulado e as regras de fim de jogo do edital. Serve para comparar versões com evidência em vez de impressão. O uso de agora é validar o anti-empate (`xadrex.ANTIEMPATE`) antes de ligá-lo na competição.

## Jogadores

| nome | o que é | papel |
|---|---|---|
| `xadrex` | o programa real (`xadrex.pensar`, `tempo.py`) com `ANTIEMPATE = False` | versão de referência |
| `xadrex+ae` | o mesmo, com `ANTIEMPATE = True` | versão testada |
| `bea` | o notebook antigo da Bea reimplementado (Skill 20, 2 s fixos por lance, Hash 5 GB) | adversário forte |
| `fraco` | Stockfish com Skill Level baixo (padrão 5), tempo fixo curto (padrão 1 s), 1 thread | equipes mais fracas |

`xadrex` contra `xadrex+ae` não roda: o motor do xadrex é global no módulo e `ANTIEMPATE` valeria para os dois lados. A arena recusa essa combinação (e também o mesmo jogador dos dois lados).

## Como rodar uma combinação

Da raiz do repositório, com o ambiente do xadrex (precisa do `python-chess`):

```
python3 arena/arena.py --a xadrex --b bea --games 10 --base-min 10 --inc-s 0 --seed 2026 --nome match_10min
```

No Windows, troque `python3` por `.venv\Scripts\python.exe`. O Stockfish é procurado nesta ordem: `--stockfish CAMINHO`, variável `ARENA_STOCKFISH`, `stockfish` no PATH e, por último, o `.exe` em `engines/`. O `--help` mostra qual caminho vai ser usado.

Opções principais:

- `--a`, `--b`: jogadores (padrão `--a xadrex --b bea`). O placar é sempre do ponto de vista de A.
- `--fraco-skill N` (0 a 20, padrão 5) e `--fraco-tempo S` (padrão 1.0): força do `fraco`.
- `--games`, `--base-min`, `--inc-s`, `--delay-min`, `--delay-max` (0 desliga o atraso), `--seed`, `--nome`.

Teste rápido (2 partidas de 1 min, sem atraso, poucos minutos):

```
python3 arena/arena.py --a xadrex+ae --b fraco --games 2 --base-min 1 --delay-max 0 --nome smoke
```

Se o `xadrex.py` ainda não define `ANTIEMPATE`, a arena avisa no início: o atributo é atribuído mesmo assim, mas não tem efeito, e o `xadrex+ae` joga como o `xadrex`.

## Lote do anti-empate (`lote.py`)

Roda em sequência as 4 combinações (`xadrex` e `xadrex+ae` contra `bea` e contra `fraco`) com a mesma seed, as mesmas aberturas e os mesmos parâmetros. Cada combinação é um processo separado da arena. No fim imprime e grava em `tabela.txt` uma linha por combinação (W/D/L, pontos 3-1-0, porcentagem e Elo com IC 95%), a diferença de pontos entre `xadrex+ae` e `xadrex` contra cada adversário e os motivos de término.

```
python3 arena/lote.py --games 6 --seed 2026 --nome lote_ae
```

Padrões: 10+0, atraso 3–8 s, fraco com Skill 5 e 1 s. A seed, se não for passada, é sorteada uma vez e usada nas 4 combinações. O tempo de parede de uma partida 10+0 fica em torno de 2 a 5 min (o atraso humano é descontado do relógio, não esperado).

## O que gera

Em `arena/resultados/<nome>/` (no lote, uma subpasta por combinação):

- `partidas.pgn`: as partidas, com tempo de cada lance (`%emt`), relógio (`%clk`) e eventos do xadrex nos comentários (`humano=` é a parte humana do lance anterior que o relógio automático ensinou ao gestor).
- `partidas.jsonl`: uma linha por partida (resultado, motivo, estatísticas de tempo de cada lado).
- `resumo.json`: placar do ponto de vista de A, pontos 3-1-0 dos dois lados, Elo com intervalo de 95%, tudo também separado por cor, e contagem dos motivos de fim. Em `config.antiempate_no_modulo` fica registrado se o `xadrex.py` definia `ANTIEMPATE` no momento do run.

Só `arena/resultados/match_10min/` vai para o Git (evidência do match de 03/11/2026, gravada com a versão antiga da arena e por isso com as chaves `xadrex_de_brancas`/`pontos_xadrex` em vez de `a_de_brancas`/`pontos_a`). Os outros runs são ignorados.

## O que cada adaptador reproduz (`modelos.py`)

- `Bea`: reimplementa a célula 0 de `chess-challenge/code/index.ipynb` (o notebook não pode ser importado). Um processo do Stockfish por partida, a cada lance Skill Level 20, Move Overhead 15, Hash 5120 e busca fixa de 2 s.
- `Fraco`: um processo do Stockfish por partida, Threads 1, Skill Level e tempo fixos. Não imita nenhum programa real.
- `Xadrex(antiempate)`: chama o código real (`xadrex.pensar`, `xadrex.leitura_obrigatoria`, `xadrex.calibrar`, `tempo.fechar_lance`) e segue o fluxo do relógio automático (commits f091a20 e 215637e). O relógio em que `pensar` se baseia é o relógio da arena, e a parte humana de cada lance é ensinada ao `AtrasoHumano`, como no ENTER ao bater o relógio. A leitura do relógio físico só acontece quando `leitura_obrigatoria` pede (antes do 1º lance com menos de 2 min), simulada com o relógio da arena truncado em segundos. Nada é gravado em `partida_atual.json` nem em `logs/`. A contagem antiga (atraso médio estimado por lance, `k += 1`) foi removida; quem precisar dela encontra no commit 1fa1223.

Todos usam o mesmo binário do Stockfish.

## Limites e como ler o resultado

- **Comparação indireta.** As duas variantes nunca se enfrentam. O que se compara é o desempenho de cada uma contra o mesmo adversário, com a mesma seed e as mesmas aberturas.
- **A seed não repete as partidas.** Ela fixa as aberturas e a sequência do atraso humano, mas o tempo de busca de cada lance varia, então as partidas divergem cedo. As duas variantes não jogam "a mesma partida com um lance diferente".
- **Amostra pequena não dá significância.** Com 6 partidas por combinação e resultados mistos, o IC do Elo passa de ±200 (só empates dá IC de largura zero, artefato do método, não precisão). Uma diferença de 1 ou 2 resultados entre as variantes é ruído. O lote serve para pegar regressão grosseira e para ver se o mecanismo dispara, não para provar ganho.
- **Sinal de regressão** (motivo para não ligar o anti-empate): `xadrex+ae` com alguma derrota contra o `bea` onde o `xadrex` não perdeu nenhuma, menos pontos 3-1-0 que o `xadrex` contra o `fraco`, qualquer derrota para o `fraco`, ou perdas por tempo, lance ilegal ou falha que o `xadrex` não teve. Sinal a favor: contra o `fraco`, empates do `xadrex` (repetição, 50 lances) virando vitórias sem derrotas novas. Contra o `bea` (Stockfish forte), desviar do empate costuma virar derrota (D5 do diário): ali o critério é não perder mais que o `xadrex`.
- O relógio automático é simulado com medição perfeita: o erro de `OUVIR_MS` (risco D7 do diário) e o ENTER esquecido não entram. Na arena toda a parte humana vem depois do lance.
- O atraso humano é sorteado de forma uniforme entre `--delay-min` e `--delay-max` (padrão 3–8 s), não medido de uma equipe real.
- As partidas começam depois de aberturas fixas (10 linhas, cada uma jogada com as duas cores), fora do relógio.
