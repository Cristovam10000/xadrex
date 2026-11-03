"""Arena de partidas automáticas: xadrex x bea, com relógio, atraso humano simulado e regras do edital.

Uso (ver --help):  python3 arena/arena.py --games 10 --seed 42
Saídas em arena/resultados/<nome>/: partidas.pgn, partidas.jsonl, resumo.json.
"""
import argparse
import json
import math
import random
import statistics
import time
from datetime import datetime
from pathlib import Path

import chess
import chess.engine
import chess.pgn

import modelos

# linhas principais curtas, em UCI; a Najdorf precisa de 10 meios-lances para chegar ao 5...a6
ABERTURAS = [
    ("Ruy Lopez", "e2e4 e7e5 g1f3 b8c6 f1b5 a7a6 b5a4 g8f6"),
    ("Italiana", "e2e4 e7e5 g1f3 b8c6 f1c4 f8c5 c2c3 g8f6"),
    ("Siciliana Najdorf", "e2e4 c7c5 g1f3 d7d6 d2d4 c5d4 f3d4 g8f6 b1c3 a7a6"),
    ("Francesa", "e2e4 e7e6 d2d4 d7d5 b1c3 g8f6"),
    ("Caro-Kann", "e2e4 c7c6 d2d4 d7d5 b1c3 d5e4 c3e4 c8f5"),
    ("Gambito da Dama Recusado", "d2d4 d7d5 c2c4 e7e6 b1c3 g8f6 c1g5 f8e7"),
    ("Eslava", "d2d4 d7d5 c2c4 c7c6 g1f3 g8f6 b1c3 d5c4"),
    ("India do Rei", "d2d4 g8f6 c2c4 g7g6 b1c3 f8g7 e2e4 d7d6"),
    ("Inglesa", "c2c4 e7e5 b1c3 b8c6 g2g3 g7g6 f1g2 f8g7"),
    ("Nimzo-India", "d2d4 g8f6 c2c4 e7e6 b1c3 f8b4"),
]
DESVIO = ("bea: notebook index.ipynb (celula 0) reimplementado (original: /opt/homebrew/bin/stockfish), "
          "binario {sf}; xadrex: COMANDO_MOTOR trocado do .exe Windows (SF19) para {sf}")


def carregar_aberturas():
    """Valida cada abertura com python-chess; lance ilegal derruba a arena antes de começar."""
    saida = []
    for nome, seq in ABERTURAS:
        board = chess.Board()
        lances = [board.push_uci(u) for u in seq.split()]  # push_uci levanta ValueError se ilegal
        saida.append((nome, lances))
    return saida


def fim_de_jogo(board):
    """Mesmo critério de xadrex.fim_de_jogo: o árbitro declara repetição tripla e 50 lances sem reclamação."""
    o = board.outcome()
    if o:
        return o.result(), o.termination.name.lower()
    if board.is_repetition(3):
        return "1/2-1/2", "tripla repeticao"
    if board.is_fifty_moves():
        return "1/2-1/2", "regra dos 50 lances"
    return None


def vitoria_de(cor):
    return "1-0" if cor == chess.WHITE else "0-1"


def fmt_clk(ms):
    s = max(0.0, ms / 1000)
    return f"{int(s // 3600)}:{int(s % 3600 // 60):02d}:{s % 60:04.1f}"


def jogar_partida(n, abertura, jogadores, args, rng):
    """jogadores: {chess.WHITE: adaptador, chess.BLACK: adaptador}. Devolve (registro, jogo PGN)."""
    nome_ab, lances_ab = abertura
    base_ms, inc_ms = args.base_min * 60_000, args.inc_s * 1000
    board = chess.Board()
    for m in lances_ab:  # abertura não consome relógio
        board.push(m)
    relogio = {chess.WHITE: base_ms, chess.BLACK: base_ms}
    lado = {c: {"modelo": j.nome, "lances": 0, "pensar_s": [], "atraso_s": 0.0, "relogio_min_ms": base_ms,
                "ilegais": 0, "falhas": 0, "eventos": []} for c, j in jogadores.items()}
    comentarios = []
    resultado = motivo = None

    for cor, j in jogadores.items():
        try:
            j.iniciar_partida(cor, base_ms, args.inc_s)
        except Exception as e:
            lado[cor]["falhas"] += 1
            resultado, motivo = vitoria_de(not cor), f"falha ao iniciar ({j.nome}): {e!r}"
            break

    while resultado is None:
        fim = fim_de_jogo(board)
        if fim:
            resultado, motivo = fim
            break
        if board.ply() >= args.max_plies:
            resultado, motivo = "1/2-1/2", f"teto de {args.max_plies} meios-lances"
            break
        cor, j, st = board.turn, jogadores[board.turn], lado[board.turn]
        t = time.monotonic()
        try:
            lance = j.lance(board.copy(), relogio[cor])
        except Exception as e:  # travou/falhou: derrota de quem jogava
            st["falhas"] += 1
            resultado, motivo = vitoria_de(not cor), f"falha ({j.nome}): {e!r}"
            break
        gasto = time.monotonic() - t
        st["eventos"] += j.eventos
        if not isinstance(lance, chess.Move) or lance not in board.legal_moves:
            st["ilegais"] += 1
            resultado, motivo = vitoria_de(not cor), f"lance ilegal ({j.nome}): {lance}"
            break
        atraso = rng.uniform(args.delay_min, args.delay_max) if args.delay_max > 0 else 0.0
        relogio[cor] -= (gasto + atraso) * 1000
        st["lances"] += 1
        st["pensar_s"].append(gasto)
        st["atraso_s"] += atraso
        st["relogio_min_ms"] = min(st["relogio_min_ms"], relogio[cor])
        if relogio[cor] <= 0:  # a bandeira caiu antes de apertar o relógio: o lance não é registrado
            resultado, motivo = vitoria_de(not cor), f"tempo esgotado ({j.nome})"
            break
        relogio[cor] += inc_ms
        board.push(lance)
        extra = (" " + " ".join(j.eventos)) if j.eventos else ""
        comentarios.append(f"[%emt {fmt_clk(gasto * 1000)}] [%clk {fmt_clk(relogio[cor])}] "
                           f"pensou {gasto:.2f}s, atraso {atraso:.1f}s{extra}")

    for j in jogadores.values():
        try:
            j.encerrar_partida()
        except Exception:
            pass

    jogo = chess.pgn.Game()
    h = jogo.headers
    h["Event"] = "Arena xadrex x bea"
    h["Site"] = "local"
    h["Date"] = datetime.now().strftime("%Y.%m.%d")
    h["Round"] = str(n)
    h["White"], h["Black"] = jogadores[chess.WHITE].nome, jogadores[chess.BLACK].nome
    h["Result"] = resultado
    h["Termination"] = motivo
    h["TimeControl"] = f"{args.base_min * 60:g}+{args.inc_s:g}"
    h["Seed"] = str(args.seed)
    h["HumanDelay"] = f"{args.delay_min:g}-{args.delay_max:g}s" if args.delay_max > 0 else "0"
    h["Opening"] = nome_ab
    h["Engine"] = args.motor_nome
    h["KnownDeviation"] = args.desvio
    node = jogo
    for i, m in enumerate(board.move_stack):
        node = node.add_variation(m)
        if i < len(lances_ab):
            node.comment = "abertura (fora do relogio)"
        else:
            node.comment = comentarios[i - len(lances_ab)]

    def resumo_lado(c):
        st = lado[c]
        return {"modelo": st["modelo"], "lances": st["lances"],
                "pensar_medio_s": round(statistics.fmean(st["pensar_s"]), 3) if st["pensar_s"] else None,
                "pensar_max_s": round(max(st["pensar_s"]), 3) if st["pensar_s"] else None,
                "atraso_total_s": round(st["atraso_s"], 1),
                "relogio_min_s": round(st["relogio_min_ms"] / 1000, 2), "relogio_final_s": round(relogio[c] / 1000, 2),
                "ilegais": st["ilegais"], "falhas": st["falhas"], "eventos": st["eventos"]}

    cor_x = next(c for c, j in jogadores.items() if j.nome == "xadrex")
    pontos_x = {"1/2-1/2": 0.5, vitoria_de(cor_x): 1.0}.get(resultado, 0.0)
    registro = {"partida": n, "abertura": nome_ab, "brancas": h["White"], "pretas": h["Black"],
                "resultado": resultado, "motivo": motivo, "meios_lances": board.ply(),
                "pontos_xadrex": pontos_x, "cor_xadrex": "brancas" if cor_x == chess.WHITE else "pretas",
                "brancas_stats": resumo_lado(chess.WHITE), "pretas_stats": resumo_lado(chess.BLACK)}
    return registro, jogo


def elo(p):
    """Diferença de Elo pela fórmula logística; None em 0% ou 100% (infinito)."""
    return None if p <= 0 or p >= 1 else -400 * math.log10(1 / p - 1) + 0.0  # + 0.0 evita "-0"


def estatisticas(pontos):
    """Placar e Elo (IC 95% pelo desvio-padrão da pontuação por partida) do ponto de vista do xadrex."""
    n = len(pontos)
    if n == 0:
        return {"partidas": 0}
    v, e = pontos.count(1.0), pontos.count(0.5)
    p = statistics.fmean(pontos)
    ep = statistics.pstdev(pontos) / math.sqrt(n)
    lo, hi = max(0.0, p - 1.96 * ep), min(1.0, p + 1.96 * ep)
    fmt = lambda x: None if x is None else round(x, 1)
    out = {"partidas": n, "vitorias": v, "empates": e, "derrotas": n - v - e, "pontuacao_pct": round(100 * p, 1),
           "elo": fmt(elo(p)), "elo_ic95": [fmt(elo(lo)), fmt(elo(hi))]}
    # 0%/100% (ou IC tocando os extremos): Elo infinito, informado em texto em vez de quebrar a conta
    txt = lambda q: "-inf" if q <= 0 else "+inf" if q >= 1 else f"{elo(q):+.0f}"
    out["elo_txt"] = f"{txt(p)} [{txt(lo)}, {txt(hi)}]"
    return out


def resumo(registros):
    r = {"geral": estatisticas([x["pontos_xadrex"] for x in registros]),
         "xadrex_de_brancas": estatisticas([x["pontos_xadrex"] for x in registros if x["cor_xadrex"] == "brancas"]),
         "xadrex_de_pretas": estatisticas([x["pontos_xadrex"] for x in registros if x["cor_xadrex"] == "pretas"]),
         "motivos": {}}
    for x in registros:
        r["motivos"][x["motivo"]] = r["motivos"].get(x["motivo"], 0) + 1
    return r


def imprimir_resumo(r):
    print("\n=== RESUMO (ponto de vista do xadrex) ===")
    for chave in ("geral", "xadrex_de_brancas", "xadrex_de_pretas"):
        s = r[chave]
        if s["partidas"]:
            print(f"{chave:18} +{s['vitorias']} ={s['empates']} -{s['derrotas']}  ({s['partidas']} partidas) "
                  f"{s['pontuacao_pct']:5.1f}%  Elo {s['elo_txt']}")
    print("motivos:", ", ".join(f"{k}: {v}" for k, v in r["motivos"].items()))


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--games", type=int, default=10, help="total de partidas (pares por abertura, cores trocadas)")
    ap.add_argument("--base-min", type=float, default=10.0)
    ap.add_argument("--inc-s", type=float, default=0.0)
    ap.add_argument("--delay-min", type=float, default=3.0, help="atraso humano mínimo por lance (s)")
    ap.add_argument("--delay-max", type=float, default=8.0, help="atraso humano máximo por lance (s); 0 desliga")
    ap.add_argument("--seed", type=int, default=None, help="padrão: aleatória (registrada no PGN)")
    ap.add_argument("--max-plies", type=int, default=300, help="teto de segurança: empate ao atingir")
    ap.add_argument("--nome", default=None, help="pasta do run em resultados/ (padrão: data e hora)")
    ap.add_argument("--stockfish", default=modelos.STOCKFISH,
                    help="executável do Stockfish (padrão: $ARENA_STOCKFISH, stockfish do PATH ou o .exe em "
                         f"engines/; agora: {modelos.STOCKFISH})")
    args = ap.parse_args()
    if not args.stockfish:
        ap.error("Stockfish não encontrado: use --stockfish CAMINHO ou a variável ARENA_STOCKFISH")
    modelos.STOCKFISH = args.stockfish
    args.desvio = DESVIO.format(sf=args.stockfish)
    if (args.games < 1 or args.base_min <= 0 or args.inc_s < 0 or args.max_plies < 1
            or (args.delay_max > 0 and not 0 <= args.delay_min <= args.delay_max)):
        ap.error("parâmetros inválidos")
    if args.seed is None:
        args.seed = random.SystemRandom().randrange(2**31)
    if args.games % 2:
        print(f"aviso: --games {args.games} é ímpar; a última abertura será jogada só com uma das cores")

    aberturas = carregar_aberturas()
    with chess.engine.SimpleEngine.popen_uci(modelos.STOCKFISH) as e:
        args.motor_nome = e.id.get("name", "?")
    nome = args.nome or datetime.now().strftime("%Y%m%d_%H%M%S")
    pasta = Path(__file__).resolve().parent / "resultados" / nome
    pasta.mkdir(parents=True, exist_ok=False)
    rng = random.Random(args.seed)
    bea, xadrex = modelos.Bea(), modelos.Xadrex()

    atraso = f"{args.delay_min:g}-{args.delay_max:g}s" if args.delay_max > 0 else "desligado"
    print(f"run {nome} | {args.games} partidas | {args.base_min:g} min + {args.inc_s:g} s | atraso {atraso} | "
          f"seed {args.seed} | {args.motor_nome}", flush=True)
    print(f"desvio conhecido: {args.desvio}", flush=True)
    registros = []
    for i in range(args.games):
        abertura = aberturas[(i // 2) % len(aberturas)]
        x_brancas = i % 2 == 0
        jog = {chess.WHITE: xadrex if x_brancas else bea, chess.BLACK: bea if x_brancas else xadrex}
        print(f"[{i + 1}/{args.games}] {jog[chess.WHITE].nome} x {jog[chess.BLACK].nome} | {abertura[0]} ...",
              flush=True)
        t = time.monotonic()
        reg, jogo = jogar_partida(i + 1, abertura, jog, args, rng)
        registros.append(reg)
        with open(pasta / "partidas.pgn", "a", encoding="utf-8") as f:
            print(jogo, file=f, end="\n\n")
        with open(pasta / "partidas.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(reg, ensure_ascii=False) + "\n")
        r = resumo(registros)
        r["config"] = {k: v for k, v in vars(args).items()}
        r["desvio_conhecido"] = args.desvio
        (pasta / "resumo.json").write_text(json.dumps(r, indent=1, ensure_ascii=False), encoding="utf-8")
        g = r["geral"]
        print(f"    -> {reg['resultado']} ({reg['motivo']}), {reg['meios_lances']} meios-lances, "
              f"{time.monotonic() - t:.0f}s | relógio final b={reg['brancas_stats']['relogio_final_s']}s "
              f"p={reg['pretas_stats']['relogio_final_s']}s | placar xadrex +{g['vitorias']} ={g['empates']} "
              f"-{g['derrotas']}", flush=True)
    imprimir_resumo(r)
    print(f"\narquivos em {pasta}")


if __name__ == "__main__":
    main()
