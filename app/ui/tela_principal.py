import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox, ttk

from sqlalchemy.exc import SQLAlchemyError

from app.domain.modelos import ModoGravacao, ResultadoCruzamento
from app.pdf.leitor_boleto import ler_boletos
from app.services.gravacao_service import GravacaoService

COLUNAS = ("arquivo", "linha", "valor", "vencimento", "parcela", "situacao")
TITULOS = {
    "arquivo": "Arquivo de Origem",
    "linha": "Linha Digitável",
    "valor": "Valor",
    "vencimento": "Vencimento",
    "parcela": "Parcela",
    "situacao": "Situação",
}
LARGURAS = {"arquivo": 220, "linha": 300, "valor": 100, "vencimento": 100, "parcela": 80, "situacao": 110}


class TelaPrincipal(tk.Tk):
    def __init__(self, service: GravacaoService, modo: ModoGravacao) -> None:
        super().__init__()
        self.title("Extrator e Organizador de Boletos")
        self.geometry("1150x520")
        self._service = service
        self._modo = modo
        self._documento = tk.StringVar()
        self._status = tk.StringVar()
        self._resultado: ResultadoCruzamento | None = None
        self._documento_atual: int | None = None
        self._montar_widgets()

    def _montar_widgets(self) -> None:
        topo = ttk.Frame(self, padding=10)
        topo.pack(fill="x")
        ttk.Label(topo, text="Nº do documento:").pack(side="left")
        ttk.Entry(topo, textvariable=self._documento, width=14).pack(side="left", padx=6)
        ttk.Button(topo, text="1. Selecionar PDFs e cruzar", command=self._cruzar).pack(side="left", padx=6)

        self._tabela = ttk.Treeview(self, columns=COLUNAS, show="headings", height=15)
        for col in COLUNAS:
            self._tabela.heading(col, text=TITULOS[col])
            self._tabela.column(col, width=LARGURAS[col], anchor="w" if col == "arquivo" else "center")
        self._tabela.pack(fill="both", expand=True, padx=10, pady=5)
        self._tabela.bind("<Double-1>", self._copiar_linha)

        base = ttk.Frame(self, padding=10)
        base.pack(fill="x")
        self._btn_gravar = ttk.Button(
            base, text="2. Gravar observações no banco", command=self._gravar, state="disabled"
        )
        self._btn_gravar.pack(side="left")
        ttk.Label(base, textvariable=self._status).pack(side="left", padx=15)

    def _cruzar(self) -> None:
        try:
            documento = int(self._documento.get().strip())
        except ValueError:
            messagebox.showwarning("Aviso", "Informe um número de documento válido.")
            return

        caminhos = filedialog.askopenfilenames(
            title="Selecione os PDFs dos boletos",
            filetypes=[("Arquivos PDF", "*.pdf")],
        )
        if not caminhos:
            return

        boletos, sem_linha = ler_boletos([Path(c) for c in caminhos])

        try:
            resultado = self._service.cruzar_com_banco(documento, boletos)
        except SQLAlchemyError as erro:
            messagebox.showerror("Erro de banco", f"Não foi possível consultar as parcelas:\n{erro}")
            return

        self._documento_atual = documento
        self._resultado = resultado
        self._preencher(resultado)

        partes = [f"{len(resultado.pareamentos)} cruzada(s)"]
        if resultado.boletos_sem_parcela:
            partes.append(f"{len(resultado.boletos_sem_parcela)} boleto(s) sem parcela")
        if resultado.parcelas_sem_boleto:
            partes.append(f"{len(resultado.parcelas_sem_boleto)} parcela(s) sem boleto")
        self._status.set(" | ".join(partes))

        if sem_linha:
            messagebox.showwarning(
                "PDFs sem linha digitável",
                "Não foi possível extrair a linha digitável de:\n- " + "\n- ".join(sem_linha),
            )

        self._btn_gravar.config(state="normal" if resultado.pareamentos else "disabled")

    def _preencher(self, resultado: ResultadoCruzamento) -> None:
        self._tabela.delete(*self._tabela.get_children())

        for par in resultado.pareamentos:
            b = par.boleto
            self._tabela.insert(
                "", "end",
                values=(b.arquivo, b.linha_digitavel, b.valor_formatado, b.vencimento_formatado,
                        par.parcela.cod, "Pronto"),
            )

        for b in resultado.boletos_sem_parcela:
            self._tabela.insert(
                "", "end",
                values=(b.arquivo, b.linha_digitavel, b.valor_formatado, b.vencimento_formatado,
                        "—", "Sem parcela"),
            )

    def _gravar(self) -> None:
        if self._resultado is None:
            return

        total = len(self._resultado.pareamentos)
        acao = "substituindo" if self._modo is ModoGravacao.SOBRESCREVER else "anexando"
        confirmar = messagebox.askyesno(
            "Confirmar gravação",
            f"Serão atualizadas {total} parcela(s), {acao} a linha digitável nas observações.\n\nContinuar?",
        )
        if not confirmar:
            return

        try:
            gravadas = self._service.gravar(self._resultado, self._modo)
        except SQLAlchemyError as erro:
            messagebox.showerror("Erro ao gravar", f"Nada foi gravado. Motivo:\n{erro}")
            return

        messagebox.showinfo("Concluído", f"{gravadas} parcela(s) atualizada(s).")
        self._resultado = None
        self._btn_gravar.config(state="disabled")
        self._status.set(f"{gravadas} observação(ões) gravada(s).")

    def _copiar_linha(self, evento: tk.Event) -> None:
        item = self._tabela.identify_row(evento.y)
        if not item:
            return
        self.clipboard_clear()
        self.clipboard_append(self._tabela.set(item, "linha"))
        self._status.set("Linha digitável copiada.")
