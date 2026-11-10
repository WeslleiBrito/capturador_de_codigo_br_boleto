import re
from datetime import date, timedelta
from pathlib import Path

import PyPDF2

from app.domain.modelos import Boleto

PADRAO_LINHA_DIGITAVEL = re.compile(
    r"\d{5}\.?\s*\d{5}\s*\d{5}\.?\s*\d{6}\s*\d{5}\.?\s*\d{6}\s*\d{1}\s*\d{14}"
)
DATA_BASE_FATOR = date(1997, 10, 7)
CICLO_NOVO_FATOR = 9000  # novo ciclo do fator de vencimento a partir de 22/02/2025


def ler_boletos(caminhos: list[Path]) -> tuple[list[Boleto], list[str]]:
    """Retorna os boletos lidos e os nomes dos PDFs sem linha digitável."""
    boletos: list[Boleto] = []
    sem_linha: list[str] = []

    for caminho in caminhos:
        try:
            texto = _extrair_texto(caminho)
        except Exception:  # PDF corrompido, protegido ou ilegível
            sem_linha.append(caminho.name)
            continue

        achados = PADRAO_LINHA_DIGITAVEL.findall(texto)
        if not achados:
            sem_linha.append(caminho.name)
            continue

        boletos.append(_montar_boleto(caminho.name, achados[0]))

    return boletos, sem_linha


def _extrair_texto(caminho: Path) -> str:
    with caminho.open("rb") as arquivo:
        leitor = PyPDF2.PdfReader(arquivo)
        return " ".join(pagina.extract_text() or "" for pagina in leitor.pages)


def _montar_boleto(arquivo: str, bruto: str) -> Boleto:
    digitos = re.sub(r"\D", "", bruto)
    valor = int(digitos[37:47])
    fator = int(digitos[33:37])

    # Os dois candidatos cobrem os ciclos antigo e novo do fator.
    # O cruzamento aceita qualquer um deles.
    vencimentos: tuple[date, ...] = ()
    if fator:
        vencimentos = (
            DATA_BASE_FATOR + timedelta(days=fator),
            DATA_BASE_FATOR + timedelta(days=fator + CICLO_NOVO_FATOR),
        )

    return Boleto(
        arquivo=arquivo,
        linha_digitavel=digitos,
        valor_centavos=valor or None,
        vencimentos=vencimentos,
    )
