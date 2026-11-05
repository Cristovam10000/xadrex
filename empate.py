"""Anti-empate com risco limitado — regras de decisão (funções puras, sem motor).

Pontuação do torneio 3-1-0: sair de um empate compensa se 2·P(vitória) > P(derrota). Quando a busca normal
escolhe um lance que repete posição (ou a partida está parada há muitos meios-lances) com avaliação perto de
zero, o xadrex.py faz uma 2ª busca curta só entre lances que não repetem e troca de lance se a melhor
alternativa não for pior que PISO_CP. Ligado por padrão; XADREX_ANTIEMPATE=0 desliga (ver xadrex.ANTIEMPATE).

SUPOSIÇÕES: nenhum limiar abaixo foi medido; calibrar na arena.
"""
import chess

JANELA_CP = 30           # |aval| <= isto (centipeões, nosso ponto de vista) = posição de empate
PISO_CP = -50            # pior avaliação aceitável da alternativa que não repete
SEM_PROGRESSO = 20       # meios-lances sem captura nem lance de peão (board.halfmove_clock)
RELOGIO_MIN_MS = 60_000  # abaixo disto não gasta relógio tentando desviar
FRACAO_BUSCA = 0.5       # 2ª busca: fração do alvo do lance, com teto no que sobra do máximo
# piso da 2ª busca: no final do 10+0 o alvo do lance cai para 0,1-0,4 s e a 2ª busca nem rodava (arena 04/11: 40 de
# 51 gatilhos barrados por "sem-tempo"). Passa do máximo do lance de propósito; o freio de RELOGIO_MIN_MS limita o custo.
BUSCA_MIN_MS = 1000


def repete(board, lance):
    """O lance leva a uma posição que já ocorreu na partida? (is_repetition(2) conta a posição atual)"""
    board.push(lance)
    try:
        return board.is_repetition(2)
    finally:
        board.pop()


def progride(board, lance):
    """Captura ou lance de peão: zera o contador dos 50 lances."""
    return board.is_capture(lance) or board.piece_type_at(lance.from_square) == chess.PAWN


def gatilho(board, lance, aval_cp):
    """'repeticao', 'sem-progresso' ou None. Mate nunca dispara: fica fora da janela."""
    if aval_cp is None or abs(aval_cp) > JANELA_CP:
        return None
    if repete(board, lance):
        return "repeticao"
    if board.halfmove_clock >= SEM_PROGRESSO and not progride(board, lance):
        return "sem-progresso"
    return None


def freio(board, nossa, relogio_ms):
    """Motivo para aceitar o empate sem tentar desviar, ou None."""
    if relogio_ms < RELOGIO_MIN_MS:
        return "relogio"
    if board.legal_moves.count() == 1:
        return "lance-unico"
    if board.has_insufficient_material(nossa):
        return "sem-material"
    if not (board.knights | board.bishops | board.rooks | board.queens):
        return "reis-e-peoes"  # 0.00 em busca profunda aqui costuma ser empate exato; desviar perde
    return None


def candidatos(board, lance, motivo):
    """Lances que não repetem posição; em 'sem-progresso', só capturas e lances de peão (os que zeram o contador)."""
    lances = [m for m in board.legal_moves if m != lance and not repete(board, m)]
    if motivo == "sem-progresso":
        lances = [m for m in lances if progride(board, m)]
    return lances


def tempo_busca(alvo_ms, maximo_ms, gasto_ms):
    """Orçamento da 2ª busca: FRACAO_BUSCA do alvo, sem passar do máximo do lance (o que já foi gasto sai dele),
    mas nunca abaixo de BUSCA_MIN_MS."""
    return max(BUSCA_MIN_MS, min(FRACAO_BUSCA * alvo_ms, maximo_ms - gasto_ms))


def desviar(aval_alternativa_cp):
    """Troca de lance só se a alternativa (avaliação de iteração completa) não for pior que o piso."""
    return aval_alternativa_cp is not None and aval_alternativa_cp >= PISO_CP
