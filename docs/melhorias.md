# Melhorias pendentes — xadrex (Chess Challenge III)

Prazo: código no Git até 04/11/2026; competição em 06/11/2026.

## 1. Tempo padrão 15+10 → 10+0
- `xadrex.py:185-186`: padrões do prompt de início.
- Acrescentar 10+0 em `test_tempo.py` (`test_simulacao_sem_perder_por_tempo`).
- Depende da resposta da organização sobre incremento.

## 2. Stockfish (.exe) dentro do repositório
- Hoje `engines/stockfish-windows-x86-64-universal.exe` está no `.gitignore` e não vai para o Git.
- Problema: o `.exe` tem ~103 MB e o GitHub recusa arquivos acima de 100 MB.
- Opções (decidir):
  - Git LFS para o `.exe` (exige `git lfs install` em quem clonar; a organização precisa conseguir baixar).
  - Versionar o `.zip` oficial, se ficar abaixo de 100 MB, e extrair na instalação (conferir SHA-256 do README).
  - Anexar o binário a um GitHub Release e documentar o download.
- Junto: abortar na abertura do programa se o motor não abrir (hoje cai em "primeiro lance legal" silenciosamente, `xadrex.py:399-400` e `:278`).

## 3. Contagem automática do relógio
- Hoje o relógio é estimado e o operador digita a leitura do relógio físico a cada 8 lances e em todo lance abaixo de 2 min.
- Objetivo: o programa medir sozinho o tempo que corre no nosso relógio, inclusive a parte humana.
- Proposta em discussão (ver conversa de 03/11/2026).

## 4. Anti-empate com risco limitado (ciclos sem progresso)
- Caso real: partida manual em que a avaliação ficou 0.00 do lance 18 em diante, com reis andando em vai e volta (sem tripla repetição).
- Motivação: pontuação 3-1-0 → desviar do empate compensa se 2·P(vitória) > P(derrota).
- Gatilho: |aval| ≤ 0,30 e (posição repetida ou ~20 meios-lances sem captura/lance de peão).
- Só no gatilho: MultiPV 3-5; escolher a melhor alternativa que não repete com aval ≥ -0,50.
- Freios: relógio baixo, sem material de mate, final de reis e peões com 0.00 em busca profunda → aceita o empate.
- Limiares são suposições; ajustar na arena.
- Validação: arena com pontuação 3-1-0, contra Stockfish forte e contra adversário fraco.
