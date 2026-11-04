"""Roda os testes e as validações do xadrex com um comando só (Windows e macOS, só biblioteca padrão).

  unit     testes unitários (test_tempo, test_empate, test_xadrex), cerca de 10 s
  smoke    arena rápida: xadrex x bea e xadrex+ae x fraco, 2 partidas de 1 min cada, apaga a pasta no fim
  match    xadrex x bea em 10+0, atraso 3-8 s, seed 2026 (cerca de 4 min por partida)
  lote     arena/lote.py (anti-empate: 4 combinações), 1h30 a 2h30 com 6 partidas por combinação
  tabela   tabela comparativa de resultados já salvos (ex.: lote interrompido)
  tudo     unit e depois smoke

Windows: .venv\\Scripts\\python.exe rodar_testes.py unit      macOS: python3 rodar_testes.py unit
Guia completo em docs/testes.md.
"""
import argparse
import json
import os
import shutil
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

sys.dont_write_bytecode = True  # o import de lote abaixo não cria __pycache__ em arena/
RAIZ = Path(__file__).resolve().parent
ARENA = RAIZ / "arena"
RESULTADOS = ARENA / "resultados"
sys.path.insert(0, str(ARENA))
import lote  # noqa: E402  (só biblioteca padrão; reaproveita COMBINACOES, pasta_de e tabela)

TESTES = ["test_tempo.py", "test_empate.py", "test_xadrex.py"]
# PYTHONIOENCODING: no Windows a saída em pipe usaria cp1252 e quebraria os acentos; UNBUFFERED: o tee mostra na hora
ENV = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8", "PYTHONUNBUFFERED": "1"}


def agora():
    return datetime.now().strftime("%Y%m%d_%H%M%S")


def com_stockfish(cmd, args):
    return cmd + (["--stockfish", args.stockfish] if args.stockfish else [])


def unit(args):
    falhas = 0
    for nome in TESTES:
        t = time.monotonic()
        p = subprocess.run([sys.executable, nome], cwd=RAIZ, env=ENV, capture_output=True, text=True,
                           encoding="utf-8", errors="replace")
        ok = p.returncode == 0
        print(f"{'ok     ' if ok else 'FALHOU '} {nome} ({time.monotonic() - t:.1f} s)", flush=True)
        if not ok:
            falhas += 1
            print(p.stdout + p.stderr)
    print(f"\n{len(TESTES) - falhas}/{len(TESTES)} arquivos passaram")
    return 1 if falhas else 0


def smoke(args):
    nome = f"smoke_{agora()}"
    pasta = RESULTADOS / nome
    codigo = 0
    try:
        for a, b in [("xadrex", "bea"), ("xadrex+ae", "fraco")]:
            print(f"\n##### smoke {a} x {b} #####", flush=True)
            cmd = [sys.executable, str(ARENA / "arena.py"), "--a", a, "--b", b, "--games", "2", "--base-min", "1",
                   "--delay-max", "0", "--nome", f"{nome}/{lote.pasta_de(a, b)}"]
            r = subprocess.run(com_stockfish(cmd, args), cwd=RAIZ, env=ENV).returncode
            if r:
                print(f"!! {a} x {b} terminou com código {r}", flush=True)
                codigo = 1
        if pasta.exists():
            print("\n" + texto_tabela(pasta))
    finally:
        if args.manter:
            print(f"\nresultados mantidos em {pasta}")
        elif pasta.exists():
            shutil.rmtree(pasta)
            print(f"\npasta {pasta} apagada (use --manter para guardar)")
    return codigo


def rodar_com_log(cmd, pasta):
    """Roda cmd mostrando a saída na tela e gravando em <pasta>/console.log. A arena e o lote recusam pasta que já
    existe, então o log fica ao lado (<pasta>.console.log) durante o run e entra na pasta no fim."""
    if pasta.exists():
        sys.exit(f"{pasta} já existe; escolha outro --nome")
    RESULTADOS.mkdir(parents=True, exist_ok=True)
    provisorio = pasta.with_name(pasta.name + ".console.log")
    with open(provisorio, "w", encoding="utf-8") as log:
        p = subprocess.Popen(cmd, cwd=RAIZ, env=ENV, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True,
                             encoding="utf-8", errors="replace")
        try:
            for linha in p.stdout:
                sys.stdout.write(linha)
                sys.stdout.flush()
                log.write(linha)
                log.flush()
            codigo = p.wait()
        except KeyboardInterrupt:  # o Ctrl+C também chega ao subprocesso; o que já foi jogado continua salvo
            codigo = p.wait()
            print("\ninterrompido")
    if pasta.is_dir():
        destino = pasta / "console.log"
        os.replace(provisorio, destino)
    else:
        destino = provisorio
    print(f"saída do console em {destino}")
    return codigo


def match(args):
    nome = args.nome or f"match_{agora()}"
    cmd = [sys.executable, str(ARENA / "arena.py"), "--a", "xadrex", "--b", "bea", "--games", str(args.games),
           "--base-min", "10", "--inc-s", "0", "--delay-min", "3", "--delay-max", "8", "--seed", "2026",
           "--nome", nome]
    return rodar_com_log(com_stockfish(cmd, args), RESULTADOS / nome)


def rodar_lote(args, extra):
    nome = args.nome or f"lote_{agora()}"
    cmd = [sys.executable, str(ARENA / "lote.py"), "--games", str(args.games), "--seed", str(args.seed),
           "--nome", nome] + extra
    return rodar_com_log(com_stockfish(cmd, args), RESULTADOS / nome)


def texto_tabela(pasta):
    """Tabela de lote.py a partir das subpastas com resumo.json (vale para lote completo, parcial ou smoke)."""
    # ponytail: lote.py só monta a tabela no fim do próprio run; depois do lote_ae, mover esta leitura do disco
    # para lote.py (ex.: lote.py --so-tabela PASTA) e chamar de lá, para não ter dois lugares lendo resumo.json
    resultados, avisos = {}, []
    for resumo in sorted(pasta.glob("*/resumo.json")):
        try:
            r = json.loads(resumo.read_text(encoding="utf-8"))
        except json.JSONDecodeError:  # a arena regrava o arquivo a cada partida; pode ter pego no meio da escrita
            avisos.append(f"{resumo}: ilegível agora (sendo gravado?); rode de novo")
            continue
        if "a" not in r or "b" not in r:
            avisos.append(f"{resumo}: formato antigo da arena (sem 'a'/'b'), fora da tabela")
            continue
        resultados[(r["a"], r["b"])] = r
    if not resultados:
        return "\n".join(avisos + [f"nenhum resumo.json utilizável em subpastas de {pasta}"])
    ordem = {c: i for i, c in enumerate(lote.COMBINACOES)}
    resultados = dict(sorted(resultados.items(), key=lambda kv: ordem.get(kv[0], len(ordem))))
    faltam = [f"{a} x {b}" for a, b in lote.COMBINACOES if (a, b) not in resultados]
    cfg = next(iter(resultados.values())).get("config", {})
    cabecalho = (f"{pasta.name} | seed {cfg.get('seed', '?')} | {cfg.get('base_min', '?')}+{cfg.get('inc_s', '?')}"
                 f"\nplacar do ponto de vista da variante (pontos 3-1-0: variante x adversário)\n")
    rodape = []
    if faltam and pasta.name.startswith("lote"):
        rodape.append("\ncombinações do lote ainda sem resultado: " + ", ".join(faltam))
    return "\n".join([cabecalho, lote.tabela(resultados)] + rodape + avisos)


def tabela(args):
    pasta = Path(args.pasta).resolve()
    if not pasta.is_dir():
        sys.exit(f"pasta não encontrada: {pasta}")
    print(texto_tabela(pasta))
    return 0


def tudo(args):
    if unit(args):
        print("\nunit falhou: smoke não foi rodado")
        return 1
    return smoke(args)


def main():
    if hasattr(sys.stdout, "reconfigure"):  # console do Windows sem UTF-8: troca o caractere em vez de quebrar
        sys.stdout.reconfigure(errors="replace")
    sf = argparse.ArgumentParser(add_help=False)
    sf.add_argument("--stockfish", default=argparse.SUPPRESS, metavar="CAMINHO",
                    help="executável do Stockfish repassado à arena (padrão: ARENA_STOCKFISH, PATH ou engines/)")
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter,
                                 parents=[sf])
    sub = ap.add_subparsers(dest="cmd", required=True, metavar="SUBCOMANDO")
    sub.add_parser("unit", help="testes unitários (~10 s)")
    p = sub.add_parser("smoke", parents=[sf], help="arena rápida, 2 combinações x 2 partidas de 1 min")
    p.add_argument("--manter", action="store_true", help="não apaga a pasta de resultados no fim")
    p = sub.add_parser("match", parents=[sf], help="xadrex x bea em 10+0, atraso 3-8 s, seed 2026")
    p.add_argument("--games", type=int, default=10, help="partidas (padrão 10, ~40 min)")
    p.add_argument("--nome", help="pasta em arena/resultados/ (padrão: match_<data e hora>)")
    p = sub.add_parser("lote", parents=[sf], help="arena/lote.py: anti-empate nas 4 combinações",
                       description="Repassa ao arena/lote.py; opções extras (--base-min, --inc-s, --delay-min, "
                                   "--delay-max, --fraco-skill, --fraco-tempo) vão direto para ele.")
    p.add_argument("--games", type=int, default=6, help="partidas por combinação (padrão 6)")
    p.add_argument("--seed", type=int, default=2026, help="padrão 2026")
    p.add_argument("--nome", help="pasta em arena/resultados/ (padrão: lote_<data e hora>)")
    p = sub.add_parser("tabela", help="tabela comparativa de resultados já salvos")
    p.add_argument("pasta", help="pasta com subpastas que têm resumo.json, ex.: arena/resultados/lote_ae")
    p = sub.add_parser("tudo", parents=[sf], help="unit e depois smoke")
    p.add_argument("--manter", action="store_true", help="não apaga a pasta do smoke no fim")
    args, extra = ap.parse_known_args()
    if extra and args.cmd != "lote":
        ap.error(f"opções desconhecidas: {' '.join(extra)}")
    args.stockfish = getattr(args, "stockfish", None)
    acoes = {"unit": unit, "smoke": smoke, "match": match, "tabela": tabela, "tudo": tudo,
             "lote": lambda a: rodar_lote(a, extra)}
    return acoes[args.cmd](args)


if __name__ == "__main__":
    sys.exit(main())
