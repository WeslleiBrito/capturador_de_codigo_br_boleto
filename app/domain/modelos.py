from dataclasses import dataclass
from datetime import date
from enum import Enum


class ModoGravacao(Enum):
    SOBRESCREVER = "sobrescrever"
    ANEXAR = "anexar"


def formatar_brl(centavos: int) -> str:
    texto = f"{centavos / 100:,.2f}"
    return "R$ " + texto.replace(",", "X").replace(".", ",").replace("X", ".")


@dataclass(frozen=True)
class Boleto:
    arquivo: str
    linha_digitavel: str
    valor_centavos: int | None
    vencimentos: tuple[date, ...]

    @property
    def valor_formatado(self) -> str:
        return formatar_brl(self.valor_centavos) if self.valor_centavos else "—"

    @property
    def vencimento_formatado(self) -> str:
        if not self.vencimentos:
            return "—"
        hoje = date.today()
        mais_proximo = min(self.vencimentos, key=lambda d: abs((d - hoje).days))
        return mais_proximo.strftime("%d/%m/%Y")


@dataclass(frozen=True)
class Parcela:
    cod: int
    documento: int
    vencimento: date
    valor_centavos: int
    observacao: str | None = None


@dataclass(frozen=True)
class Pareamento:
    boleto: Boleto
    parcela: Parcela


@dataclass(frozen=True)
class ResultadoCruzamento:
    pareamentos: list[Pareamento]
    boletos_sem_parcela: list[Boleto]
    parcelas_sem_boleto: list[Parcela]
