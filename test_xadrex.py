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


def test_sem_motor_nao_inicia():
    import builtins
    with tempfile.TemporaryDirectory() as d:
        originais = xadrex.COMANDO_MOTOR, xadrex.ESTADO, builtins.input
        xadrex.COMANDO_MOTOR = [str(Path(d) / "nao-existe.exe")]
        xadrex.ESTADO = Path(d) / "partida_atual.json"
        salvo = '{"cor": "w", "lances": ["e2e4"]}'
        xadrex.ESTADO.write_text(salvo, encoding="utf-8")

        def sem_perguntas(*_):
            raise AssertionError("não pode perguntar nada sem motor")
        builtins.input = sem_perguntas
        try:
            assert xadrex.main() == 1  # código de saída != 0, sem iniciar partida
            assert xadrex.ESTADO.read_text(encoding="utf-8") == salvo  # retomada preservada
            assert [p.name for p in Path(d).iterdir()] == ["partida_atual.json"]
        finally:
            xadrex.COMANDO_MOTOR, xadrex.ESTADO, builtins.input = originais


def teclas(texto):
    it = iter(texto)
    return lambda: next(it)


def test_ler_teclas():
    eco = []
    assert xadrex.ler_teclas(teclas("e7e5\r"), eco.append)[0] == "e7e5" and "".join(eco) == "e7e5\n"
    assert xadrex.ler_teclas(teclas("e7\x08\x08\x08g1f3\r"), eco.append)[0] == "g1f3"  # backspace a mais não quebra
    assert xadrex.ler_teclas(teclas("\xe0Ke2\x00;e4\r"), eco.append)[0] == "e2e4"  # seta/F1 no Windows
    assert xadrex.ler_teclas(teclas("\x1b[Ae2\x1b[1;5Ce4\n"), eco.append)[0] == "e2e4"  # setas no terminal Unix
    assert xadrex.ler_teclas(teclas("\x01\te2e4 1:31\r"), eco.append)[0] == "e2e4 1:31"  # controle ignorado
    texto, primeira, enter = xadrex.ler_teclas(teclas("\r"), eco.append)
    assert texto == "" and primeira == enter

    def devagar():  # 1ª tecla e depois 50 ms até o ENTER
        yield "e"
        time.sleep(0.05)
        yield "\r"
    g = devagar()
    texto, primeira, enter = xadrex.ler_teclas(lambda: next(g), eco.append)
    assert texto == "e" and enter - primeira >= 0.05
    try:
        xadrex.ler_teclas(teclas("e2\x03"), eco.append)
        raise AssertionError("Ctrl+C")
    except KeyboardInterrupt:
        pass


def test_entrada_simples():
    import contextlib
    import io
    import sys
    import types
    from dataclasses import asdict
    originais = xadrex.ENTRADA_SIMPLES, sys.stdin
    xadrex.input = lambda prompt: "e7e5"  # sombreia o input() embutido só dentro de xadrex
    sys.stdin = types.SimpleNamespace(isatty=lambda: True)  # "terminal": sem a chave tentaria msvcrt/termios
    aberto = {"relogio": 600_000, "inicio": 100.0, "t0": 102.0, "busca": 3000, "mostrado": 105.0, "num": 1}

    def fechar():
        est = {"inc_s": 0, "k": 0, "atraso": asdict(xadrex.tempo.AtrasoHumano()), "exigir_leitura": False}
        with contextlib.redirect_stdout(io.StringIO()):
            xadrex.fechar_relogio(est, aberto, 110.0, True, io.StringIO())
        return est
    try:
        xadrex.ENTRADA_SIMPLES = True
        texto, primeira, enter = xadrex.ler_linha("> ")
        assert texto == "e7e5" and primeira == enter  # sem instante da 1ª tecla
        est = fechar()
        # sem medir a digitação o relógio interno conta a menos: lance não medido e k volta a contar (regra antiga)
        assert not est["medido"] and est["k"] == 1
        est["k"] = xadrex.tempo.LEITURA_A_CADA
        assert xadrex.leitura_obrigatoria(est)  # relógio em ~9:52, mas 8 lances sem leitura
        xadrex.ENTRADA_SIMPLES = False
        est = fechar()
        assert est["medido"] and est["k"] == 0
    finally:
        del xadrex.input
        xadrex.ENTRADA_SIMPLES, sys.stdin = originais


def test_partida_relogio_automatico():
    """Somos pretas em 10+0, com relógio e leitor de teclas falsos. Cobre ENTER ao bater o relógio, Ctrl+C no
    prompt, ENTER esquecido (lance digitado direto), leitura opcional aceita graças à folga e 'u'."""
    import contextlib
    import io
    import types
    agora = [100.0]
    roteiro = [  # (texto, segundos até a 1ª tecla, segundos digitando)
        ("e2e4", 10, 2),          # 1ª tecla 110, ENTER 112
        (KeyboardInterrupt, 1, 0),  # Ctrl+C no prompt do ENTER: o nosso tempo continua aberto
        ("", 3, 0),               # ENTER ao bater o relógio em 119
        ("g1f3", 20, 1.5),        # adversário pensou 20 s (nosso relógio parado); 1ª tecla 139, ENTER 140,5
        ("f1c4", 30, 1),          # ENTER esquecido: 1ª tecla em 172,5 fecha o nosso tempo e já é o lance
        ("", 1, 0),               # ENTER em 176,5
        ("d2d3 9:30", 5, 2),      # leitura acima do relógio interno, mas dentro da folga do ENTER esquecido
        ("u", 1, 0),
        ("sair", 1, 0),
    ]
    nossos = iter(["e7e5", "b8c6", "g8f6", "f8c5"])
    vistos = []

    def ler_linha(_prompt):
        vistos.append(json.loads(json.dumps(est)))
        texto, espera, digitar = roteiro.pop(0)
        agora[0] += espera
        primeira = agora[0]
        if texto is KeyboardInterrupt:
            raise KeyboardInterrupt
        agora[0] += digitar
        return texto, primeira, agora[0]

    def pensar(board, est, nossa, t0):
        agora[0] += 3 if board.fullmove_number == 1 else 2  # busca
        return chess.Move.from_uci(next(nossos)), {}, xadrex.tempo.ControleBusca(1000, 1000), "teste"

    originais = xadrex.ler_linha, xadrex.pensar, xadrex.time, xadrex.ESTADO
    with tempfile.TemporaryDirectory() as d:
        xadrex.ler_linha, xadrex.pensar = ler_linha, pensar
        xadrex.time = types.SimpleNamespace(monotonic=lambda: agora[0], sleep=time.sleep)
        xadrex.ESTADO = Path(d) / "partida_atual.json"
        est = {"cor": "b", "base_s": 600, "inc_s": 0, "previsto_ms": 600_000, "k": 0, "exigir_leitura": False,
               "medido": False, "folga_ms": 0, "atraso": {"media": 5000, "desvio": 2500, "amostras": 0},
               "aval_anterior": None, "log": "x", "lances": []}
        log = io.StringIO()
        try:
            with contextlib.redirect_stdout(io.StringIO()):
                xadrex.partida(est, chess.Board(), log)
        finally:
            xadrex.ler_linha, xadrex.pensar, xadrex.time, xadrex.ESTADO = originais
    prev = [v["previsto_ms"] for v in vistos]
    assert prev[1] == prev[2] == 600_000 - 2000 - 1000  # relógio em t0: desconta ouvir (1 s) e digitar (2 s)
    # 1º lance: 1ª tecla 110 -> ENTER ao bater 119: gasto 9 s + ouvir 1 s; busca 3 s; parte humana 7 s
    assert prev[3] == 590_000 and vistos[3]["medido"] and vistos[3]["atraso"]["media"] == 7000
    assert prev[4] == 590_000 - 1500 - 1000
    # ENTER esquecido: fecha na 1ª tecla (172,5), conta a mais o tempo do adversário; não ensina o atraso
    assert prev[5] == 587_500 - (172.5 - 140.5) * 1000 - 1000 - 1000  # e já desconta ouvir/digitar do lance novo
    assert vistos[5]["atraso"]["media"] == 7000 and vistos[5]["folga_ms"] == (172.5 - 142.5) * 1000
    assert prev[6] == prev[5] - 3000 and vistos[6]["atraso"]["media"] == 6500  # parte humana 3 s
    assert not xadrex.leitura_obrigatoria({**vistos[6], "previsto_ms": 60_000})  # medido: abaixo de 2 min, opcional
    assert xadrex.leitura_obrigatoria({**vistos[6], "previsto_ms": 60_000, "medido": False})  # sem medição: regra antiga
    assert prev[7] == 570_000 and vistos[7]["folga_ms"] == 0  # leitura 9:30 aceita (dentro da folga)
    assert vistos[8]["exigir_leitura"] and not vistos[8]["medido"]  # depois de 'u'
    texto = log.getvalue()
    assert texto.count("relogio lance=") == 4 and "fim_por=tecla" in texto and "humano=7.00s" in texto
    assert est["lances"] == ["e2e4", "e7e5", "g1f3", "b8c6", "f1c4", "g8f6"]  # 'u' tirou d2d3 e f8c5
    assert not roteiro


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
