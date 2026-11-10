import os
from contextlib import contextmanager
from typing import Iterator

from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, Engine
from sqlalchemy.orm import Session

# Carrega o .env da raiz do projeto (uma vez, na importação)
load_dotenv()

_engine: Engine | None = None


class ConfiguracaoBancoError(RuntimeError):
    """Variável obrigatória do .env ausente ou inválida."""


def _variavel_obrigatoria(nome: str) -> str:
    valor = os.getenv(nome)
    if not valor:
        raise ConfiguracaoBancoError(f"Variável {nome} não definida no .env")
    return valor


def _criar_engine() -> Engine:
    # URL.create escapa caracteres especiais da senha automaticamente
    url = URL.create(
        drivername="mysql+pymysql",
        username=_variavel_obrigatoria("DB_USER"),
        password=_variavel_obrigatoria("DB_PASSWORD"),
        host=_variavel_obrigatoria("DB_HOST"),
        port=int(os.getenv("DB_PORT", "3307")),
        database=_variavel_obrigatoria("DB_NAME"),
        query={"charset": "utf8mb4"},
    )
    return create_engine(
        url,
        pool_pre_ping=True,   # testa a conexão antes de usar (evita "MySQL server has gone away")
        pool_recycle=1800,    # renova conexões ociosas a cada 30 min
    )


def obter_engine() -> Engine:
    """Cria o engine na primeira chamada e reutiliza nas seguintes."""
    global _engine
    if _engine is None:
        _engine = _criar_engine()
    return _engine


@contextmanager
def sessao() -> Iterator[Session]:
    """
    Sessão com transação: commit ao sair sem erro, rollback em caso de exceção.
    Uso:
        with sessao() as s:
            s.execute(text("UPDATE ..."), {...})
    """
    sess = Session(obter_engine())
    try:
        yield sess
        sess.commit()
    except Exception:
        sess.rollback()
        raise
    finally:
        sess.close()


def testar_conexao() -> None:
    """Lança exceção se o banco não responder. Útil para o botão de teste na tela."""
    with obter_engine().connect() as conn:
        conn.execute(text("SELECT 1"))
