"""
# Dados e primeira analise com LLM
Modulo de tratamento de dados legados, identificacao de inconsistencias/nulos
e mapeamento da janela temporal para analises futuras de PLD/AML.
"""

import os
import sys
import json
import unicodedata
import pandas as pd
from datetime import datetime

# Garante suporte a UTF-8 na saida padrao
if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

def main():
    # Caminho do arquivo de dados
    caminho_dados = os.path.join(os.path.dirname(__file__), "..", "dados", "dados_nivel_1.json")
    
    # 1. Carregamento dos dados brutos
    with open(caminho_dados, "r", encoding="utf-8") as f:
        raw_data = json.load(f)

    taxa_cambio = raw_data.get("taxa_cambio_usd_brl", 5.4)
    df = pd.DataFrame(raw_data["operacoes"])

    # -------------------------------------------------------------
    # PARTE 1: Tratamento dos Dados e Sinalizacao de Valores Nulos
    # -------------------------------------------------------------
    def limpar_texto(valor):
        if isinstance(valor, str):
            return "".join(c for c in valor if unicodedata.category(c)[0] != "C").strip()
        return valor

    # Limpeza de caracteres invisiveis/controle
    df = df.map(limpar_texto)

    # Deduplicacao de registros repetidos
    df_tratado = df.drop_duplicates(subset=["id"], keep="first").copy()

    # Sinalizacao de registros nulos ou com texto indicativo de nulo
    condicao_nulo = (
        df_tratado.isnull().any(axis=1) | 
        df_tratado.isin(["NULO", "NULL", "None", "nan"]).any(axis=1)
    )
    registros_nulos = df_tratado[condicao_nulo]

    print("=" * 60)
    print("PARTE 1: RELATORIO DE HIGIENIZACAO E AUDITORIA DE DADOS")
    print("=" * 60)
    print(f"Total de registros validos pos-deduplicacao: {len(df_tratado)}")
    print(f"Total de operacoes com campos nulos identificadas: {len(registros_nulos)}\n")

    for _, row in registros_nulos.iterrows():
        print("[ALERTA DE CAMPO NULO]")
        print(f"   - ID da Operacao: {row['id']}")
        print(f"   - Cliente: {row['cliente_id']}")
        print(f"   - Campo com Nulo: 'data' -> {row['data']}")
        print(f"   - Canal / Tipo: {row['canal']} / {row['tipo']}")
        print(f"   - Valor: R$ {row['valor']:,.2f}")
        print(f"   - Observacao do Legado: '{row['observacao']}'")

    # -------------------------------------------------------------
    # PARTE 2: Analise da Janela Temporal (Espaco entre Datas)
    # -------------------------------------------------------------
    df_temporal = df_tratado[df_tratado["data"].notnull() & (df_tratado["data"] != "")].copy()
    df_temporal["data_dt"] = pd.to_datetime(df_temporal["data"], format="%Y-%m-%d")

    primeira_data = df_temporal["data_dt"].min()
    ultima_data = df_temporal["data_dt"].max()
    intervalo_dias = (ultima_data - primeira_data).days

    op_primeira = df_temporal.loc[df_temporal["data_dt"].idxmin()]
    op_ultima = df_temporal.loc[df_temporal["data_dt"].idxmax()]

    print("\n" + "=" * 60)
    print("PARTE 2: ANALISE DO ESPACO TEMPORAL ENTRE AS DATAS")
    print("=" * 60)
    print(f"- Primeira transacao registrada: {primeira_data.strftime('%d/%m/%Y')} ({primeira_data.strftime('%d/%m')})")
    print(f"  -> Operacao: {op_primeira['id']} | Cliente: {op_primeira['cliente_id']} | Valor: R$ {op_primeira['valor']:,.2f}")
    print(f"- Ultima transacao registrada:   {ultima_data.strftime('%d/%m/%Y')} ({ultima_data.strftime('%d/%m')})")
    print(f"  -> Operacao: {op_ultima['id']} | Cliente: {op_ultima['cliente_id']} | Valor: R$ {op_ultima['valor']:,.2f}")
    print(f"- Espaco temporal total:         {intervalo_dias} dias (de {primeira_data.strftime('%d/%m')} a {ultima_data.strftime('%d/%m')})")
    print("=" * 60)

if __name__ == "__main__":
    main()
