from decimal import Decimal

from sqlalchemy import Column, Date, Integer, MetaData, Numeric, Table, Text, select, update
from sqlalchemy.orm import Session

from app.domain.modelos import Parcela

metadata = MetaData()

pagar_parcelas = Table(
    "pagar_parcelas",
    metadata,
    Column("pagparc_cod", Integer, primary_key=True),
    Column("pagparc_documento", Integer, nullable=False),
    Column("pagparc_dtvencimento", Date),
    Column("pagparc_vlrdocumento", Numeric(12, 2)),
    Column("pagparc_obs", Text),
)


class ParcelaRepository:
    """Acesso às parcelas. Não decide regras de negócio, só consulta e grava."""

    def __init__(self, sessao: Session) -> None:
        self._sessao = sessao

    def buscar_por_documento(self, documento: int) -> list[Parcela]:
        stmt = (
            select(pagar_parcelas)
            .where(pagar_parcelas.c.pagparc_documento == documento)
            .order_by(pagar_parcelas.c.pagparc_cod)
        )
        return [_para_parcela(linha) for linha in self._sessao.execute(stmt).mappings()]

    def observacoes_bloqueadas(self, documento: int, cods: list[int]) -> dict[int, str | None]:
        """Lê as observações atuais travando as linhas (SELECT ... FOR UPDATE)."""
        stmt = (
            select(pagar_parcelas.c.pagparc_cod, pagar_parcelas.c.pagparc_obs)
            .where(
                pagar_parcelas.c.pagparc_documento == documento,
                pagar_parcelas.c.pagparc_cod.in_(cods),
            )
            .with_for_update()
        )
        return {linha.pagparc_cod: linha.pagparc_obs for linha in self._sessao.execute(stmt)}

    def atualizar_observacao(self, documento: int, cod: int, observacao: str) -> None:
        stmt = (
            update(pagar_parcelas)
            .where(
                pagar_parcelas.c.pagparc_cod == cod,
                pagar_parcelas.c.pagparc_documento == documento,
            )
            .values(pagparc_obs=observacao)
        )
        self._sessao.execute(stmt)


def _para_parcela(linha) -> Parcela:
    return Parcela(
        cod=int(linha["pagparc_cod"]),
        documento=int(linha["pagparc_documento"]),
        vencimento=linha["pagparc_dtvencimento"],
        valor_centavos=round(Decimal(str(linha["pagparc_vlrdocumento"])) * 100),
        observacao=linha["pagparc_obs"],
    )
