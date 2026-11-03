"""Testes rápidos: .venv\\Scripts\\python.exe test_xadrex.py"""
import json
import tempfile
import time
from pathlib import Path

import chess
import chess.engine

import xadrex
from xadrex import calibrar, carregar_estado, desfazer, fim_de_jogo, fmt_aval, ler_lance, ler_relogio


def test_ler_lance():
    b = chess.Board()
    assert ler_lance(b, "e2e4") == chess.Move.from_uci("e2e4")
    assert isinstance(ler_lance(b, "e2e5"), str)  # ilegal
    assert isinstance(ler_lance(b, "0000"), str)  # lance nulo não pode passar
    assert isinstance(ler_lance(b, "xyz"), str)
    p = chess.Board("8/4P3/8/8/8/8/k7/4K3 w - - 0 1")
    assert isinstance(ler_lance(p, "e7e8"), str)  # promoção sem a peça
    assert ler_lance(p, "e7e8n") == chess.Move.from_uci("e7e8n")
    r = chess.Board("r3k2r/8/8/8/8/8/8/R3K2R w KQkq - 0 1")
    assert ler_lance(r, "e1g1") in r.legal_moves  # roque
    ep = chess.Board("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1")
    assert ler_lance(ep, "e5d6") in ep.legal_moves  # en passant


def test_desfazer():
    b = chess.Board()
    assert not desfazer(b, chess.WHITE)
    b.push_uci("e2e4")  # nosso (brancas)
    assert not desfazer(b, chess.WHITE)  # só nosso lance: nada do adversário para corrigir
    b.push_uci("e7e5")
    b.push_uci("g1f3")
    assert desfazer(b, chess.WHITE) and [m.uci() for m in b.move_stack] == ["e2e4"]
    b = chess.Board()
    b.push_uci("e2e4")  # adversário (somos pretas)
    b.push_uci("c7c5")
    assert desfazer(b, chess.BLACK) and not b.move_stack


def test_formatos():
    assert fmt_aval(chess.engine.PovScore(chess.engine.Cp(35), chess.WHITE), chess.BLACK) == "-0.35"
    assert fmt_aval(chess.engine.PovScore(chess.engine.Mate(3), chess.BLACK), chess.BLACK) == "#3"
    assert fmt_aval(None, chess.WHITE) == "-"
    assert ler_relogio("12:05") == 725_000
    for ruim in ("2:99", "-1:00", "5", "a:b"):
        try:
            ler_relogio(ruim)
            raise AssertionError(ruim)
        except ValueError:
            pass


def test_fim_de_jogo():
    b = chess.Board()
    for u in "g1f3 g8f6 f3g1 f6g8 g1f3 g8f6 f3g1".split():
        b.push_uci(u)
    assert fim_de_jogo(b) is None  # repetição só possível no próximo lance: o jogo continua
    b.push_uci("f6g8")
    assert "repetição" in fim_de_jogo(b)
    assert fim_de_jogo(chess.Board("4k3/8/8/8/8/8/8/R3K3 w - - 99 80")) is None
    assert "50" in fim_de_jogo(chess.Board("4k3/8/8/8/8/8/8/R3K3 w - - 100 80"))
    assert fim_de_jogo(chess.Board("7k/6Q1/6K1/8/8/8/8/8 b - - 0 1")).startswith("1-0")  # mate


def test_carregar_estado():
    with tempfile.TemporaryDirectory() as d:
        xadrex.ESTADO = Path(d) / "partida_atual.json"
        base = {"cor": "b", "previsto_ms": 9e5, "inc_s": 10, "k": 0, "atraso": {"media": 5000, "desvio": 2500},
                "aval_anterior": None, "log": "x", "lances": ["e2e4"]}
        for conteudo in ("{", "{}", json.dumps({**base, "lances": ["e2e5"]}), json.dumps({**base, "atraso": {"x": 1}})):
            xadrex.ESTADO.write_text(conteudo, encoding="utf-8")
            try:
                carregar_estado()
                raise AssertionError(conteudo)
            except AssertionError:
                raise
            except Exception:
                pass
        xadrex.ESTADO.write_text(json.dumps(base), encoding="utf-8")
        est, board = carregar_estado()
        assert board.turn == chess.BLACK and est["cor"] == "b"


def test_calibrar():
    est = {"previsto_ms": 600_000, "k": 2, "atraso": {"media": 5000, "desvio": 2500, "amostras": 0}}
    calibrar(est, 590_000)  # 10 s a menos que o previsto em 2 lances: 5 s a mais por lance
    assert est["atraso"]["media"] == 10_000 and est["previsto_ms"] == 590_000 and est["k"] == 0
    calibrar(est, 500_000)  # k=0: só corrige o relógio, não aprende
    assert est["atraso"]["media"] == 10_000 and est["previsto_ms"] == 500_000
    antes = json.dumps(est)
    assert not calibrar(est, 600_000) and json.dumps(est) == antes  # leitura impossível não muda nada


MOTOR_TRAVADO = r'''
import sys
for linha in sys.stdin:
    c = linha.split()
    if not c: continue
    if c[0] == "uci":
        print("id name Travado\noption name Threads type spin default 1 min 1 max 512\n"
              "option name Hash type spin default 16 min 1 max 4096\nuciok", flush=True)
    elif c[0] == "isready":
        print("readyok", flush=True)
    elif c[0] == "go":  # uma iteração e depois nunca responde, nem ao stop
        print("info depth 1 score cp 12 nodes 20 time 1 pv e2e4", flush=True)
'''


def test_motor_travado():
    import sys
    with tempfile.TemporaryDirectory() as d:
        falso = Path(d) / "travado.py"
        falso.write_text(MOTOR_TRAVADO, encoding="utf-8")
        original = xadrex.COMANDO_MOTOR
        xadrex.COMANDO_MOTOR = [sys.executable, "-u", str(falso)]
        try:
            for relogio, limite_s in ((20_000, 10), (5_500, 1.5)):  # com pouco relógio, o vigia não espera 3 s
                est = {"previsto_ms": relogio, "inc_s": 0, "atraso": {"media": 5000, "desvio": 2500, "amostras": 0},
                       "aval_anterior": None}
                xadrex.abrir_motor()  # aberto antes, como na partida: o tempo medido é só o da busca
                t = time.monotonic()
                lance, info, _, motivo = xadrex.pensar(chess.Board(), est, chess.WHITE, t)
                assert lance == chess.Move.from_uci("e2e4") and info["depth"] == 1 and "travou" in motivo
                assert time.monotonic() - t < limite_s and xadrex.motor is None, (relogio, time.monotonic() - t)
        finally:
            xadrex.matar_motor()
            xadrex.COMANDO_MOTOR = original


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
