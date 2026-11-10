import os
import re
import json
from datetime import date, datetime, timedelta
import tkinter as tk
from tkinter import ttk, filedialog, messagebox, simpledialog
import PyPDF2


# --- Extração e formatação dos dados do boleto ---

def extrair_linha_digitavel(texto):
    # Padrão Regex que funcionou perfeitamente para o seu modelo
    padrao = r'\d{5}\.?\s*\d{5}\s*\d{5}\.?\s*\d{6}\s*\d{5}\.?\s*\d{6}\s*\d{1}\s*\d{14}'
    resultados = re.findall(padrao, texto)

    codigos_limpos = []
    for res in resultados:
        codigo_so_numeros = re.sub(r'\D', '', res)
        codigos_limpos.append(codigo_so_numeros)

    return codigos_limpos


def formatar_valor(codigo):
    # Posições 37 a 46 da linha digitável: valor em centavos
    centavos = int(codigo[37:47])
    if centavos == 0:
        return "—"  # boleto sem valor definido
    valor = centavos / 100
    texto = f"{valor:,.2f}"  # 1,234.56
    texto = texto.replace(",", "X").replace(".", ",").replace("X", ".")  # 1.234,56
    return f"R$ {texto}"


def formatar_vencimento(codigo):
    # Posições 33 a 36: fator de vencimento (dias desde 07/10/1997)
    fator = int(codigo[33:37])
    if fator == 0:
        return "—"  # boleto sem vencimento

    base = date(1997, 10, 7)
    hoje = date.today()

    # Ciclo antigo e ciclo novo (a partir de 22/02/2025, +9000 dias)
    candidatos = [
        base + timedelta(days=fator),
        base + timedelta(days=fator + 9000),
    ]

    # Fica com a data mais próxima de hoje
    vencimento = min(candidatos, key=lambda d: abs((d - hoje).days))
    return vencimento.strftime("%d/%m/%Y")


# --- Conversões para o cruzamento com o banco ---

def valor_tabela_para_centavos(texto):
    # "R$ 1.234,56" -> 123456
    if not texto or texto == "—":
        return None
    s = texto.replace("R$", "").strip()
    s = s.replace(".", "").replace(",", ".")
    return round(float(s) * 100)


def valor_banco_para_centavos(texto):
    # Aceita "1234.56", "1234,56" ou "1.234,56"
    s = texto.strip()
    if "," in s:
        s = s.replace(".", "").replace(",", ".")
    return round(float(s) * 100)


def data_tabela_para_data(texto):
    if not texto or texto == "—":
        return None
    return datetime.strptime(texto, "%d/%m/%Y").date()


def data_banco_para_data(texto):
    # Aceita "2026-12-29", "2026-12-29 00:00:00" ou "29/12/2026"
    s = texto.strip()[:10]
    for formato in ("%Y-%m-%d", "%d/%m/%Y"):
        try:
            return datetime.strptime(s, formato).date()
        except ValueError:
            pass
    raise ValueError(f"Data inválida: {texto}")


def ler_parcelas_coladas(texto):
    # Espera colunas: cod, documento, dtvencimento, vlrdocumento (Tab, ; ou |)
    parcelas = []
    for linha in texto.splitlines():
        partes = [p.strip() for p in re.split(r'\t|;|\|', linha)]
        if len(partes) < 4 or not partes[0].isdigit() or not partes[1].isdigit():
            continue  # ignora cabeçalhos, linhas vazias e linhas de rodapé
        try:
            parcelas.append({
                "cod": int(partes[0]),
                "documento": int(partes[1]),
                "vencimento": data_banco_para_data(partes[2]),
                "centavos": valor_banco_para_centavos(partes[3]),
            })
        except ValueError:
            continue
    return sorted(parcelas, key=lambda p: p["cod"])


# --- Ações da interface ---

def copiar_codigo(codigo):
    root.clipboard_clear()
    root.clipboard_append(codigo)
    lbl_status.config(text="Código copiado para a área de transferência!")
    root.after(2000, lambda: lbl_status.config(text=""))


def processar_arquivos():
    arquivos_selecionados = filedialog.askopenfilenames(
        title="Selecione os PDFs dos boletos",
        filetypes=[("Arquivos PDF", "*.pdf")]
    )

    if not arquivos_selecionados:
        return

    # Limpa a tabela antes de carregar novos arquivos
    for item in tabela.get_children():
        tabela.delete(item)

    posicao_atual = 1

    for caminho_completo in arquivos_selecionados:
        nome_arquivo = os.path.basename(caminho_completo)

        try:
            with open(caminho_completo, 'rb') as arquivo_pdf:
                leitor = PyPDF2.PdfReader(arquivo_pdf)
                texto_completo = ""

                for pagina in leitor.pages:
                    texto_extraido = pagina.extract_text()
                    if texto_extraido:
                        texto_completo += texto_extraido + " "

                codigos = extrair_linha_digitavel(texto_completo)
                if codigos:
                    # Colunas: Posição, Linha Digitável, Valor, Vencimento, Arquivo, Ação
                    tabela.insert('', 'end', values=(
                        posicao_atual,
                        codigos[0],
                        formatar_valor(codigos[0]),
                        formatar_vencimento(codigos[0]),
                        nome_arquivo,
                        'Copiar'
                    ))
                    posicao_atual += 1

        except Exception as e:
            print(f"Erro ao ler {nome_arquivo}: {e}")


def editar_posicao(event):
    # Não abre a edição se o duplo clique foi na coluna "Ação"
    if tabela.identify_column(event.x) == '#6':
        return

    item_selecionado = tabela.selection()
    if not item_selecionado:
        return

    valores_atuais = tabela.item(item_selecionado[0], 'values')
    posicao_antiga = valores_atuais[0]
    codigo = valores_atuais[1]
    valor = valores_atuais[2]
    vencimento = valores_atuais[3]
    arquivo = valores_atuais[4]

    nova_posicao = simpledialog.askinteger(
        "Editar Parcela",
        f"Arquivo: {arquivo}\n\nDigite a nova posição (parcela) para este boleto:",
        initialvalue=int(posicao_antiga)
    )

    if nova_posicao is not None:
        tabela.item(item_selecionado[0], values=(nova_posicao, codigo, valor, vencimento, arquivo, 'Copiar'))
        ordenar_tabela()


def ordenar_tabela():
    linhas = [(int(tabela.set(k, 'Posição')), k) for k in tabela.get_children('')]
    linhas.sort()

    for index, (valor, k) in enumerate(linhas):
        tabela.move(k, '', index)


def clique_tabela(event):
    regiao = tabela.identify_region(event.x, event.y)
    coluna = tabela.identify_column(event.x)   # '#6' = coluna "Ação"
    linha = tabela.identify_row(event.y)

    if regiao == 'cell' and coluna == '#6' and linha:
        codigo = tabela.set(linha, 'Linha Digitável')
        copiar_codigo(codigo)


# --- Geração do SQL de observações ---

def ler_parcelas_json(caminho):
    # Aceita uma lista de objetos ou o formato {"SELECT ...": [ ... ]}
    with open(caminho, 'r', encoding='utf-8') as arquivo_json:
        dados = json.load(arquivo_json)

    if isinstance(dados, dict):
        dados = next((v for v in dados.values() if isinstance(v, list)), [])

    parcelas = []
    for registro in dados:
        try:
            parcelas.append({
                "cod": int(registro["pagparc_cod"]),
                "documento": int(registro["pagparc_documento"]),
                "vencimento": data_banco_para_data(str(registro["pagparc_dtvencimento"])),
                "centavos": round(float(registro["pagparc_vlrdocumento"]) * 100),
            })
        except (KeyError, ValueError, TypeError):
            continue
    return sorted(parcelas, key=lambda p: p["cod"])


def importar_json_observacoes():
    if not tabela.get_children(''):
        messagebox.showinfo("Aviso", "Extraia os boletos antes de gerar o SQL.")
        return

    caminho = filedialog.askopenfilename(
        title="Selecione o JSON do SELECT",
        filetypes=[("Arquivo JSON", "*.json")]
    )
    if not caminho:
        return

    try:
        parcelas = ler_parcelas_json(caminho)
    except (OSError, json.JSONDecodeError) as e:
        messagebox.showerror("Erro", f"Não foi possível ler o JSON:\n{e}")
        return

    gerar_sql_observacoes(parcelas)


def gerar_sql_observacoes(parcelas_banco):
    if not parcelas_banco:
        messagebox.showwarning("Aviso", "Nenhuma parcela válida foi encontrada no texto colado.")
        return

    disponiveis = list(parcelas_banco)
    comandos = []
    nao_encontrados = []

    # Percorre a tabela na ordem das posições e cruza com as parcelas do banco
    for item in tabela.get_children(''):
        pos, linha, valor, venc, arquivo, _ = tabela.item(item, 'values')
        centavos = valor_tabela_para_centavos(valor)
        vencimento = data_tabela_para_data(venc)

        if centavos is None or vencimento is None:
            nao_encontrados.append(f"{arquivo} (sem valor ou vencimento)")
            continue

        escolhida = next(
            (p for p in disponiveis if p["centavos"] == centavos and p["vencimento"] == vencimento),
            None
        )

        if escolhida is None:
            nao_encontrados.append(f"{arquivo} (parcela {pos}, {valor}, {venc})")
            continue

        disponiveis.remove(escolhida)
        comandos.append(
            f"UPDATE pagar_parcelas SET pagparc_obs = '{linha}' "
            f"WHERE pagparc_cod = {escolhida['cod']} "
            f"AND pagparc_documento = {escolhida['documento']};"
        )

    if not comandos:
        messagebox.showwarning("Aviso", "Nenhuma parcela foi cruzada com os boletos. Confira valores e vencimentos.")
        return

    caminho = filedialog.asksaveasfilename(
        defaultextension=".sql",
        initialfile="atualizar_observacoes.sql",
        filetypes=[("Arquivo SQL", "*.sql")]
    )
    if not caminho:
        return

    with open(caminho, 'w', encoding='utf-8') as arquivo_sql:
        arquivo_sql.write("-- Atualiza pagparc_obs com a linha digitável de cada boleto\n")
        arquivo_sql.write(f"-- Total de comandos: {len(comandos)}\n\n")
        arquivo_sql.write("\n".join(comandos) + "\n")

    resumo = f"{len(comandos)} parcela(s) cruzada(s) e salva(s) no arquivo SQL."
    if nao_encontrados:
        resumo += f"\n\nNão cruzadas ({len(nao_encontrados)}):\n- " + "\n- ".join(nao_encontrados)
    messagebox.showinfo("SQL gerado", resumo)
    lbl_status.config(text=f"SQL gerado com {len(comandos)} comando(s).")
    root.after(3000, lambda: lbl_status.config(text=""))


def abrir_janela_colagem():
    if not tabela.get_children(''):
        messagebox.showinfo("Aviso", "Extraia os boletos antes de gerar o SQL.")
        return

    janela = tk.Toplevel(root)
    janela.title("Colar resultado do SELECT")
    janela.geometry("800x400")

    tk.Label(
        janela,
        text="Cole o resultado do SELECT (colunas: pagparc_cod, pagparc_documento, "
             "pagparc_dtvencimento, pagparc_vlrdocumento).\n"
             "Use colunas separadas por Tab, ponto e vírgula ou barra vertical.",
        justify='left'
    ).pack(anchor='w', padx=10, pady=8)

    texto = tk.Text(janela, height=18)
    texto.pack(fill='both', expand=True, padx=10)

    def confirmar():
        conteudo = texto.get("1.0", "end")
        janela.destroy()
        gerar_sql_observacoes(ler_parcelas_coladas(conteudo))

    tk.Button(
        janela,
        text="Gerar SQL",
        command=confirmar,
        bg="#2196F3",
        fg="white",
        font=("Arial", 10, "bold")
    ).pack(pady=10)


# --- Configuração da Interface Gráfica Principal ---
root = tk.Tk()
root.title("Extrator e Organizador de Boletos")
root.geometry("1000x480")
root.eval('tk::PlaceWindow . center')

# Frame superior para os botões
frame_topo = tk.Frame(root)
frame_topo.pack(pady=10, fill='x')

btn_selecionar = tk.Button(
    frame_topo,
    text="1. Selecionar PDFs e Extrair",
    command=processar_arquivos,
    bg="#4CAF50",
    fg="white",
    font=("Arial", 10, "bold")
)
btn_selecionar.pack(side='left', padx=20)

lbl_instrucao = tk.Label(
    frame_topo,
    text="* Duplo clique em uma linha para editar a Posição | Clique em 'Copiar' para copiar a linha digitável",
    fg="gray"
)
lbl_instrucao.pack(side='right', padx=20)

# Configuração da Tabela (Treeview)
colunas = ('Posição', 'Linha Digitável', 'Valor', 'Vencimento', 'Arquivo de Origem', 'Ação')
tabela = ttk.Treeview(root, columns=colunas, show='headings', height=15)

tabela.heading('Posição', text='Posição / Parcela')
tabela.column('Posição', width=120, anchor='center')

tabela.heading('Linha Digitável', text='Linha Digitável')
tabela.column('Linha Digitável', width=300, anchor='center')

tabela.heading('Valor', text='Valor')
tabela.column('Valor', width=100, anchor='center')

tabela.heading('Vencimento', text='Vencimento')
tabela.column('Vencimento', width=110, anchor='center')

tabela.heading('Arquivo de Origem', text='Arquivo de Origem')
tabela.column('Arquivo de Origem', width=200, anchor='w')

tabela.heading('Ação', text='Ação')
tabela.column('Ação', width=80, anchor='center')

tabela.pack(pady=10, padx=20, fill='both', expand=True)

# Frame inferior com a ação de SQL
frame_base = tk.Frame(root)
frame_base.pack(pady=5, fill='x')

btn_sql = tk.Button(
    frame_base,
    text="Gerar SQL de observações",
    command=abrir_janela_colagem,
    bg="#2196F3",
    fg="white",
    font=("Arial", 10, "bold")
)
btn_sql.pack(side='left', padx=20)

btn_json = tk.Button(
    frame_base,
    text="Importar JSON do SELECT",
    command=importar_json_observacoes,
    bg="#FF9800",
    fg="white",
    font=("Arial", 10, "bold")
)
btn_json.pack(side='left', padx=10)

# Label de status (feedback)
lbl_status = tk.Label(root, text="", fg="green", font=("Arial", 9, "bold"))
lbl_status.pack(pady=5)

# Bindings
tabela.bind("<Button-1>", clique_tabela)
tabela.bind("<Double-1>", editar_posicao)

root.mainloop()
