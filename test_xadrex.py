"""Testes rápidos: .venv\\Scripts\\python.exe test_xadrex.py"""
import json
import tempfile
from pathlib import Path

import chess
import chess.engine

import xadrex
from xadrex import carregar_estado, desfazer, fim_de_jogo, fmt_aval, ler_lance, ler_relogio


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
        for conteudo in ("{", "{}", json.dumps({"cor": "w", "nosso_ms": 1, "inc_s": 0, "log": "x", "lances": ["e2e5"]})):
            xadrex.ESTADO.write_text(conteudo, encoding="utf-8")
            try:
                carregar_estado()
                raise AssertionError(conteudo)
            except AssertionError:
                raise
            except Exception:
                pass
        xadrex.ESTADO.write_text(json.dumps({"cor": "b", "nosso_ms": 9e5, "inc_s": 10, "log": "x", "lances": ["e2e4"]}),
                                 encoding="utf-8")
        est, board = carregar_estado()
        assert board.turn == chess.BLACK and est["cor"] == "b"


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
