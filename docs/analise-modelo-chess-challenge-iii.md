# Escolha de motor para o Chess Challenge III

**Data:** 13/09/2026  
**Estado:** pesquisa e decisão arquitetural; nenhum motor da equipe foi implementado.  
**Objetivo:** escolher uma base de xadrez competitiva, executável sem rede e compatível com a exigência de um componente decisório de autoria da equipe.

## Evidências e limites da análise

- O workspace `C:\projetos.2\xadrex` estava vazio antes desta análise. Não havia código, convenções ou testes do projeto para auditar.
- O regulamento local `C:\Users\crish\Downloads\Chess-Challenge-III-1.pdf` tem três páginas; SHA-256 `edcec7139d2e6ed48f6b5c43d4dee7990279c21a9e3a38cd475f8e08dc893bcf`. Todas as páginas foram extraídas e inspecionadas visualmente. Ele é **fonte de requisitos a analisar**, não uma solicitação para enviar código ou contatar a organização.
- A FAQ transcrita pelo usuário detalha as regras, mas não veio com data, URL ou assinatura independente. Onde contradiz o PDF, a precedência precisa ser confirmada por escrito com a organização.
- Hardware observado neste ambiente: Intel Core 7 240H, 10 núcleos/16 processadores lógicos; 15,7 GiB de RAM; NVIDIA GeForce RTX 5050 Laptop GPU com 8151 MiB de VRAM informados pelo driver. Ainda não está confirmado que será o notebook usado na competição.
- Pesquisa externa consultada em 13/09/2026. As fichas de repositório do conector Hugging Face responderam; as ferramentas de busca de modelos e artigos do mesmo conector retornaram erro `Tool ... not found`. A descoberta foi complementada pelas páginas públicas e pela API pública do Hub.

## Requisitos e conflitos que mudam a arquitetura

| Tema | PDF | FAQ fornecida | Consequência |
| --- | --- | --- | --- |
| Autoria | Modelos preexistentes são aceitos se houver modificações significativas; cópias simples desclassificam (p. 2). | Exige ao menos avaliação, busca/seleção ou gestão de tempo própria e funcional; ajustar parâmetros não basta. | O componente próprio precisa decidir efetivamente durante as partidas, com código e evidência de testes. |
| Tempo normal | **25 minutos por lado**, sem incremento mencionado (p. 2). | **15 minutos por lado + 10 segundos por lance**. | Implementar perfis de relógio configuráveis; não fixar uma das versões sem confirmação. |
| Entrega | Git para a organização em **04/11/2026**, com validação e desclassificação se não ocorrer (p. 2). | Declarar base/commit no credenciamento e disponibilizar repositório à banca ao final. | Preparar para o prazo mais cedo até a organização esclarecer a divergência. Nenhuma entrega foi realizada nesta análise. |
| Falha operacional | Travamento/falha do software acarreta derrota na partida (p. 3). | Tabuleiro físico é fonte da verdade; entrada UCI manual após anúncio, repetição e movimento físico. | Confiabilidade, recuperação de estado e ensaio com operador são requisitos centrais. |
| Chaves e fases | A p. 1 diz literalmente “5 quatro rodadas”; a p. 2 diz que as 8 melhores vão às “Semifinais e Final”. | Descreve melhor de três, cores alternadas e Armageddon. | Há inconsistência editorial a esclarecer; o software deve suportar nova partida, troca de cor e relógios diferentes. |

Também há uma divergência de elegibilidade interna ao PDF: o público-alvo inclui ensino médio (p. 1), mas a seção “Composição das Equipes” pede três alunos de graduação (p. 3). Isto não altera a escolha do motor, mas deve ser esclarecido antes da inscrição.

## Decisão recomendada

**Usar um fork do Stockfish 19 estável, tag `sf_19`, commit `edb0d9db6731067ec50ce619ff372b463bc4dd5d`, mantendo sua rede NNUE compatível e implementando um gestor de tempo original dentro do motor.** A versão foi anunciada em 05/09/2026 e o binário Windows oficial foi verificado nesta máquina. [Anúncio do Stockfish 19](https://stockfishchess.org/blog/2026/stockfish-19/), [repositório e licença](https://github.com/official-stockfish/Stockfish/blob/sf_19/README.md).

“Motor” é o programa completo que recebe uma posição e escolhe um lance. NNUE (*Efficiently Updatable Neural Network*, rede neural eficientemente atualizável) é o modelo de avaliação de posições dentro do Stockfish; a busca alfa-beta explora consequências dos lances e usa essas avaliações. A NNUE foi desenhada para execução eficiente na CPU, portanto a GPU disponível **não acelera diretamente o Stockfish**. [Explicação técnica oficial](https://official-stockfish.github.io/docs/stockfish-wiki/Advanced-topics.html), [FAQ oficial sobre GPU](https://official-stockfish.github.io/docs/stockfish-wiki/Stockfish-FAQ.html).

O motivo da escolha é a combinação de força já demonstrada pela base, execução local em CPU, protocolo e informações de busca disponíveis e risco de integração menor do que uma pilha GPU. O anúncio oficial relata ganho de até 44 pontos Elo contra Stockfish 18 **nos testes do próprio projeto**; isso não é uma previsão da força do futuro fork nem prova vitória neste notebook. [Anúncio e condições do resultado](https://stockfishchess.org/blog/2026/stockfish-19/).

### Comparação das alternativas

| Base | Adequação ao torneio | Autoria e custo principal | Decisão |
| --- | --- | --- | --- |
| **Stockfish 19 + NNUE original** | Forte ponto de partida, CPU local, UCI e telemetria de busca. | Fork em C++ sob GPLv3 e algoritmo decisório próprio a testar; uma simples mudança de `Move Overhead`, `Threads` ou constantes não satisfaz a FAQ. | **Base principal recomendada.** |
| **Lc0 + Chessformer BT4** | Motor local com rede neural e busca em árvore Monte Carlo, usando GPU. O Hub do projeto hospeda BT4 (190 milhões de parâmetros; arquivo de pesos de cerca de 320 MB). | Backend GPU, pesos compatíveis, consumo real de VRAM/energia, teste de força no hardware e componente próprio; licença exata dos pesos deve ser verificada antes da distribuição. | Experimento comparativo, não base principal sem benchmark. |
| **Maia-2 Blitz** | Prevê distribuição de lances legais condicionada ao nível dos jogadores; ficha indica 23,3 milhões de parâmetros e licença MIT. | Objetivo declarado é imitar padrões humanos, não maximizar desempenho competitivo; ainda exigiria busca/gestão de tempo e autoria. | Útil para pesquisa de comportamento humano, não para selecionar os lances principais. |
| **LLM genérico ou motor próprio em Python** | LLM local é permitido pela FAQ; um motor próprio com `python-chess` favorece aprendizado e autoria inequívoca. | LLM exige validação explícita de legalidade e não oferece, por si, profundidade/nós/PV comparáveis; motor próprio demanda implementar e calibrar busca e avaliação, provavelmente com menor força inicial. | Somente se o objetivo primário mudar para pesquisa didática, após testes comparativos. |

Fontes primárias: [Lc0 e licença GPLv3](https://github.com/LeelaChessZero/lc0), [FAQ do Lc0](https://lczero.org/play/faq/), [repositórios oficiais do Lc0 no Hugging Face](https://huggingface.co/LeelaChessZero), [BT4 no Hub](https://huggingface.co/LeelaChessZero/BT4), [Maia-2 Blitz no Hub](https://huggingface.co/shermansiu/maia2-blitz), [paper Maia-2](https://huggingface.co/papers/2409.20553), [documentação do python-chess](https://python-chess.readthedocs.io/en/stable/engine.html).

Nenhuma comparação direta Stockfish 19 versus Lc0/BT4 foi executada neste notebook. Portanto, “melhor” aqui significa **melhor escolha inicial considerando competição, implementação e confiabilidade**, e não vitória empírica comprovada sobre todas as alternativas.

### Por que um motor sem GPU ainda pode ser a melhor escolha

Sim, o Lc0 utiliza GPU quando executado com um backend compatível, como CUDA. Ele combina uma rede neural relativamente grande com MCTS e agrupa avaliações de várias posições em lotes para aproveitar o paralelismo da GPU. O Stockfish segue outra arquitetura: sua NNUE é pequena e atualizada incrementalmente, enquanto a busca alfa-beta avalia muitos nós com latência muito baixa na CPU. Enviar cada uma dessas avaliações curtas à GPU acrescentaria sincronização e transferência de dados; por isso, a documentação oficial do Stockfish afirma que a GPU não é adequada ao seu padrão de avaliação.

Usar GPU, isoladamente, não significa jogar melhor. Não se deve comparar os motores apenas por nós por segundo: um “nó” do Lc0 envolve uma avaliação neural e uma política de expansão diferentes de um nó do Stockfish. A comparação válida é por partidas pareadas no mesmo hardware, controle de tempo, aberturas e cores invertidas.

**Analogia:** o Stockfish funciona como um enxadrista que consulta uma ficha pequena e muito rápida milhões de vezes; o Lc0 funciona como uma equipe que envia grupos de posições para uma central de análise mais pesada. **Correspondência técnica:** a ficha é a NNUE executada na CPU; a central é a rede do Lc0 processada em lote na GPU; as consultas são os nós das respectivas buscas. **Limitação:** a qualidade não depende somente da velocidade das consultas, mas também da avaliação, da busca, da gestão de tempo e da posição analisada.

Para este projeto, o Stockfish 19 permanece como recomendação principal porque reúne força geral, maturidade, menor risco operacional e telemetria UCI diretamente compatível com o log exigido. A própria FAQ do Lc0 diz que a comparação depende do hardware, mas considera o Stockfish ligeiramente mais forte em geral. Essa afirmação não substitui um benchmark local do Lc0.

O Lc0 continua sendo a melhor segunda alternativa para explorar a RTX 5050. O experimento correto seria usar o Lc0 estável 0.32.1 com o BT4, medir compatibilidade e velocidade do backend CUDA, e então executar partidas pareadas contra o Stockfish 19. O arquivo BT4 no Hugging Face tem cerca de 320 MB comprimidos; isso não determina sozinho o consumo de VRAM durante a busca. A compatibilidade com os aproximadamente 8 GiB disponíveis precisa ser validada em execução. Também se deve esclarecer a licença específica dos pesos, pois o repositório BT4 no Hub não apresenta model card nem licença declarada, embora o código do Lc0 seja GPLv3.

## Componente decisório de autoria proposto

Criar uma **gestão de tempo consciente da operação humana**, distinta do ajuste de parâmetros já existentes. O Stockfish 19 já altera o tempo de busca com a queda de avaliação, a estabilidade do melhor lance e o esforço por lance; esses mecanismos devem ser preservados e usados como ponto de comparação. [Código de gestão de tempo](https://github.com/official-stockfish/Stockfish/blob/sf_19/src/timeman.cpp), [decisão de parada em `search.cpp`](https://github.com/official-stockfish/Stockfish/blob/sf_19/src/search.cpp).

Proposta operacional:

1. O aplicativo registra a leitura do relógio físico, a hora monotônica em que ela foi feita e os tempos reais que o operador gastou para inserir o lance adversário e para anunciar/mover/acionar o relógio após receber a resposta.
2. O gestor calcula uma **reserva adaptativa** para a ação humana com base em amostras recentes, um piso de segurança e margem para atraso; a reserva não depende apenas de um valor fixo de `Move Overhead`.
3. O gestor usa relógio restante, incremento confirmado, reserva e fase da partida para definir limite normal e limite máximo de busca. Em apuro, o limite é reduzido antes que falte tempo para anunciar e executar o lance no tabuleiro.
4. A busca continua com a lógica posicional do Stockfish; a equipe registra o orçamento concedido, a reserva calculada e a razão da parada. Os testes confrontam o fork com a base intacta e medem perdas por tempo e qualidade dos lances.

Isto é **proposta**, não componente implementado. Sua aceitação como “modificação significativa” depende de implementação real, distinção clara do algoritmo original, funcionamento durante a partida e arguição da banca. A FAQ autoriza gestão de tempo própria, mas não existe homologação antecipada registrada.

**Analogia:** o motor é um enxadrista com assessor de relógio. O assessor não escolhe a jogada: decide quanto tempo o enxadrista pode pensar e ainda conseguir anunciar e mover a peça. **Correspondência técnica:** o “enxadrista” é busca + NNUE; o “assessor” é o novo algoritmo que transforma leituras do relógio e atrasos medidos em limites de busca. **Limitação:** o atraso humano é variável e não pode ser previsto perfeitamente; a reserva reduz risco de perda por tempo, mas não o elimina nem prova ganho de força.

## Fluxo mínimo de partida proposto

```text
Relógio físico + lance UCI anunciado
        -> operador confirma e insere no terminal
        -> validador de lance e histórico completo
        -> estado enviado ao fork do Stockfish 19
        -> gestor de tempo próprio limita a busca
        -> bestmove + depth/nodes/score/PV/time
        -> operador anuncia, move peça e aciona relógio
        -> log local por lance e conferência com tabuleiro
```

UCI (*Universal Chess Interface*, Interface Universal de Xadrez) é o protocolo textual que transmite posição, tempo e lances entre aplicativo e motor. `python-chess` pode representar o tabuleiro e validar a entrada com `Board.parse_uci()` antes de modificar o estado; `Board.push()` **sozinho não verifica legalidade**. A biblioteca também disponibiliza integração UCI e informações de busca (`depth`, `nodes`, `score`, `pv`, `time`). [Validação de lances](https://python-chess.readthedocs.io/en/stable/core.html), [interface de motor](https://python-chess.readthedocs.io/en/stable/engine.html).

Para cada lance da equipe, gravar em `.txt`/`.log`: número, cor, UCI, profundidade, nós, avaliação com perspectiva explicitada, variante principal (PV, sequência mais promissora encontrada pela busca) e tempo. Guardar também FEN (*Forsyth–Edwards Notation*, texto que descreve uma posição), relógios vistos, versão/commit do motor e motivo de fallback. O log deve ser escrito e descarregado em disco a cada lance concluído. Uma avaliação de mate precisa ser distinta de centipeões. O log de depuração do Stockfish **não substitui automaticamente** o formato exigido pela FAQ.

Manter histórico de lances confirmado, não apenas a posição atual: repetições dependem do histórico. Se houver divergência, interromper a busca, conferir o tabuleiro físico e reconstruir a sequência desde o último estado confirmado; um simples reset por FEN pode perder a informação necessária à tripla repetição. Não aceitar uma jogada do motor sem conferir legalidade e turno. Planejar tratamento explícito de promoção, roque, en passant, lance ilegal digitado, processo do motor encerrado e relógio abaixo da reserva. [Documentação de repetição do python-chess](https://python-chess.readthedocs.io/en/stable/core.html).

Iniciar **sem opening book e sem ponderação**: o book limitado a dez meios-lances é permitido, mas um lance obtido só do book não produz naturalmente profundidade, nós e avaliação exigidos para cada lance; seria necessário definir como preencher esses campos honestamente. Ponderar no turno adversário pode ajudar, porém o anúncio e a entrada são assíncronos e elevam o risco de analisar a posição errada. Tablebase Syzygy de até cinco peças é opcional mais tarde; configurar o limite efetivo para cinco, sem incluir bases de seis ou sete. Essas escolhas simplificam a primeira versão, não são proibições do regulamento.

## Ensaios e validação

**Executado nesta análise:**

- Extração e revisão visual das três páginas do PDF.
- Consulta às fontes oficiais e às fichas de repositório do Hugging Face.
- Confirmação do tag Git `sf_19` no commit integral acima.
- Download temporário do binário oficial `stockfish-windows-x86-64-universal.zip` para `%TEMP%\xadrex-stockfish19`; SHA-256 baixado e publicado coincidem: `3c8bf1f9ea66a09350a40df4f632288285ac206d99f33ab5842c408fc30b48a7`. Nenhum binário foi colocado no workspace.
- `stockfish ... bench 1024 14 13 default depth`: 40.443.583 nós em 5.309 ms, cerca de 7,62 milhões de nós/s. Em três execuções curtas por configuração (`bench 512 <threads> 12 default depth`), médias: 10 threads ~6,90 milhões; 14 ~7,76 milhões; 16 ~7,75 milhões de nós/s. As amostras são pequenas, com carga e temperatura não controladas; **não provam** configuração ótima nem força em partidas.
- Smoke test UCI com `position startpos moves e2e4 e7e5` e `go movetime 500`: o binário retornou `bestmove g1f3` e linha `info` com `depth=19`, `nodes=321077`, `score cp 33`, PV e `time=501 ms`. Isso comprova saída básica exigida para log, não a existência do aplicativo de log nem a legalidade de todas as futuras partidas.

**A executar quando houver implementação:**

1. Testes de unidade do gestor com relógio normal, incremento zero, 15+10, 25+0, Armageddon 5/4, entrada humana atrasada, relógio quase esgotado e leituras inconsistentes.
2. Testes de integração offline de uma partida completa com brancas e pretas, incluindo promoção, roque, en passant, repetição, cinquenta lances, erro de digitação e recuperação do histórico.
3. Ensaio presencial cronometrado com tabuleiro e relógio reais; verificar latência do operador, ausência de lances ilegais, ausência de perda por tempo e integridade do log após cada lance.
4. Partidas pareadas do fork contra Stockfish 19 intacto, mesmas aberturas e cores alternadas, em controle confirmado; relatar vitórias/empates/derrotas, perdas por tempo, travamentos e incerteza estatística. Ferramenta candidata para teste **antes do evento**: [Fastchess](https://github.com/Disservin/fastchess). Nenhum teste de força entre motores foi realizado nesta análise.
5. Teste inteiramente sem rede, com dependências, binário, pesos, book/tablebase opcionais e licenças já disponíveis localmente. Não usar API externa durante a partida.

Ponto inicial de configuração, **não medido como ótimo**: 14 threads (deixar dois processadores lógicos livres), `Hash=512 MiB`, `MultiPV=1`, sem limitação artificial de força. Confirmar em partida longa, na tomada/bateria prevista, se o notebook mantém desempenho e a interface permanece responsiva. A orientação oficial indica que `MultiPV > 1` consome recursos que poderiam buscar melhor o primeiro lance. [Ajustes do Stockfish](https://official-stockfish.github.io/docs/stockfish-wiki/Stockfish-FAQ.html).

## Licença, proveniência e próximos passos

O fork do Stockfish herda as obrigações da GPLv3 (*GNU General Public License version 3*, licença de software livre com reciprocidade): ao distribuir o binário modificado, fornecer a licença e o código-fonte correspondente à versão distribuída, inclusive as alterações. Registrar tag/commit da base, diferença do fork, versão e hash do binário, rede NNUE usada, dependências e instruções de compilação. Pesos de terceiros e opening book não são autoria da equipe segundo a FAQ. [Termos oficiais do Stockfish](https://github.com/official-stockfish/Stockfish/blob/sf_19/README.md).

Pendências que impedem declarar o projeto pronto: confirmar por escrito qual controle de tempo vale e qual é o prazo de entrega; confirmar o notebook da equipe; implementar motor, interface, gestor próprio e log; testar operação offline e partidas reais. Não foi enviado email, feito credenciamento ou publicado repositório. Se o gestor próprio piorar a força ou causar perdas por tempo, **rollback técnico**: manter um branch do Stockfish 19 intacto como referência, reverter o componente experimental e revalidar uma alternativa autoral antes da entrega. O motor intacto sozinho não satisfaz a autoria da FAQ.

## Glossário curto

- **CPU (*Central Processing Unit*, unidade central de processamento):** processador geral que executa a busca e a NNUE do Stockfish.
- **GPU (*Graphics Processing Unit*, unidade de processamento gráfico):** processador paralelo útil aos modelos maiores do Lc0, desde que haja backend e memória suficientes.
- **LLM (*Large Language Model*, modelo grande de linguagem):** modelo treinado principalmente para prever texto; sem lógica adicional de xadrez, não substitui um motor com busca e estado legal.
- **MCTS (*Monte Carlo Tree Search*, busca em árvore Monte Carlo):** método de selecionar e expandir variantes de jogo com estatísticas da árvore, usado pelo Lc0.
- **Nó:** posição examinada durante a busca; nós por segundo medem velocidade de busca, não força absoluta entre motores diferentes.
- **Centipeão:** centésimo da unidade tradicional de avaliação em peões; sua interpretação moderna no Stockfish é normalizada e não equivale diretamente a material ganho.
