from app.domain.cruzamento import cruzar
from app.domain.modelos import Boleto, ModoGravacao, ResultadoCruzamento
from app.infra.database import sessao
from app.infra.repositories.parcela_repository import ParcelaRepository

SEPARADOR = " | "


def montar_observacao(atual: str | None, linha: str, modo: ModoGravacao) -> str | None:
    """Retorna o novo texto da observação, ou None se nada precisa mudar."""
    if modo is ModoGravacao.SOBRESCREVER:
        return None if atual == linha else linha

    if not atual:
        return linha
    if linha in atual:
        return None  # já gravado antes, evita duplicar
    return f"{atual}{SEPARADOR}{linha}"


class GravacaoService:
    """Orquestra consulta, cruzamento e gravação. Cada operação roda em uma transação."""

    def cruzar_com_banco(self, documento: int, boletos: list[Boleto]) -> ResultadoCruzamento:
        with sessao() as sess:
            parcelas = ParcelaRepository(sess).buscar_por_documento(documento)
        return cruzar(boletos, parcelas)

    def gravar(self, resultado: ResultadoCruzamento, modo: ModoGravacao) -> int:
        """Grava todas as observações em uma única transação. Se uma falhar, nada é gravado."""
        if not resultado.pareamentos:
            return 0

        documento = resultado.pareamentos[0].parcela.documento
        cods = [par.parcela.cod for par in resultado.pareamentos]
        gravadas = 0

        with sessao() as sess:
            repo = ParcelaRepository(sess)
            atuais = repo.observacoes_bloqueadas(documento, cods)

            for par in resultado.pareamentos:
                cod = par.parcela.cod
                nova = montar_observacao(atuais.get(cod), par.boleto.linha_digitavel, modo)
                if nova is None:
                    continue
                repo.atualizar_observacao(documento, cod, nova)
                gravadas += 1

        return gravadas
