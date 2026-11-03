"""Xadrex — programa de partida do III Chess Challenge (linha de comando, offline)."""
import json
import logging
import math
import os
import time
from dataclasses import asdict
from datetime import datetime
from pathlib import Path

import chess
import chess.engine

import tempo

RAIZ = Path(__file__).resolve().parent
COMANDO_MOTOR = [str(RAIZ / "engines" / "stockfish-windows-x86-64-universal.exe")]
ESTADO = RAIZ / "partida_atual.json"
LOGS = RAIZ / "logs"
OPCOES_MOTOR = {"Threads": max(1, (os.cpu_count() or 2) - 2), "Hash": 512}
AJUDA = ("Comandos: <lance UCI> [mm:ss do nosso relógio] | u (desfaz último par de lances) | tab | sair | fim\n"
         "Ex.: 'e7e5 12:31' registra o lance e calibra o gestor de tempo com o relógio físico.")

motor = None
logging.getLogger("asyncio").setLevel(logging.CRITICAL)  # motor morto pelo vigia gera aviso inofensivo no console


def abrir_motor():
    global motor
    matar_motor()
    # setpgrp: o Ctrl+C do console não chega ao Stockfish (senão ele morre junto)
    motor = chess.engine.SimpleEngine.popen_uci(COMANDO_MOTOR, setpgrp=True, timeout=5)
    motor.configure(OPCOES_MOTOR)
    motor.timeout = 2.0  # prazo para comandos fora da busca, inclusive para a análise *começar* (padrão: 10 s)


def matar_motor():
    global motor
    m, motor = motor, None
    if m is not None:
        try:
            m.close()
        except Exception:
            pass


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


def calibrar(est, leitura_ms):
    """Leitura do relógio físico no momento da entrada do lance adversário: corrige a estimativa e,
    se houve lances nossos desde a última leitura, ensina ao gestor o atraso humano médio deles.
    Devolve False (sem alterar nada) se a leitura for impossível, ex.: 2:00 digitado no lugar de 0:20."""
    atraso = tempo.AtrasoHumano(**est["atraso"])
    if not tempo.leitura_plausivel(est["previsto_ms"], est["k"], atraso, leitura_ms):
        return False
    if est["k"] > 0:
        atraso.observar(atraso.media + (est["previsto_ms"] - leitura_ms) / est["k"])
        est["atraso"] = asdict(atraso)
    est["previsto_ms"], est["k"], est["exigir_leitura"] = leitura_ms, 0, False
    return True


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
    if est["cor"] not in ("w", "b") or not all(isinstance(est[k], (int, float)) for k in ("previsto_ms", "inc_s", "k")):
        raise ValueError("campos inválidos")
    tempo.AtrasoHumano(**est["atraso"])
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
                while True:
                    r = perguntar("Nosso relógio agora (mm:ss)", fmt_relogio(est["previsto_ms"]))
                    try:
                        est["previsto_ms"], est["k"], est["exigir_leitura"] = ler_relogio(r), 0, False
                        return est, board
                    except ValueError:
                        print("Use mm:ss")
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
        "previsto_ms": base * 60_000,  # nosso relógio estimado no momento em que começamos a pensar
        "k": 0,                        # lances nossos desde a última leitura do relógio físico
        "exigir_leitura": False,       # ligado após 'u': o incremento creditado pode não ter existido
        "atraso": asdict(tempo.AtrasoHumano()),
        "aval_anterior": None,
        "log": str(LOGS / f"partida_{datetime.now():%Y%m%d_%H%M%S}.log"),
        "lances": [],
    }
    with open(est["log"], "a", encoding="utf-8") as f:
        f.write(
            f"# Xadrex — {datetime.now():%Y-%m-%d %H:%M:%S}\n"
            f"# motor: Stockfish 19 (sf_19) {OPCOES_MOTOR}; gestão de tempo: tempo.py (autoria da equipe)\n"
            f"# nossa cor: {'brancas' if est['cor'] == 'w' else 'pretas'} | tempo: {base:g} min + {inc:g} s\n"
            f"# aval = ponto de vista da nossa cor, em peões (#N = mate em N)\n"
        )
    return est, chess.Board()


def buscar(board, controle, nossa, ultimo, prazo_ms):
    """Roda a busca do Stockfish sob o comando do gestor de tempo. `ultimo` recebe a última iteração completa;
    passado `prazo_ms` sem bestmove, o motor é morto e vale a última iteração completa."""
    t0 = time.monotonic()
    motivo = None
    an = motor.analysis(board, chess.engine.Limit(time=controle.maximo / 1000), info=chess.engine.INFO_ALL)
    try:
        while True:
            try:
                while not an.would_block():
                    info = an.get()
                    if "pv" in info and "score" in info and not info.get("lowerbound") and not info.get("upperbound"):
                        controle.iteracao(info.get("depth", 0), info["pv"][0], tempo.aval_cp(info["score"].pov(nossa)))
                        ultimo.clear()
                        ultimo.update(info)
            except chess.engine.AnalysisComplete:
                break
            ms = (time.monotonic() - t0) * 1000
            if motivo is None:
                motivo = controle.parar(ms)
                if motivo:
                    an.stop()
            if ms > prazo_ms:  # não respondeu ao stop a tempo: travado
                matar_motor()
                if controle.lance is None:
                    raise RuntimeError("motor travou sem nenhuma iteração completa")
                return controle.lance, dict(ultimo), "motor-travou;melhor-da-busca"
            time.sleep(0.005)
    except BaseException:
        if motor is not None:
            try:
                an.stop()
            except Exception:
                pass
        raise
    melhor = an.wait().move
    info = dict(an.info)  # nós e tempo totais
    if ultimo.get("pv") and ultimo["pv"][0] == melhor:  # profundidade/avaliação/PV da última iteração completa
        info.update({k: ultimo[k] for k in ("depth", "seldepth", "score", "pv") if k in ultimo})
    return melhor, info, motivo or "maximo"


def pensar(board, est, nossa, t0):
    """Pede o lance ao motor sob o gestor; se falhar, reinicia uma vez com busca curta e, no fim, joga um lance legal.
    O relógio usado é o previsto na entrada do lance adversário menos o que já passou desde então (t0)."""
    atraso = tempo.AtrasoHumano(**est["atraso"])
    unico = board.legal_moves.count() == 1
    for tentativa in range(2):
        relogio = est["previsto_ms"] - (time.monotonic() - t0) * 1000
        if tentativa == 0:
            alvo, maximo = tempo.orcamento(relogio, est["inc_s"] * 1000, atraso, tempo.fase(board),
                                           board.fullmove_number)
        else:  # 2ª tentativa curta, depois de uma falha que já gastou relógio
            alvo = maximo = min(500, max(tempo.EMERGENCIA_MS, (relogio - atraso.media) / 4))
        controle = tempo.ControleBusca(alvo, maximo, est["aval_anterior"], unico)
        # o vigia nunca espera além do que o relógio físico permite (menos a parte humana do lance)
        prazo = min(maximo + tempo.VIGIA_MS, max(maximo + 300, relogio - atraso.media))
        ultimo = {}
        try:
            if tentativa or motor is None:
                abrir_motor()
            lance, info, motivo = buscar(board, controle, nossa, ultimo, prazo)
            if lance in board.legal_moves:
                return lance, info, controle, motivo
        except Exception as e:
            print(f"!! motor falhou ({e!r})")
            if controle.lance is not None and controle.lance in board.legal_moves:
                return controle.lance, dict(ultimo), controle, "falha-motor;melhor-da-busca"
    return next(iter(board.legal_moves)), {}, controle, "fallback=primeiro-lance-legal"


def jogar_nosso_lance(board, est, nossa, log, t0):
    print("... pensando")
    relogio = est["previsto_ms"]
    lance, info, controle, motivo = pensar(board, est, nossa, t0)
    gasto = time.monotonic() - t0
    num, san = board.fullmove_number, board.san(lance)
    board.push(lance)
    atraso = tempo.AtrasoHumano(**est["atraso"])
    est["previsto_ms"] = relogio - gasto * 1000 + est["inc_s"] * 1000 - atraso.media
    est["k"] += 1
    if controle.aval is not None:  # só iteração completa: linhas lowerbound/upperbound não são avaliação exata
        est["aval_anterior"] = controle.aval
    aval = fmt_aval(info.get("score"), nossa)
    print(f"\n>>> NOSSO LANCE: {lance.uci()}   ({san})")
    print(f"    aval {aval} | prof {info.get('depth', '-')} | {gasto:.1f}s (alvo {controle.alvo / 1000:.1f}s, "
          f"parou: {motivo}) | relógio ~{fmt_relogio(est['previsto_ms'])} na próxima vez\n")
    pv = " ".join(m.uci() for m in info.get("pv", []))
    registrar(log,
              f"lance={num} cor={'brancas' if nossa else 'pretas'} uci={lance.uci()} prof={info.get('depth', '-')} "
              f"nos={info.get('nodes', '-')} aval={aval} pv={pv or '-'} tempo={gasto:.2f}s "
              f"relogio_inicio={fmt_relogio(relogio)} alvo={controle.alvo / 1000:.1f}s max={controle.maximo / 1000:.1f}s "
              f"parada={motivo} atraso={atraso.media / 1000:.1f}s/{atraso.seguro / 1000:.1f}s")


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
        exigir = est.get("exigir_leitura") or tempo.precisa_leitura(est["previsto_ms"], est["k"])
        try:
            texto = input("Lance do adversário + NOSSO RELÓGIO (ex.: e7e5 1:31): " if exigir
                          else "Lance do adversário (UCI) [mm:ss]: ").strip().lower()
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
                # o incremento do lance desfeito foi creditado mas pode não existir: só a leitura física corrige
                est["k"], est["exigir_leitura"] = 0, True
                registrar(log, f"# desfeito: voltou para {len(board.move_stack)} meios-lances")
                salvar(est, board)
                print("Desfeito. Digite o lance correto do adversário.")
            else:
                print("Nada para desfazer.")
            continue
        partes = texto.split()
        if not partes or len(partes) > 2:
            print(AJUDA)
            continue
        leitura = None
        if len(partes) == 2:
            try:
                leitura = ler_relogio(partes[1])
            except ValueError:
                print("Relógio inválido: use mm:ss (segundos de 00 a 59), ex.: e7e5 12:31")
                continue
        if leitura is None and exigir:
            print("Agora a leitura do NOSSO relógio é obrigatória (a estimativa já pode estar errada). Ex.: e7e5 1:31")
            continue
        lance = ler_lance(board, partes[0])
        if isinstance(lance, str):
            print(lance)
            continue
        if leitura is not None and not calibrar(est, leitura):
            a = tempo.AtrasoHumano(**est["atraso"])
            maximo = est["previsto_ms"] + est["k"] * a.media + tempo.TOLERANCIA_LEITURA_MS
            print(f"Leitura {fmt_relogio(leitura)} impossível (no máximo ~{fmt_relogio(maximo)}). Confira o relógio. "
                  "Se estiver certa, use 'sair' e retome informando o relógio.")
            continue
        num = board.fullmove_number
        board.push(lance)
        t0 = time.monotonic()
        extra = ""
        if leitura is not None:
            a = tempo.AtrasoHumano(**est["atraso"])
            extra = f" leitura={fmt_relogio(leitura)} atraso={a.media / 1000:.1f}s/{a.seguro / 1000:.1f}s"
            print(f"(relógio calibrado; atraso humano ~{a.media / 1000:.1f}s, reserva {a.seguro / 1000:.1f}s)")
        registrar(log, f"lance={num} cor={'pretas' if nossa else 'brancas'} uci={lance.uci()} (adversário){extra}")
        salvar(est, board)


def main():
    try:
        try:  # antes das perguntas: na retomada, o relógio informado já não inclui o tempo de abrir o motor
            abrir_motor()
        except Exception as e:
            print(f"!! motor não abriu ({e!r}); vou tentar de novo no nosso lance")
        est, board = iniciar()
        with open(est["log"], "a", encoding="utf-8", buffering=1) as log:
            partida(est, board, log)
    finally:  # sem fechar, a thread do motor segura o processo aberto após um erro
        matar_motor()


if __name__ == "__main__":
    main()
