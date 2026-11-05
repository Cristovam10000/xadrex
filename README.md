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
| Autoria da equipe | Gestão de tempo — `tempo.py` (ver seção abaixo); integração e controle da busca em `xadrex.py`; anti-empate opcional em `empate.py` (desligado por padrão) |
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

Se o motor não abrir (ex.: `.exe` fora de `engines/`), o programa mostra o caminho esperado e fecha com código 1
sem iniciar a partida; uma partida salva continua guardada para a retomada. Confira a seção "Instalação".

Informe nossa cor, tempo base e incremento. O padrão é 10 min + 0 s (Errata nº 01): sem incremento, relógio
físico (confirmado com a organização). No turno do adversário, digite o lance
anunciado em UCI (`e2e4`, `e7e8q`). Nosso lance aparece como `>>> NOSSO LANCE: ...`.

**Relógio automático.** Depois de mostrar o nosso lance, o programa pede `ENTER ao bater o relógio`: quem
opera aperta ENTER no momento em que a equipe bate o relógio físico. Com isso o programa mede sozinho o tempo
que saiu do nosso relógio: da primeira tecla do lance adversário (mais 1 s estimado para ouvir o anúncio) até
esse ENTER. Se o ENTER for esquecido e o operador já digitar o lance seguinte do adversário, tudo bem: a primeira
tecla fecha o nosso tempo (conta um pouco a mais, o lado seguro) e o lance digitado vale normalmente. Combinem na
equipe quem aperta o ENTER. Durante a vez do adversário, evite digitar antes de ele anunciar o lance: a primeira
tecla marca o início do nosso tempo (`tab` e linha vazia não contam).

| Comando | Efeito |
| --- | --- |
| `e7e5` | lance do adversário |
| `e7e5 12:31` | lance do adversário + leitura do nosso relógio físico naquele momento (corrige o relógio interno). Opcional enquanto o relógio automático funciona. **Obrigatória** depois de `u` e, abaixo de 2 min, quando o último lance nosso não pôde ser medido (retomada, 1º lance das brancas) |
| `u` | desfaz nosso último lance e o do adversário (corrigir digitação) |
| `tab` | mostra tabuleiro e lista de lances |
| `sair` | fecha; a partida é retomada ao rodar de novo (pergunta o relógio atual) |
| ENTER vazio | logo depois do nosso lance: marca o instante em que batemos o relógio |
| `fim` | encerra a partida (abandono, tempo, empate acordado) |

O log de cada partida fica em `logs/`: por lance, número, cor, UCI, profundidade, nós, avaliação, PV, tempo
gasto e as decisões do gestor (alvo, máximo, motivo da parada, atraso humano estimado). Uma linha `relogio`
por lance nosso registra o relógio automático: início (1ª tecla), fim (ENTER ou tecla), gasto medido, tempo de
busca e parte humana medida.

**Chave de emergência.** Se o leitor de teclas der problema no dia (tecla que não aparece, travamento), feche com
`sair` e rode de novo com a entrada simples, sem mexer no código. No PowerShell:
`$env:XADREX_ENTRADA_SIMPLES=1; .venv\Scripts\python.exe xadrex.py`; no cmd: `set XADREX_ENTRADA_SIMPLES=1` e depois
`.venv\Scripts\python.exe xadrex.py`. Nesse modo o tempo de digitar não é medido, então a leitura do relógio
(`e7e5 12:31`) volta a ser obrigatória a cada 8 lances nossos e abaixo de 2 min.

**Anti-empate.** Ligado por padrão desde 04/11/2026: na arena fez 80 x 58 pontos 3-1-0 contra o `bea` (30 partidas cada, sem derrotas; diário D13). Quando a busca escolhe
um lance que repete uma posição (ou a partida está há 20 meios-lances sem captura nem lance de peão) e a avaliação
está entre -0,30 e +0,30, o programa faz uma 2ª busca curta só entre os lances que não repetem e joga a melhor
alternativa se ela não for pior que -0,50 (a 2ª busca tem pelo menos 1 s). Não tenta com menos de 1 min no relógio,
sem material para dar mate, em final só de reis e peões nem com lance único; qualquer erro nessa etapa mantém o lance
original. O início da partida e o cabeçalho do log dizem se está ligado. Para desligar, no PowerShell:
`$env:XADREX_ANTIEMPATE=0; .venv\Scripts\python.exe xadrex.py`; no cmd: `set XADREX_ANTIEMPATE=0` e depois
`.venv\Scripts\python.exe xadrex.py`. Ligado, o log de cada lance nosso ganha o campo
`antiempate=` (gatilho, freio, candidatos, avaliação da alternativa, decisão e tempo da 2ª busca). Os limiares
ficam em `empate.py` e ainda são suposições.

Testes: `.venv\Scripts\python.exe test_tempo.py`, `.venv\Scripts\python.exe test_empate.py` e
`.venv\Scripts\python.exe test_xadrex.py`. Para rodar tudo de uma vez (testes de unidade, smoke da arena,
match e lote), use `rodar_testes.py`; o guia completo está em [docs/testes.md](docs/testes.md).

## Gestor de tempo (autoria da equipe)

O Stockfish decide **qual** lance jogar; `tempo.py` decide **por quanto tempo** ele pensa. O gestor do próprio
Stockfish não sabe que, numa partida com tabuleiro físico, o nosso relógio também corre enquanto o operador
digita o lance adversário, anuncia o nosso, move a peça e aperta o relógio. Nos testes com o gestor dele e um
atraso humano fixo de 5 s, ele gastou 13 s com 24 s no relógio.

1. **Atraso humano medido** (`AtrasoHumano`, `fechar_lance`). A cada lance nosso, o relógio automático mede
   o gasto (1ª tecla do lance adversário até o ENTER ao bater o relógio, mais `OUVIR_MS` = 1 s, uma
   suposição); gasto menos tempo de busca é uma amostra do custo humano. A estimativa usa o algoritmo do
   tempo de retransmissão do TCP (RFC 6298): média suavizada (1/8) e desvio suavizado (1/4); a reserva de
   segurança é média + 4 × desvio (mínimo 3 s). A leitura digitada do relógio físico continua aceita como
   correção; leitura impossível (maior que o relógio interno mais o que ele pode ter contado a mais) é
   recusada, ex.: `2:00` digitado no lugar de `0:20`.
2. **Orçamento por lance** (`orcamento`). Reserva o custo humano do lance atual; distribui o resto por um
   horizonte de lances que depende da fase (material) e de haver saldo de incremento; soma ao alvo o saldo
   do incremento (incremento − atraso humano), que é **negativo** sem incremento; aplica rampa de abertura;
   o máximo nunca passa de 30% do tempo disponível.
3. **Controle da busca** (`ControleBusca`). A cada iteração completa do Stockfish: troca recente do melhor
   lance estende o alvo (até 3×), queda da avaliação em relação à busca anterior estende (até 2×), melhor
   lance estável por 8 iterações encurta (0,6×); para na hora em lance único e mate encontrado. Se o motor
   não responder ao `stop` (até 3 s além do máximo, nunca além do que o relógio permite), o programa o mata
   e joga o melhor lance da última iteração completa. Tempo já gasto antes da busca é descontado.

Evidência: `test_tempo.py` simula partidas com a contagem antiga do programa (o gestor só conhece o relógio
previsto; leitura só quando exigida, com erro de até 1 s) e atraso humano aleatório: sem perdas por tempo
em 10+0 com 60 lances nossos (equipe com 3–8 s por lance), 15+10 com 120 lances (equipe com 3–8 s e equipe
lenta com 6–10 s), 25+0 com 80 lances e Armageddon (5 e 4 min). Limite conhecido: em 10+0 com 80 lances nossos
a simulação perde por tempo em 19 de 50 partidas. Com o relógio automático (`simular_medido`: só o tempo de
ouvir é estimado, sem nenhuma leitura), 10+0 com 60 lances nossos também não perde. O horizonte sem incremento foi escolhido nessa simulação: com a primeira versão,
todas as 30 partidas 25+0 de 80 lances perdiam por tempo.
