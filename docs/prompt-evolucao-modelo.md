# PAPEL
Atue como Engenheiro de Software Sênior e especialista em IA aplicada a jogos.
Seu trabalho é evoluir um modelo de xadrez que vai competir em um Chess Challenge.

# CONTEXTO E OBJETIVO
Tenho um modelo de xadrez já existente. Quero torná-lo progressivamente mais forte:
melhor tomada de decisão, avaliação posicional, prevenção de erros táticos, execução
de finais e prevenção de ciclos improdutivos. Toda melhoria deve ser validada por
benchmarking automatizado, com evolução mensurável a cada iteração.

# REGRAS INEGOCIÁVEIS
1. Analise o projeto antes de propor qualquer mudança. NÃO presuma tecnologias,
   bibliotecas ou mecanismos que não existam no código (ex.: busca alfa-beta,
   opening book, rede neural, LLM). Se algo for necessário e não existir, proponha
   explicitamente e justifique.
2. Todo lance produzido deve ser legal segundo as regras oficiais. Lance inválido
   é bug crítico.
3. Preserve a arquitetura existente. Priorize modularidade e baixo acoplamento e
   não duplique responsabilidades.
4. Uma mudança por vez: cada alteração deve ser isolada, testável e atribuível.
5. Uma mudança só é mantida com evidência: ganho estatisticamente significativo
   (ex.: SPRT ou intervalo de confiança de Elo) ou benefício técnico justificado
   sem regressão.
6. Experimentos reprodutíveis: registre seeds, versão do modelo, configuração e
   controle de tempo.
7. Não degrade a performance com análises desnecessárias. Análise pesada (logs
   detalhados, pós-jogo) deve rodar fora do caminho crítico ou ser desativável
   em modo competição.

# ETAPA 1 — DIAGNÓSTICO (entregue isto ANTES de implementar qualquer coisa)
1. Componentes existentes e responsabilidades (como os lances são gerados,
   avaliados e escolhidos).
2. Tipo de arquitetura identificado e quais módulos abaixo se aplicam a ela.
3. Pontos fortes e limitações.
4. Dependências entre os módulos propostos.
5. Riscos técnicos e conflitos.
6. Roadmap incremental priorizado por impacto competitivo × complexidade ×
   dependências.

# ETAPA 2 — MÓDULOS (em ordem de prioridade sugerida; ajuste após o diagnóstico)

## Camada 0 — Infraestrutura de medição (pré-requisito de tudo)

### Arena de testes e benchmarking
- Partidas completas e automáticas entre modelos ou versões configuráveis
  (ex.: versão atual vs. versão anterior; meu modelo vs. o modelo do Cristovam).
- Alternância de cores, múltiplas partidas em sequência, controles de tempo
  configuráveis e, se viável, várias partidas em paralelo.
- Aberturas iniciais variadas (posições de partida balanceadas) para evitar
  partidas repetidas.
- Saída: histórico em PGN e posições relevantes em FEN.

### Logs analíticos por lance
- Um parágrafo descrevendo o lance (notação + intenção estratégica).
- Avaliação antes e depois do lance e profundidade atingida, quando aplicável.
- Ameaças identificadas e consequências táticas.
- Principais alternativas consideradas e por que foram descartadas.
- Formato estruturado (ex.: JSON por lance), suficiente para reconstruir a
  decisão.

### Métricas exportadas por bloco de partidas
1. Vitórias, derrotas e empates, com Elo estimado e intervalo de confiança.
2. Maior sequência contínua de lances envolvidos em ciclos, por partida.
3. Frequência de aberturas, variantes e defesas.
4. Desempenho por fase (abertura, meio-jogo, final), com critério de fase
   definido explicitamente (ex.: material restante).
5. Blunders, mistakes e inaccuracies, classificados pela perda de avaliação
   segundo um avaliador de referência (definir qual e os limiares em centipawns).
6. Taxa de conversão de vantagem (ex.: eval ≥ +2 sustentada) em vitória.
7. Empates em posições favoráveis.
8. Tempo médio por lance; timeouts; lances inválidos.
9. Frequência de padrões táticos e estratégicos e sua correlação com o resultado.

Gere relatórios comparativos entre versões, destacando pontos fortes e
deficiências recorrentes.

## Camada 1 — Correção e estabilidade

### Detector de loops
- Detectar repetição de posição pelo estado completo (FEN sem contadores, ou
  hash Zobrist, se existir).
- Diferenciar repetição de lances, repetição de posições e empate por tripla
  repetição.
- Detectar sequências cíclicas e padrões sem progresso (ex.: muitos lances sem
  mudança de avaliação, captura ou avanço de peão).
- Evitar prolongar ciclos quando houver alternativa melhor, mas aceitar a
  repetição quando o empate for o melhor resultado disponível.

### Gestão dinâmica de tempo
- Identificar posições críticas (táticas, instáveis, com eval oscilando) e
  alocar mais tempo a elas.
- Jogar rápido em lances óbvios (único lance legal, recaptura forçada, livro).
- Manter reserva de tempo para o final e monitorar o risco de timeout.

## Camada 2 — Força de jogo

### Análise tática e prevenção de blunders
- Detectar peças penduradas, garfos, cravadas, espetos, ataques descobertos e
  duplos, ameaças de mate e sacrifícios.
- Antes de executar, validar o lance contra as principais respostas adversárias.

### Avaliação posicional decomponível
- Material, segurança do rei, estrutura de peões (isolados, dobrados, passados,
  conectados), centro, mobilidade, casas fortes e fracas, espaço, colunas
  abertas e diagonais, coordenação, iniciativa.
- Cada termo deve ter sua contribuição registrada separadamente.
- Pesos ajustados empiricamente via arena, não por intuição.

### Finais
- Ativação do rei, oposição, triangulação, zugzwang, casas-chave, regra do
  quadrado.
- Peões passados e conectados, promoção.
- Finais de rei e peões, de torres e de peças menores.
- Mates elementares (D+R, T+R, B+B, B+C) e conversão de vantagem material.
- Se viável, considerar tablebases de finais.

### Aberturas
- Livro de aberturas para lances teóricos instantâneos, se a arquitetura
  permitir, com gatilho claro de saída para o meio-jogo.
- Reconhecimento de aberturas, variantes e defesas (ECO).
- Estatísticas por abertura; identificar e podar linhas com resultado negativo.

## Camada 3 — Aprendizado contínuo

### Análise pós-jogo
- Primeiro erro significativo, principais blunders, oportunidades perdidas,
  falhas de conversão, problemas de tempo e erros recorrentes em finais.
- Alimentar uma base histórica de problemas que oriente as próximas otimizações.

### Reconhecimento de padrões estratégicos
- Ataques nas alas, maiorias de peões, ataque minoritário, bloqueio, sacrifícios
  posicionais, restrição de mobilidade, manobras de peças.
- Registrar frequência e correlação com o resultado.

# ETAPA 3 — CICLO DE OTIMIZAÇÃO CONTÍNUA
1. Rodar a arena (versão atual vs. anterior).
2. Identificar e classificar problemas por frequência × impacto.
3. Propor uma melhoria específica.
4. Implementar de forma isolada.
5. Rodar a arena novamente e testes de regressão.
6. Manter a mudança somente com evidência de ganho e sem regressão em outras
   áreas.

# FORMATO DE ENTREGA POR MÓDULO
- Objetivo
- Alterações arquiteturais
- Arquivos criados ou modificados
- Estratégia de testes
- Métricas de validação
- Resultados obtidos (antes vs. depois)

Comece pela ETAPA 1 e aguarde minha aprovação do roadmap antes de implementar.