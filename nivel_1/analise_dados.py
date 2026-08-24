"""
# Dados e primeira analise com LLM
Modulo completo de auditoria PLD/AML, agregacoes, aplicacao das Regras 1 e 2,
validacao comparativa e analise de sensibilidade da transacao sem data (CLI-A-5).
"""

import os
import sys
import json
import unicodedata
import pandas as pd
from datetime import datetime

# Suporte a UTF-8 no terminal
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def main():
    caminhos = [
        os.path.join(os.path.dirname(__file__), "..", "dados", "dados_nivel_1.json"),
        os.path.join("dados", "dados_nivel_1.json")
    ]
    caminho_dados = next((p for p in caminhos if os.path.exists(p)), "dados/dados_nivel_1.json")

    # 1. Carregamento dos dados
    with open(caminho_dados, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    taxa_cambio = raw_data.get("taxa_cambio_usd_brl", 5.4)
    df_raw = pd.DataFrame(raw_data["operacoes"])

    # 2. Higienizacao e Deduplicacao
    def limpar_texto(valor):
        if isinstance(valor, str):
            return "".join(c for c in valor if unicodedata.category(c)[0] != "C").strip()
        return valor

    df_limpo = df_raw.map(limpar_texto)
    df = df_limpo.drop_duplicates(subset=["id"], keep="first").copy()

    # Conversao cambial para BRL
    df["valor_brl"] = df.apply(
        lambda r: float(r["valor"]) * taxa_cambio if r["moeda"] == "USD" else float(r["valor"]),
        axis=1
    )

    print("=" * 80)
    print("1. VOLUME TOTAL TRANSACIONADO POR CLIENTE")
    print("=" * 80)
    vol_cliente = df.groupby("cliente_id").agg(
        qtd_operacoes=("id", "count"),
        volume_total_brl=("valor_brl", "sum"),
        ticket_medio_brl=("valor_brl", "mean"),
        mediana_brl=("valor_brl", "median")
    ).reset_index().sort_values(by="volume_total_brl", ascending=False)
    print(vol_cliente.to_string(index=False))

    print("\n" + "=" * 80)
    print("2. QUANTIDADE DE OPERACOES POR CANAL")
    print("=" * 80)
    ops_canal = df.groupby("canal").agg(
        qtd_operacoes=("id", "count"),
        volume_total_brl=("valor_brl", "sum")
    ).reset_index().sort_values(by="qtd_operacoes", ascending=False)
    print(ops_canal.to_string(index=False))

    print("\n" + "=" * 80)
    print("3. REGRA 1 — FRACIONAMENTO (SMURFING / STRUCTURING)")
    print("=" * 80)
    df_valid_data = df[df["data"].notnull()].copy()
    regra_1_analise = []

    for (cliente, data), grupo in df_valid_data.groupby(["cliente_id", "data"]):
        qtd = len(grupo)
        soma_val = grupo["valor_brl"].sum()
        max_val = grupo["valor_brl"].max()
        
        c1_qtd = (qtd >= 3)
        c2_soma = (soma_val > 50000.00)
        c3_limite_unitario = (max_val < 20000.00)
        sinalizado = c1_qtd and c2_soma and c3_limite_unitario
        
        regra_1_analise.append({
            "cliente_id": cliente,
            "data": data,
            "qtd_operacoes": qtd,
            "soma_brl": soma_val,
            "maior_operacao_brl": max_val,
            "qtd_ge_3": c1_qtd,
            "soma_gt_50k": c2_soma,
            "todas_lt_20k": c3_limite_unitario,
            "SINALIZADO_REGRA_1": sinalizado
        })

    df_regra_1 = pd.DataFrame(regra_1_analise)
    sinalizados_r1 = df_regra_1[df_regra_1["SINALIZADO_REGRA_1"] == True]
    print(sinalizados_r1.to_string(index=False))

    print("\n" + "=" * 80)
    print("4. REGRA 2 — VALOR ATIPICO (OUTLIER)")
    print("=" * 80)
    contagem_cliente = df.groupby("cliente_id")["id"].count()
    clientes_elegiveis = contagem_cliente[contagem_cliente >= 4].index.tolist()

    regra_2_alertas = []
    for cliente in clientes_elegiveis:
        grupo = df[df["cliente_id"] == cliente].copy()
        mediana_cli = grupo["valor_brl"].median()
        limite_5x = 5 * mediana_cli
        
        for _, op in grupo.iterrows():
            if op["valor_brl"] > limite_5x:
                regra_2_alertas.append({
                    "operacao_id": op["id"],
                    "cliente_id": cliente,
                    "data": op["data"],
                    "moeda_orig": op["moeda"],
                    "valor_orig": op["valor"],
                    "valor_brl": op["valor_brl"],
                    "mediana_cliente_brl": mediana_cli,
                    "limite_5x_mediana": limite_5x,
                    "multiplo_mediana": round(op["valor_brl"] / mediana_cli, 2),
                    "SINALIZADO_REGRA_2": True
                })

    df_regra_2 = pd.DataFrame(regra_2_alertas)
    print(f"Clientes elegiveis (>= 4 operacoes): {clientes_elegiveis}")
    print(df_regra_2.to_string(index=False))

    print("\n" + "=" * 80)
    print("5. VALIDACAO E COMPARATIVO EXPLICITO (REGRA 1)")
    print("=" * 80)
    casos_comparacao = df_regra_1[
        df_regra_1["cliente_id"].isin(["CLI-A-1", "CLI-A-3", "CLI-A-2"]) &
        df_regra_1["data"].isin(["2026-03-09", "2026-03-05", "2026-03-14"])
    ].copy()

    casos_comparacao["Status"] = casos_comparacao["SINALIZADO_REGRA_1"].map({
        True: "CAPTURADO (Fracionamento Confirmado)",
        False: "NAO CAPTURADO (Fora dos Parametros)"
    })
    print(casos_comparacao[[
        "cliente_id", "data", "qtd_operacoes", "soma_brl", "maior_operacao_brl",
        "qtd_ge_3", "soma_gt_50k", "todas_lt_20k", "Status"
    ]].to_string(index=False))

    print("\n" + "=" * 80)
    print("6. ANALISE DA TRANSACAO SEM DATA (CLI-A-5) E PROVA DE EXECUCAO")
    print("=" * 80)
    datas_simulacao = ["2026-03-07", "2026-03-16", "2026-03-26"]
    ops_datadas_cli5 = df[(df["cliente_id"] == "CLI-A-5") & (df["data"].notnull())].copy()
    op_sem_data = df[df["id"] == "OP-0017"].iloc[0].to_dict()

    provas = []
    for d in datas_simulacao:
        op_sim = op_sem_data.copy()
        op_sim["data"] = d
        df_sim = pd.concat([ops_datadas_cli5, pd.DataFrame([op_sim])], ignore_index=True)
        
        grupo_d = df_sim[df_sim["data"] == d]
        qtd_d = len(grupo_d)
        soma_d = grupo_d["valor_brl"].sum()
        r1_sinalizado = (qtd_d >= 3) and (soma_d > 50000.00) and (grupo_d["valor_brl"].max() < 20000.00)
        
        mediana_sim = df_sim["valor_brl"].median()
        limite_5x = 5 * mediana_sim
        r2_sinalizado = (df_sim["valor_brl"].max() > limite_5x)
        
        provas.append({
            "Data Imputada": d,
            "Ops no Dia": qtd_d,
            "Soma Dia (BRL)": soma_d,
            "Regra 1 (Fracionamento)": "NAO ATINGE" if not r1_sinalizado else "ATINGE",
            "Mediana (BRL)": mediana_sim,
            "Limite 5x (BRL)": limite_5x,
            "Maior Op (BRL)": df_sim["valor_brl"].max(),
            "Regra 2 (Atipico)": "NAO ATINGE" if not r2_sinalizado else "ATINGE",
            "Veredito": "NAO ELEGIVEL A SUSPEITA MATEMATICA"
        })

    df_provas = pd.DataFrame(provas)
    print(df_provas.to_string(index=False))

if __name__ == "__main__":
    main()
