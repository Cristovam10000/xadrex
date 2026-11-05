"""Testes das regras do anti-empate (sem motor): .venv\\Scripts\\python.exe test_empate.py"""
import chess

import empate

M = chess.Move.from_uci


def vai_e_volta():
    """Posição inicial de novo, brancas a jogar: g1f3 leva a uma posição que já ocorreu."""
    b = chess.Board()
    for u in "g1f3 g8f6 f3g1 f6g8".split():
        b.push_uci(u)
    return b


TORRES = "2r3k1/5pp1/7p/8/8/7P/5PP1/3R2K1 w - - 20 40"  # 20 meios-lances sem captura nem lance de peão


def test_gatilho_repeticao():
    b = vai_e_volta()
    assert empate.repete(b, M("g1f3")) and not empate.repete(b, M("b1c3"))
    assert len(b.move_stack) == 4  # repete() devolve o tabuleiro como estava
    assert empate.gatilho(b, M("g1f3"), 0) == "repeticao"
    assert empate.gatilho(b, M("g1f3"), -empate.JANELA_CP) == "repeticao"
    assert empate.gatilho(b, M("g1f3"), empate.JANELA_CP + 1) is None  # fora da janela: não é empate
    assert empate.gatilho(b, M("g1f3"), None) is None  # sem iteração completa
    assert empate.gatilho(b, M("g1f3"), 100_000) is None  # mate fica fora da janela
    assert empate.gatilho(b, M("b1c3"), 0) is None  # não repete e o contador está em 4


def test_gatilho_sem_progresso():
    b = chess.Board(TORRES)
    assert empate.gatilho(b, M("d1d7"), 10) == "sem-progresso"
    assert empate.gatilho(b, M("g2g3"), 10) is None  # lance de peão já é progresso
    assert empate.gatilho(chess.Board(TORRES.replace(" 20 40", " 19 40")), M("d1d7"), 10) is None


def test_freios():
    b = chess.Board(TORRES)
    assert empate.freio(b, chess.WHITE, empate.RELOGIO_MIN_MS) is None
    assert empate.freio(b, chess.WHITE, empate.RELOGIO_MIN_MS - 1) == "relogio"
    assert empate.freio(chess.Board("7k/8/8/8/8/8/r7/K7 w - - 30 60"), chess.WHITE, 300_000) == "sem-material"
    assert empate.freio(chess.Board("8/5pk1/6p1/8/8/6P1/5PK1/8 w - - 30 60"), chess.WHITE, 300_000) == "reis-e-peoes"
    unico = chess.Board("7k/8/8/8/8/8/1r6/K6r w - - 30 60")  # só Kxb2 sai do xeque
    assert unico.legal_moves.count() == 1 and empate.freio(unico, chess.WHITE, 300_000) == "lance-unico"


def test_candidatos():
    b = vai_e_volta()
    c = empate.candidatos(b, M("g1f3"), "repeticao")
    assert M("g1f3") not in c and len(c) == 19  # os outros 19 lances iniciais não repetem
    t = chess.Board(TORRES)
    c = empate.candidatos(t, M("d1d7"), "sem-progresso")
    assert c and all(t.piece_type_at(m.from_square) == chess.PAWN or t.is_capture(m) for m in c)
    assert empate.candidatos(chess.Board("4k3/8/8/8/8/8/8/R3K2r w - - 20 40"), M("a1a2"), "sem-progresso") == []


def test_tempo_e_decisao():
    assert empate.tempo_busca(6000, 20_000, 1000) == 3000  # metade do alvo
    assert empate.tempo_busca(6000, 3500, 1000) == 2500    # teto: o que sobra do máximo
    assert empate.tempo_busca(200, 200, 200) == empate.BUSCA_MIN_MS  # final do 10+0: piso, não 0
    assert empate.desviar(empate.PISO_CP) and empate.desviar(0)
    assert not empate.desviar(empate.PISO_CP - 1) and not empate.desviar(None)


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
