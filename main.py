from app.domain.modelos import ModoGravacao
from app.services.gravacao_service import GravacaoService
from app.ui.tela_principal import TelaPrincipal

# Troque para ModoGravacao.SOBRESCREVER se preferir substituir as observações existentes.
MODO_PADRAO = ModoGravacao.ANEXAR


def main() -> None:
    TelaPrincipal(GravacaoService(), MODO_PADRAO).mainloop()


if __name__ == "__main__":
    main()
