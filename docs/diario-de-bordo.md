# Diário de bordo — ajustes para o Chess Challenge III

Leia este arquivo primeiro se for continuar o trabalho (pessoa ou agente). Ele diz o que já foi feito, o que foi decidido e por quê, e qual é o próximo passo.

- Branch de trabalho: `competicao-ajustes` (nada foi enviado ao remoto; o merge na `main` é decisão da equipe).
- Prazos: código via Git para a organização em **04/11/2026**; competição em **06/11/2026**.
- Equipe: Bea e Cristovam (mesma equipe).

## Documentos de referência

| Arquivo | O que é |
| --- | --- |
| `docs/edital-chess-challenge-iii.md` | Regulamento consolidado com a Errata nº 01 (10 min por equipe). |
| `docs/prompt-evolucao-modelo.md` | Instruções de trabalho: diagnóstico antes de implementar, uma mudança por vez, só mantém com evidência. |
| `docs/melhorias.md` | Backlog de melhorias com detalhes técnicos. |
| `docs/analise-modelo-chess-challenge-iii.md` | Análise de 13/09/2026 que escolheu o Stockfish 19. **Histórica**: cita 25 min e uma FAQ com 15+10, e recomendava um fork dentro do motor, que não foi feito. |

## Como retomar

1. `git switch competicao-ajustes` e leia a seção "Estado atual".
2. Testes: `python test_tempo.py` e `python test_xadrex.py` (no Windows, `.venv\Scripts\python.exe ...`).
3. Pegue o primeiro item "pendente" da tabela de fases. Uma mudança por commit, com teste.
4. Ao terminar uma fase, atualize a tabela e registre as decisões novas abaixo.

## Estado atual

| Fase | Situação | Commit |
| --- | --- | --- |
| 0. Diagnóstico comparativo (chess-challenge × xadrex) | feita | — |
| 0. Arena de partidas automáticas | feita; match de 10 partidas em 10+0 rodando em 03/11 | — |
| 1. Padrão de tempo 10+0 + teste de simulação 10+0 | feita (60 lances nossos: 0/50 perdas; 80 lances: 19/50, limite conhecido) | 60ebb8d |
| 2. Abortar antes da partida se o motor não abrir | feita (mensagem com caminho esperado, saída com código 1, partida salva preservada) | neste commit |
| 3. Relógio automático (medir a parte humana sem digitar a leitura) | pendente | |
| 4. Anti-empate com risco limitado | adiada (depois do prazo, só com validação na arena) | |
| — Stockfish `.exe` no repositório (passa de 100 MB) | aguardando decisão: Git LFS, `.zip` ou GitHub Release | |
| — Incremento oficial | confirmado: 10+0, relógio físico (organização, 03/11/2026) | |

## Decisões

### D1 — 03/11/2026 — Competir com o xadrex, não com o chess-challenge
O chess-challenge (código da Bea de 2023) é o Stockfish 16 com 2 s fixos por lance e 1 thread, chamado por um notebook. A rede neural do projeto nunca escolhe lances e não funcionaria (saída sigmoid de 1 neurônio contra rótulos UCI em texto; peças pretas somem da entrada; dataset é ponteiro do Git LFS). O notebook trava com Enter vazio, o que pelo edital é derrota. O xadrex tem gestão de tempo própria, testes, entrada que nunca levanta exceção, retomada e desfazer.

### D2 — 03/11/2026 — Padrão de tempo 10+0 (confirmado)
Confirmado com a organização em 03/11/2026: 10 min por equipe, sem incremento, relógio físico. Como o relógio é físico, a parte humana do lance sempre sai do nosso tempo. O suporte a incremento continua no código.
Histórico: a errata fixa 10 min por equipe e não fala em incremento. O padrão anterior (15+10) veio de uma FAQ sem data. Simulação com o `tempo.py`: operador lento (6–10 s por lance), 60 lances, perde 50/50 partidas no padrão 15+10 e 0/50 configurado como 10+0. O operador ainda pode digitar outro valor no início.
Teste (`test_simulacao_sem_perder_por_tempo`, equipe com 3–8 s, mesma contagem do programa): 10+0 com 60 lances nossos não perde em 50 sementes (menor sobra ~94 s); com 70 lances também 0/50 (~32 s). **Limite conhecido:** com 80 lances nossos, 19/50 perdem por tempo. O teste usa 60 lances; não foi afrouxado.

### D3 — 03/11/2026 — Motor ausente deve parar o programa antes da partida
Hoje, sem o `.exe`, o programa só avisa e depois joga o "primeiro lance legal" (`pensar`, último recurso). O operador não percebe. Parar antes da partida não cria risco durante o jogo.
Implementado: `main()` devolve 1 antes de qualquer pergunta (o `iniciar()` nem roda, então a partida salva fica intacta). Durante a partida, a recuperação de `pensar()` (reabrir o motor, último recurso) não mudou.

### D4 — 03/11/2026 — Relógio automático em vez de leitura digitada
Problema: abaixo de 2 min o programa exige digitar o relógio físico a cada lance, justamente quando falta tempo. Proposta: o programa espelha o nosso relógio.
- Início do nosso tempo: primeira tecla do lance do adversário (+ estimativa fixa de "ouvir o lance").
- Fim: o operador aperta Enter ao bater o relógio físico (combinar na equipe quem faz isso).
- A diferença alimenta o `AtrasoHumano` em todo lance; a leitura `e7e5 12:31` vira correção opcional.
- Se o Enter for esquecido, o relógio interno conta a mais (lado seguro: pensa menos, não perde por tempo).

### D5 — 03/11/2026 — Anti-empate adiado
Pontuação 3-1-0: desviar do empate compensa se 2·P(vitória) > P(derrota). Mas contra outro Stockfish um lance pior costuma virar derrota, e em finais de reis e peões o 0.00 em busca profunda é exato. Proposta com risco limitado em `docs/melhorias.md` (item 4). Só entra com validação na arena, contra adversário forte e fraco.

## Arena

Fica em `/Users/bea/workspace/xadrez/arena/` (fora do repositório; será trazida para cá quando o match de 03/11 terminar). Roda o xadrex (código real, via `xadrex.pensar`) contra o notebook da Bea reimplementado, com relógio, atraso humano simulado (3–8 s), aberturas balanceadas com cores trocadas, PGN e Elo com intervalo de confiança.

Resultado do match de 03/11: pendente.
