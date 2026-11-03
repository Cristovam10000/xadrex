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
| Autoria da equipe | Gestão de tempo — `tempo.py` (ver seção abaixo); integração e controle da busca em `xadrex.py` |
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

## Uso na partida

```powershell
.venv\Scripts\python.exe xadrex.py
```

Informe nossa cor, tempo base e incremento. O padrão é 10 min + 0 s (Errata nº 01): sem incremento, relógio
físico (confirmado com a organização). No turno do adversário, digite o lance
anunciado em UCI (`e2e4`, `e7e8q`). Nosso lance aparece como `>>> NOSSO LANCE: ...`.

| Comando | Efeito |
| --- | --- |
| `e7e5` | lance do adversário |
| `e7e5 12:31` | lance do adversário + leitura do nosso relógio físico naquele momento (calibra o gestor de tempo). **Obrigatória** quando o relógio estimado está abaixo de 2 min, a cada 8 lances sem leitura e depois de `u` |
| `u` | desfaz nosso último lance e o do adversário (corrigir digitação) |
| `tab` | mostra tabuleiro e lista de lances |
| `sair` | fecha; a partida é retomada ao rodar de novo (pergunta o relógio atual) |
| `fim` | encerra a partida (abandono, tempo, empate acordado) |

O log de cada partida fica em `logs/`: por lance, número, cor, UCI, profundidade, nós, avaliação, PV, tempo
gasto e as decisões do gestor (alvo, máximo, motivo da parada, atraso humano estimado).

Testes: `.venv\Scripts\python.exe test_tempo.py` e `.venv\Scripts\python.exe test_xadrex.py`.

## Gestor de tempo (autoria da equipe)

O Stockfish decide **qual** lance jogar; `tempo.py` decide **por quanto tempo** ele pensa. O gestor do próprio
Stockfish não sabe que, numa partida com tabuleiro físico, o nosso relógio também corre enquanto o operador
digita o lance adversário, anuncia o nosso, move a peça e aperta o relógio. Nos testes com o gestor dele e um
atraso humano fixo de 5 s, ele gastou 13 s com 24 s no relógio.

1. **Atraso humano aprendido** (`AtrasoHumano`). Quando o operador digita a leitura do relógio físico junto
   com o lance adversário, o programa compara com o relógio que tinha previsto; a diferença por lance é uma
   amostra do custo humano. A estimativa usa o algoritmo do tempo de retransmissão do TCP (RFC 6298):
   média suavizada (1/8) e desvio suavizado (1/4); a reserva de segurança é média + 4 × desvio (mínimo 3 s).
   Sem leitura, o erro da previsão acumula a cada lance; por isso a leitura passa a ser obrigatória a cada
   8 lances, com relógio abaixo de 2 min e depois de desfazer. Leitura impossível (maior que a previsão mais
   o atraso já descontado) é recusada — ex.: `2:00` digitado no lugar de `0:20`.
2. **Orçamento por lance** (`orcamento`). Reserva o custo humano do lance atual; distribui o resto por um
   horizonte de lances que depende da fase (material) e de haver saldo de incremento; soma ao alvo o saldo
   do incremento (incremento − atraso humano), que é **negativo** sem incremento; aplica rampa de abertura;
   o máximo nunca passa de 30% do tempo disponível.
3. **Controle da busca** (`ControleBusca`). A cada iteração completa do Stockfish: troca recente do melhor
   lance estende o alvo (até 3×), queda da avaliação em relação à busca anterior estende (até 2×), melhor
   lance estável por 8 iterações encurta (0,6×); para na hora em lance único e mate encontrado. Se o motor
   não responder ao `stop` (até 3 s além do máximo, nunca além do que o relógio permite), o programa o mata
   e joga o melhor lance da última iteração completa. Tempo já gasto antes da busca é descontado.

Evidência: `test_tempo.py` simula partidas com a mesma contagem do programa (o gestor só conhece o relógio
previsto; leitura só quando exigida, com erro de até 1 s) e atraso humano aleatório: sem perdas por tempo
em 10+0 com 60 lances nossos (equipe com 3–8 s por lance), 15+10 com 120 lances (equipe com 3–8 s e equipe
lenta com 6–10 s), 25+0 com 80 lances e Armageddon (5 e 4 min). Limite conhecido: em 10+0 com 80 lances nossos
a simulação perde por tempo em 19 de 50 partidas. O horizonte sem incremento foi escolhido nessa simulação: com a primeira versão,
todas as 30 partidas 25+0 de 80 lances perdiam por tempo.
