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
2. Testes: `python test_tempo.py`, `python test_empate.py` e `python test_xadrex.py` (no Windows, `.venv\Scripts\python.exe ...`).
3. Pegue o primeiro item "pendente" da tabela de fases. Uma mudança por commit, com teste.
4. Ao terminar uma fase, atualize a tabela e registre as decisões novas abaixo.

## Estado atual

| Fase | Situação | Commit |
| --- | --- | --- |
| 0. Diagnóstico comparativo (chess-challenge × xadrex) | feita | — |
| 0. Arena de partidas automáticas | feita; trazida para arena/ (match 10+0: xadrex +4 =6 -0, D8) | 1fa1223 |
| 1. Padrão de tempo 10+0 + teste de simulação 10+0 | feita (60 lances nossos: 0/50 perdas; 80 lances: 19/50, limite conhecido) | 60ebb8d |
| 2. Abortar antes da partida se o motor não abrir | feita (mensagem com caminho esperado, saída com código 1, partida salva preservada) | c4c2146 |
| 3. Relógio automático (medir a parte humana sem digitar a leitura) | feita; falta testar o leitor de teclas no Windows real (`msvcrt`) antes de 06/11 | f091a20 |
| — Testar o leitor de teclas no Windows (ou usar a chave `XADREX_ENTRADA_SIMPLES`, D9) | pendente | |
| 4. Anti-empate com risco limitado | implementada (desligada por padrão, chave `XADREX_ANTIEMPATE`, D10); validação na arena pendente | commit "feat: anti-empate opcional com risco limitado" (hash a registrar) |
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

### D6 — 03/11/2026 — Relógio automático: como foi implementado (D4)
- Instantes: `inicio` = 1ª tecla da vez do adversário (`tab` e linha vazia não contam, porque podem vir antes do anúncio; uma tentativa com erro de digitação conta, porque o relógio já corria); `t0` = ENTER do lance adversário (começo da busca); `fim` = ENTER ao bater o relógio. Leitor tecla a tecla em `ler_linha`: `msvcrt` no Windows, `termios` em terminal Unix, `input()` fora de terminal (os dois instantes viram o fim da leitura).
- Contabilidade (`tempo.fechar_lance` e `tempo.relogio_ao_pensar`): `gasto = (fim − inicio) + OUVIR_MS`. `est["previsto_ms"]` continua sendo o relógio em `t0` quando `pensar()` roda (assinatura e significado mantidos para a arena). No `fim` ele passa a guardar o relógio de quando o nosso voltar a correr (relógio em `t0` − (fim − t0) + incremento); no ENTER do lance adversário seguinte desconta ouvir e digitar. Somando os dois passos sai exatamente `gasto − incremento` por lance, sem usar o atraso médio estimado.
- Parte humana medida = gasto − busca (busca = de `t0` até mostrar o lance) alimenta `AtrasoHumano.observar` em todo lance fechado por ENTER.
- ENTER esquecido: a 1ª tecla do lance seguinte fecha o nosso tempo. Conta a mais o tempo que o adversário pensou (lado seguro); essa amostra não ensina o atraso (inflaria a reserva) e o excesso possível vira `folga_ms`, somada ao teto de leitura plausível, para uma leitura correta não ser recusada como "impossível". A folga zera a cada leitura aceita.
- `k` (lances com atraso estimado desde a última leitura) não cresce mais no programa, porque o relógio interno não usa mais estimativa por lance. Fica no estado por compatibilidade com `calibrar` e com a arena.
- Leitura obrigatória (`leitura_obrigatoria`): depois de `u`, sempre (o lance desfeito já saiu do relógio interno e o incremento pode não existir). Fora isso, só se o último lance nosso não foi medido (`medido = False`: retomada, 1º lance das brancas, qualquer lance sem 1ª tecla registrada); aí vale a regra antiga de `precisa_leitura`, que com `k = 0` significa relógio abaixo de 2 min. Com medição, a leitura é opcional mesmo abaixo de 2 min, que era o objetivo de D4.
- Log: linha `relogio` por lance nosso com início, fim (e se veio de ENTER ou tecla), gasto, busca, parte humana e relógio interno; a linha do lance adversário traz início e ENTER.
- Simulação (`simular_medido`, 50 sementes, 10+0, equipe 3–8 s, ouvir real entre 0 e 2 s): 60 lances nossos 0/50 perdas (menor sobra 96,7 s; antes 94,2 s), 70 lances 0/50 (36,3 s; antes 31,5 s), 80 lances 10/50 (antes 19/50). O ganho de sobra é pequeno; o ganho real é tirar a leitura obrigatória abaixo de 2 min.

### D7 — 03/11/2026 — Riscos conhecidos do relógio automático
- **`OUVIR_MS` = 1 s é suposição, não medida.** É a única parte do nosso tempo que o programa não vê, e o erro dela acumula a cada lance (não há leitura para zerar). Se o tempo real de ouvir for maior, o relógio interno fica acima do real. Na simulação com ouvir real sorteado até 4 s (limitado ao tempo antes do ENTER, média ~0,55 s acima da suposição), 60 lances: 0/50 perdas (menor sobra 64 s); 70 lances: 1/50. Mitigação: uma leitura `e7e5 m:ss` de vez em quando corrige tudo; vale cronometrar no ensaio quanto leva do adversário bater o relógio até a nossa 1ª tecla e ajustar a constante.
- **O leitor `msvcrt` não foi testado em Windows** (desenvolvimento em macOS). O caminho `termios` foi conferido num pseudo-terminal (eco, backspace, seta, acento, Ctrl+C, terminal restaurado) e a lógica comum (`ler_teclas`) tem teste com teclas injetadas. Testar no notebook da competição: digitar, apagar, setas, Ctrl+C e ENTER vazio.
- Digitar durante a vez do adversário antes do anúncio (ex.: corrigir algo) antecipa o início: o relógio interno conta a mais (seguro, mas pensa menos).
- Na retomada, o relógio informado vale para o momento da pergunta; se o nosso relógio físico estava correndo, o tempo entre responder e começar a digitar não é descontado (alguns segundos). Por isso a retomada volta à regra antiga de leitura obrigatória abaixo de 2 min.

### D8 — 03/11/2026 — Leitura do match 10+0 na arena
No tabuleiro os dois empataram todas as partidas que terminaram sem bandeira: mesmo motor, sem diferença de força decisiva nesse tempo. A vantagem veio da gestão de tempo (o bea gasta 2 s fixos mais a parte humana e estoura em partidas longas).
Conclusão para a equipe: o ganho competitivo está em não perder por tempo e, contra outro Stockfish, em sair de empates (item 4 do backlog), e não em "força de motor". 10 partidas é amostra pequena; o IC exclui zero, mas é largo.

### D9 — 03/11/2026 — Chave de emergência para o leitor de teclas
O leitor `msvcrt` nunca foi testado no Windows, e programa travado na partida é derrota. Com `XADREX_ENTRADA_SIMPLES=1`, `ler_linha` usa `input()` (como fora de terminal) e o operador liga a chave sem mexer em código.
Consequência: sem o instante da 1ª tecla, o tempo de ouvir além de `OUVIR_MS` e o de digitar o lance adversário não saem do relógio interno, que passa a contar a menos (lado inseguro). Por isso, com a chave, `fechar_relogio` marca o lance como não medido (`medido = False`) e volta a incrementar `k`, para valer a regra antiga inteira de `precisa_leitura`: leitura obrigatória a cada 8 lances nossos e abaixo de 2 min. Só `medido = False` não bastaria, porque `k` não cresce mais desde D6 e a leitura só seria exigida abaixo de 2 min, com o erro acumulado da partida toda. O fim do nosso tempo (ENTER ao bater o relógio) continua medido corretamente.

### D10 — 03/11/2026 — Anti-empate implementado, desligado por padrão
Muda D5 só no momento: o código entregue em 04/11 é o que joga no dia 06, então a melhoria entra agora, desligada e sem risco para o comportamento padrão, e só é ligada (`XADREX_ANTIEMPATE=1`, ou `xadrex.ANTIEMPATE = True` na arena) se a arena mostrar ganho.
- Regras em `empate.py` (funções puras, `test_empate.py`); integração em `xadrex.antiempate`, chamada por `pensar` depois da busca normal (só na 1ª tentativa, com motor vivo). Assinatura e retorno de `pensar` mantidos; o resumo vai em `info["antiempate"]` e o motivo ganha `;antiempate-desviou` quando troca de lance.
- Gatilho: |aval| ≤ 30 cp e (o lance escolhido leva a posição já ocorrida, `is_repetition(2)` depois do push; ou `halfmove_clock` ≥ 20 e o lance escolhido não é captura nem lance de peão).
- Freios: relógio < 60 s, lance único, sem material de mate (`has_insufficient_material`), só reis e peões, orçamento da 2ª busca < 200 ms. Mate não dispara (fica fora da janela).
- 2ª busca: `buscar` com `root_moves` (o mesmo vigia que mata motor travado), orçamento = 0,5 × alvo com teto em máximo − já gasto. Candidatos: lances que não repetem; em sem-progresso, só capturas e lances de peão. Troca se a alternativa (iteração completa) tiver aval ≥ −50 cp. Erro na 2ª busca: mata o motor (o próximo `pensar` reabre) e mantém o lance original.
- **Limiares (30, −50, 20, 60 s, 0,5) são suposições**, sem medida. Riscos: a 2ª busca é mais rasa que a principal e pode aceitar um lance que perde em profundidade; contra outro Stockfish um lance pior costuma virar derrota (D5). Por isso o padrão é desligado.
- Smoke real (Stockfish 19, macOS): xeque perpétuo com os dois ciclos já jogados; a busca escolheu repetir com 0.00 e o anti-empate trocou por `Df1` (0.00 na 2ª busca, 1,1 s). Linha do log: `antiempate=gatilho:repeticao,freio:-,candidatos:22,alt:f8f1(+0.00),decisao:desviou,busca2:1.12s`.

## Arena

Fica em `arena/` (como rodar e limites em `arena/README.md`). Roda o xadrex (código real, via `xadrex.pensar`) contra o notebook da Bea reimplementado, com relógio, atraso humano simulado (3–8 s), aberturas balanceadas com cores trocadas, PGN e Elo com intervalo de confiança.

Resultado do match de 03/11 (`arena/resultados/match_10min/resumo.json`): 10 partidas em 10+0, atraso 3–8 s, seed 2026, xadrex na versão do commit 5b2428f (antes das fases 1–3).

- xadrex +4 =6 -0, 70%, Elo +147 [IC95 +34, +304]. De brancas +3 =2 -0; de pretas +1 =4 -0.
- Motivos: 4 vitórias, todas por tempo esgotado do bea; 4 por tripla repetição; 2 por material insuficiente.
- Pontuação do torneio (3-1-0): xadrex 18 × bea 6.

Leitura em D8.

Compatibilidade depois da fase 3: a arena continua funcionando sem mudanças (`pensar`, `abrir_motor`, `calibrar`, `precisa_leitura` e o significado de `est["previsto_ms"]` em `pensar` foram mantidos; campos novos do estado são lidos com `.get`). Mas ela replica a **contagem antiga** (`previsto -= gasto + atraso médio`, `k += 1`, leitura simulada pela regra de `precisa_leitura`), então não mede o relógio automático. Para medir, `modelos.Xadrex.lance(board, relogio_ms)` precisaria: usar `relogio_ms` (o relógio real da arena, que é o que o relógio automático enxerga, salvo o erro de `OUVIR_MS`) como `est["previsto_ms"]` e marcar `est["medido"] = True`; ensinar ao atraso a parte humana do lance anterior (`relogio_ms_anterior − busca_anterior + incremento − relogio_ms`); trocar a leitura por `xadrex.leitura_obrigatoria(est)` (fica falsa); e não incrementar `k`.
