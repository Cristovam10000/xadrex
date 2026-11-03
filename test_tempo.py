"""Testes do gestor de tempo: .venv\\Scripts\\python.exe test_tempo.py"""
import random

import chess

from tempo import (EMERGENCIA_MS, MIN_MS, OUVIR_MS, SEGURO_MIN_MS, AtrasoHumano, ControleBusca, fase, fechar_lance,
                   leitura_plausivel, orcamento, precisa_leitura, relogio_ao_pensar)


def test_atraso_humano():
    a = AtrasoHumano()
    a.observar(4000)
    assert (a.media, a.desvio) == (4000, 2000)  # primeira medida substitui o palpite
    for _ in range(50):
        a.observar(4000)
    assert abs(a.media - 4000) < 1 and a.desvio < 50 and a.seguro < 4200  # atraso constante: reserva encolhe
    a.observar(1e9)
    assert a.media < 12_000  # leitura absurda é limitada
    zero = AtrasoHumano()
    zero.observar(0)
    assert zero.seguro == SEGURO_MIN_MS  # primeira amostra zerada não elimina a reserva humana


def test_leituras():
    assert not precisa_leitura(900_000, 0) and precisa_leitura(900_000, 8) and precisa_leitura(119_000, 0)
    a = AtrasoHumano()
    assert leitura_plausivel(15_000, 1, a, 20_000)       # atraso real menor que o estimado: relógio acima
    assert not leitura_plausivel(15_000, 1, a, 120_000)  # "2:00" no lugar de "0:20"


def test_relogio_automatico():
    # adversário bate o relógio com o nosso em 10:00; 1ª tecla 1 s depois (OUVIR_MS), ENTER do lance em 3 s,
    # nosso lance mostrado em 8 s (busca de 5 s), ENTER ao bater o relógio em 12 s
    inicio, t0, fim = 100.0, 102.0, 111.0
    relogio_t0 = relogio_ao_pensar(600_000, inicio, t0)
    assert relogio_t0 == 600_000 - 2000 - OUVIR_MS
    relogio, gasto, humano = fechar_lance(relogio_t0, inicio, t0, fim, 5000, 0)
    assert gasto == 12_000 and humano == 7000 and relogio == 600_000 - gasto  # sem incremento: sai tudo
    assert fechar_lance(relogio_t0, inicio, t0, fim, 5000, 10_000)[0] == 600_000 - gasto + 10_000
    assert fechar_lance(relogio_t0, inicio, t0, fim, 20_000, 0)[2] == 0  # parte humana nunca negativa
    assert fechar_lance(600_000, None, t0, fim, 5000, 0) == (591_000, None, None)  # sem 1ª tecla: fecha desde t0
    a = AtrasoHumano()
    assert not leitura_plausivel(500_000, 0, a, 530_000)
    assert leitura_plausivel(500_000, 0, a, 530_000, folga_ms=30_000)  # ENTER esquecido: relógio contou a mais


def test_fase():
    assert fase(chess.Board()) == 1.0
    assert fase(chess.Board("4k3/pppp4/8/8/8/8/PPPP4/4K3 w - - 0 1")) == 0.0


def test_orcamento():
    a = AtrasoHumano()
    alvo, maximo = orcamento(900_000, 10_000, a, 1.0)  # 15+10 no início
    assert 15_000 < alvo < 30_000 and alvo <= maximo <= 4 * alvo
    alvo0, _ = orcamento(1_500_000, 0, a, 1.0)  # 25+0: horizonte longo e custo humano de cada lance futuro
    assert 15_000 < alvo0 < 25_000
    assert orcamento(10_000, 10_000, a, 0.5) == (MIN_MS, MIN_MS)  # abaixo da reserva humana: emergência
    assert orcamento(5_100, 10_000, a, 0.5) == (EMERGENCIA_MS, EMERGENCIA_MS)  # o mínimo cede ao relógio
    for relogio in (20_000, 60_000, 300_000):  # nunca planeja gastar mais que 30% do que sobra além da reserva
        _, m = orcamento(relogio, 10_000, a, 0.3)
        assert m <= max(MIN_MS, 0.3 * (relogio - a.seguro - 1000)) + 1e-6
    assert orcamento(300_000, 0, a, 0.0)[0] > orcamento(300_000, 0, a, 1.0)[0]  # final: horizonte menor
    a1, _ = orcamento(900_000, 10_000, a, 1.0, numero_lance=1)
    a10, _ = orcamento(900_000, 10_000, a, 1.0, numero_lance=10)
    assert a1 < 0.5 * a10 and a10 == alvo  # rampa de abertura


def test_controle_busca():
    c = ControleBusca(alvo=10_000, maximo=40_000)
    assert c.parar(5_000) is None  # sem iteração completa ainda
    for d in range(1, 6):
        c.iteracao(d, "e2e4", 30)
    assert c.parar(9_000) is None and c.parar(10_000).startswith("alvo")
    for d in range(6, 12):
        c.iteracao(d, "e2e4", 30)
    assert c.parar(6_000).startswith("alvo")  # 8+ iterações estáveis: para com 60% do alvo

    instavel = ControleBusca(alvo=10_000, maximo=40_000)
    for d, lance in enumerate(["e2e4", "d2d4", "e2e4", "c2c4", "g1f3"], start=10):
        instavel.iteracao(d, lance, 30)
    assert instavel.parar(20_000) is None and instavel.parar(30_000)  # trocas recentes estendem até 3x

    caindo = ControleBusca(alvo=10_000, maximo=40_000, aval_anterior=50)
    caindo.iteracao(10, "e2e4", -150)
    assert caindo.parar(15_000) is None and caindo.parar(20_000)  # avaliação caiu 2 peões: até 2x

    assert ControleBusca(alvo=10_000, maximo=12_000, lance_unico=True).parar(0) is None
    unico = ControleBusca(alvo=10_000, maximo=12_000, lance_unico=True)
    unico.iteracao(1, "e1f1", 0)
    assert unico.parar(1) == "lance-unico"

    mate = ControleBusca(alvo=10_000, maximo=40_000)
    for d in (5, 6, 7):
        mate.iteracao(d, "d1h5", 99_990)
    assert mate.parar(100) == "mate-encontrado"
    assert ControleBusca(alvo=10_000, maximo=12_000).parar(12_000) == "maximo"


def simular(base_s, inc_s, lances, atraso_min, atraso_max, semente):
    """Partida simulada com a mesma contagem de xadrex.py: o gestor só conhece o relógio previsto, e o operador
    digita a leitura apenas quando precisa_leitura() exige. Devolve a menor sobra do relógio real (ms)."""
    rnd = random.Random(semente)
    a = AtrasoHumano()
    real = previsto = base_s * 1000.0  # nosso relógio na entrada do lance adversário
    k = 0
    menor = real
    for n in range(lances):
        if precisa_leitura(previsto, k):  # mesma regra do programa (calibrar)
            leitura = real - rnd.uniform(0, 1000)  # o relógio mostra segundos inteiros
            if k > 0:
                a.observar(a.media + (previsto - leitura) / k)
            previsto, k = leitura, 0
        f = max(0.0, 1 - n / 40)  # fase cai ao longo da partida
        alvo, maximo = orcamento(previsto, inc_s * 1000, a, f, n + 1)
        pensado = min(maximo, alvo * rnd.uniform(0.5, 3.0))  # o controle de busca fica entre 0,5x e 3x do alvo
        humano = rnd.uniform(atraso_min, atraso_max)
        sobra = real - pensado - 0.6 * humano  # 60% do atraso é anunciar/mover antes de apertar o relógio
        menor = min(menor, sobra)
        if sobra <= 0:
            return sobra
        previsto = previsto - pensado + inc_s * 1000 - a.media
        k += 1
        real = real - pensado - humano + inc_s * 1000
    return menor


def simular_medido(base_s, inc_s, lances, atraso_min, atraso_max, semente, ouvir_max=2 * OUVIR_MS):
    """Mesma partida com o relógio automático de xadrex.py: o programa mede digitar (1ª tecla -> ENTER) e
    t0 -> ENTER ao bater o relógio; só o tempo de ouvir é estimado (OUVIR_MS; o real varia de 0 a ouvir_max).
    Nenhuma leitura do relógio. Devolve a menor sobra do relógio real (ms)."""
    rnd = random.Random(semente)
    a = AtrasoHumano()
    real = medido = base_s * 1000.0  # nosso relógio quando ele volta a correr (adversário bateu o dele)
    menor = real
    for n in range(lances):
        humano = rnd.uniform(atraso_min, atraso_max)
        antes, depois = 0.4 * humano, 0.6 * humano  # ouvir + digitar | anunciar, mover, bater o relógio
        ouvir = min(antes, rnd.uniform(0, ouvir_max))
        previsto = relogio_ao_pensar(medido, 0, (antes - ouvir) / 1000)  # 1ª tecla em 0 s, ENTER em t0
        f = max(0.0, 1 - n / 40)
        alvo, maximo = orcamento(previsto, inc_s * 1000, a, f, n + 1)
        pensado = min(maximo, alvo * rnd.uniform(0.5, 3.0))
        sobra = real - antes - pensado - depois
        menor = min(menor, sobra)
        if sobra <= 0:
            return sobra
        t0 = (antes - ouvir) / 1000
        medido, _, parte_humana = fechar_lance(previsto, 0, t0, t0 + (pensado + depois) / 1000, pensado, inc_s * 1000)
        a.observar(parte_humana)
        real = sobra + inc_s * 1000
    return menor


def test_simulacao_sem_perder_por_tempo():
    for semente in range(20):
        assert simular(15 * 60, 10, 120, 3000, 8000, semente) > 0      # 15+10, partida longa
        assert simular(15 * 60, 10, 120, 6000, 10000, semente) > 0     # 15+10, equipe lenta
        assert simular(25 * 60, 0, 80, 3000, 8000, semente) > 0        # 25+0
        assert simular(10 * 60, 0, 60, 3000, 8000, semente) > 0        # 10+0 (competição); 80 lances perde (diário)
        assert simular_medido(10 * 60, 0, 60, 3000, 8000, semente) > 0  # 10+0 com relógio automático
        assert simular(5 * 60, 0, 40, 2000, 5000, semente) > 0         # Armageddon brancas
        assert simular(4 * 60, 0, 35, 2000, 5000, semente) > 0         # Armageddon pretas


if __name__ == "__main__":
    for nome, f in list(globals().items()):
        if nome.startswith("test_"):
            f()
            print("ok", nome)
