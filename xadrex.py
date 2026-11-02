"""Xadrex — programa de partida do III Chess Challenge (linha de comando, offline)."""
import json
import math
import os
import time
from datetime import datetime
from pathlib import Path

import chess
import chess.engine

RAIZ = Path(__file__).resolve().parent
MOTOR = RAIZ / "engines" / "stockfish-windows-x86-64-universal.exe"
ESTADO = RAIZ / "partida_atual.json"
LOGS = RAIZ / "logs"
OPCOES_MOTOR = {"Threads": max(1, (os.cpu_count() or 2) - 2), "Hash": 512, "Move Overhead": 5000}
# shortcut: atraso humano fixo por lance (digitar, anunciar, mover, apertar relógio); a etapa 4 o torna adaptativo
ATRASO_HUMANO_MS = 5000
AJUDA = "Comandos: <lance UCI> | u (desfaz último par de lances) | tab | t mm:ss (acerta nosso relógio) | sair | fim"

motor = None


def abrir_motor():
    global motor
    if motor is not None:
        try:
            motor.quit()
        except Exception:
            pass
        motor = None
    # setpgrp: o Ctrl+C do console não chega ao Stockfish (senão ele morre junto)
    motor = chess.engine.SimpleEngine.popen_uci(str(MOTOR), setpgrp=True)
    motor.configure(OPCOES_MOTOR)


def ler_lance(board, texto):
    """Retorna o lance legal ou uma mensagem de erro (nunca levanta exceção)."""
    try:
        lance = chess.Move.from_uci(texto)
    except chess.InvalidMoveError:
        return f"'{texto}' não é UCI (ex.: e2e4, g1f3, e7e8q)."
    if lance in board.legal_moves:
        return lance
    return f"Lance ilegal: {texto}. Legais: {' '.join(sorted(m.uci() for m in board.legal_moves))}"


def desfazer(board, nossa):
    """Volta para antes do último lance do adversário (tira nosso lance e o dele)."""
    if len(board.move_stack) >= 2 and board.turn != nossa:
        board.pop()
        board.pop()
        return True
    return False


def fim_de_jogo(board):
    """Só o que já ocorreu: outcome(claim_draw=True) também conta repetição/50 lances possíveis no PRÓXIMO lance."""
    o = board.outcome()
    if o:
        return f"{o.result()} ({o.termination.name})"
    if board.is_repetition(3):
        return "1/2-1/2 (tripla repetição)"
    if board.is_fifty_moves():
        return "1/2-1/2 (regra dos 50 lances)"
    return None


def fmt_aval(score, nossa):
    if score is None:
        return "-"
    s = score.pov(nossa)
    return f"#{s.mate()}" if s.is_mate() else f"{s.score() / 100:+.2f}"


def fmt_relogio(ms):
    s = max(0, int(ms // 1000))
    return f"{s // 60}:{s % 60:02d}"


def ler_relogio(texto):
    m, s = (int(x) for x in texto.split(":"))
    if m < 0 or not 0 <= s < 60:
        raise ValueError(texto)
    return (m * 60 + s) * 1000


def desenhar(board):
    for i, linha in enumerate(str(board).splitlines()):
        print(8 - i, linha)
    print("  a b c d e f g h")


def registrar(log, linha):
    try:
        log.write(linha + "\n")
    except OSError as e:
        print(f"!! falha ao gravar o log ({e}); a partida continua")


def salvar(est, board):
    est["lances"] = [m.uci() for m in board.move_stack]
    tmp = ESTADO.with_suffix(".tmp")
    try:
        tmp.write_text(json.dumps(est, indent=1), encoding="utf-8")
        tmp.replace(ESTADO)  # troca atômica: queda no meio da escrita não corrompe o estado
    except OSError as e:  # ex.: antivírus segurando o arquivo no Windows
        print(f"!! falha ao salvar o estado ({e}); a partida continua")


def perguntar(msg, padrao):
    r = input(f"{msg} [{padrao}]: ").strip()
    return r or padrao


def perguntar_num(msg, padrao, minimo):
    while True:
        try:
            v = float(perguntar(msg, padrao).replace(",", "."))
            if math.isfinite(v) and v >= minimo:
                return v
        except ValueError:
            pass
        print(f"Digite um número >= {minimo:g}.")


def carregar_estado():
    """Lê e valida a partida salva; devolve (est, board) ou levanta exceção."""
    est = json.loads(ESTADO.read_text(encoding="utf-8"))
    if est["cor"] not in ("w", "b") or not all(isinstance(est[k], (int, float)) for k in ("nosso_ms", "inc_s")):
        raise ValueError("campos inválidos")
    str(est["log"])
    board = chess.Board()
    for u in est["lances"]:
        board.push_uci(u)  # levanta exceção se algum lance for ilegal
    return est, board


def iniciar():
    if ESTADO.exists():
        try:
            est, board = carregar_estado()
        except Exception as e:
            ruim = ESTADO.with_name(f"partida_invalida_{datetime.now():%Y%m%d_%H%M%S}.json")
            ESTADO.replace(ruim)
            print(f"!! partida salva inválida ({e!r}); guardada em {ruim.name}. Começando nova partida.")
        else:
            cor = "brancas" if est["cor"] == "w" else "pretas"
            if perguntar(f"Retomar partida salva ({cor}, {len(board.move_stack)} meios-lances)? s/n", "s").lower() == "s":
                return est, board
    cor = ""
    while cor not in ("b", "p"):
        cor = perguntar("Nossa cor: b = brancas, p = pretas", "b").lower()
    base = perguntar_num("Tempo base em minutos", "15", 1)
    inc = perguntar_num("Incremento em segundos", "10", 0)
    LOGS.mkdir(exist_ok=True)
    est = {
        "cor": "w" if cor == "b" else "b",
        "base_s": base * 60,
        "inc_s": inc,
        "nosso_ms": base * 60_000,
        "log": str(LOGS / f"partida_{datetime.now():%Y%m%d_%H%M%S}.log"),
        "lances": [],
    }
    with open(est["log"], "a", encoding="utf-8") as f:
        f.write(
            f"# Xadrex — {datetime.now():%Y-%m-%d %H:%M:%S}\n"
            f"# motor: Stockfish 19 (sf_19) {OPCOES_MOTOR}\n"
            f"# nossa cor: {'brancas' if est['cor'] == 'w' else 'pretas'} | tempo: {base:g} min + {inc:g} s\n"
            f"# aval = ponto de vista da nossa cor, em peões (#N = mate em N)\n"
        )
    return est, chess.Board()


def pensar(board, est):
    """Pede o lance ao motor; se falhar, reinicia uma vez com busca curta e, em último caso, joga um lance legal."""
    nosso = max(est["nosso_ms"], 1000) / 1000  # contagem interna pode ficar negativa; o motor precisa de valor positivo
    inc = est["inc_s"]
    limites = [
        chess.engine.Limit(white_clock=nosso, black_clock=nosso, white_inc=inc, black_inc=inc),
        chess.engine.Limit(time=0.5),  # 2ª tentativa curta: a falha já gastou relógio
    ]
    for i, limite in enumerate(limites):
        try:
            if i or motor is None:
                abrir_motor()
            r = motor.play(board, limite, info=chess.engine.INFO_ALL)
            if r.move in board.legal_moves:
                return r.move, r.info, ""
        except Exception as e:
            print(f"!! motor falhou ({e!r})")
    return next(iter(board.legal_moves)), {}, " fallback=primeiro-lance-legal"


def jogar_nosso_lance(board, est, nossa, log, t0):
    print("... pensando")
    lance, info, obs = pensar(board, est)
    gasto = time.monotonic() - t0
    num, san = board.fullmove_number, board.san(lance)
    board.push(lance)
    est["nosso_ms"] += est["inc_s"] * 1000 - gasto * 1000 - ATRASO_HUMANO_MS
    print(f"\n>>> NOSSO LANCE: {lance.uci()}   ({san})")
    print(f"    aval {fmt_aval(info.get('score'), nossa)} | prof {info.get('depth', '-')} | {gasto:.1f}s | "
          f"nosso relógio ~{fmt_relogio(est['nosso_ms'])}\n")
    pv = " ".join(m.uci() for m in info.get("pv", []))
    registrar(log,
              f"lance={num} cor={'brancas' if nossa else 'pretas'} uci={lance.uci()} prof={info.get('depth', '-')} "
              f"nos={info.get('nodes', '-')} aval={fmt_aval(info.get('score'), nossa)} pv={pv or '-'} "
              f"tempo={gasto:.2f}s relogio={fmt_relogio(est['nosso_ms'])}{obs}")


def encerrar(log, motivo):
    registrar(log, f"# FIM: {motivo}")
    print(f"\nFIM: {motivo}")
    ESTADO.unlink(missing_ok=True)


def partida(est, board, log):
    nossa = chess.WHITE if est["cor"] == "w" else chess.BLACK
    print(AJUDA)
    desenhar(board)
    t0 = time.monotonic()
    while True:
        fim = fim_de_jogo(board)  # o árbitro declara repetição e 50 lances sem reclamação
        if fim:
            encerrar(log, fim)
            return
        if board.turn == nossa:
            try:
                jogar_nosso_lance(board, est, nossa, log, t0)
            except KeyboardInterrupt:
                print("\n(Ctrl+C ignorado; recalculando. Use 'sair' para fechar.)")
                continue
            salvar(est, board)
            continue
        try:
            texto = input("Lance do adversário (UCI): ").strip().lower()
        except KeyboardInterrupt:
            print("\n(use 'sair' para fechar)")
            continue
        except EOFError:
            return
        if texto == "sair":
            print(f"Estado salvo em {ESTADO.name}; rode de novo para retomar.")
            return
        if texto == "fim":
            encerrar(log, input("Motivo (ex.: abandono, tempo, empate acordado): ").strip() or "encerrada pelo operador")
            return
        if texto in ("tab", "?"):
            desenhar(board)
            print(f"lances: {' '.join(m.uci() for m in board.move_stack) or '-'}")
            print(AJUDA)
            continue
        if texto == "u":
            if desfazer(board, nossa):
                registrar(log, f"# desfeito: voltou para {len(board.move_stack)} meios-lances")
                salvar(est, board)
                print("Desfeito. Digite o lance correto do adversário.")
            else:
                print("Nada para desfazer.")
            continue
        if texto.startswith("t "):
            try:
                est["nosso_ms"] = ler_relogio(texto[2:])
                salvar(est, board)
                print(f"Nosso relógio: {fmt_relogio(est['nosso_ms'])}")
            except ValueError:
                print("Use: t mm:ss (segundos de 00 a 59)")
            continue
        lance = ler_lance(board, texto)
        if isinstance(lance, str):
            print(lance)
            continue
        num = board.fullmove_number
        board.push(lance)
        t0 = time.monotonic()
        registrar(log, f"lance={num} cor={'pretas' if nossa else 'brancas'} uci={lance.uci()} (adversário)")
        salvar(est, board)


def main():
    est, board = iniciar()
    try:
        abrir_motor()
    except Exception as e:
        print(f"!! motor não abriu ({e!r}); vou tentar de novo no nosso lance")
    try:
        with open(est["log"], "a", encoding="utf-8", buffering=1) as log:
            partida(est, board, log)
    finally:  # sem quit(), a thread do motor segura o processo aberto após um erro
        if motor is not None:
            try:
                motor.quit()
            except Exception:
                pass


if __name__ == "__main__":
    main()
