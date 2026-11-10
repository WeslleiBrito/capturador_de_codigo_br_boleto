from app.domain.modelos import Boleto, Parcela, Pareamento, ResultadoCruzamento


def cruzar(boletos: list[Boleto], parcelas: list[Parcela]) -> ResultadoCruzamento:
    """Associa cada boleto a uma parcela pelo valor e pelo vencimento.

    Cada parcela é usada no máximo uma vez. Em caso de empate, vence a de menor código.
    """
    disponiveis = sorted(parcelas, key=lambda p: p.cod)
    pareamentos: list[Pareamento] = []
    sem_parcela: list[Boleto] = []

    for boleto in boletos:

        escolhida = _encontrar_parcela(boleto, disponiveis)
        if escolhida is None:
            sem_parcela.append(boleto)
            continue
        disponiveis.remove(escolhida)
        pareamentos.append(Pareamento(boleto=boleto, parcela=escolhida))

    return ResultadoCruzamento(
        pareamentos=pareamentos,
        boletos_sem_parcela=sem_parcela,
        parcelas_sem_boleto=disponiveis,
    )


def _encontrar_parcela(boleto: Boleto, parcelas: list[Parcela]) -> Parcela | None:
    print(f"Boleto: {boleto} \n Disponíveis: {parcelas}")
    if boleto.valor_centavos is None:
        return None
    return next(
        (
            p
            for p in parcelas
            if p.valor_centavos == boleto.valor_centavos and p.vencimento in boleto.vencimentos
        ),
        None,
    )
