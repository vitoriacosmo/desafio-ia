"""
Nível 1 — Tratamento de Dados, Regras Determinísticas e Parecer com LLM

Módulo executável completo com a esteira de PLD/AML:
1. Carga, deduplicação e normalização cambial
2. Agregações estatísticas por cliente e canal
3. Regras determinísticas de Fracionamento e Valor Atípico
4. Validação das regras
5. Parecer estruturado com Pydantic e chamada à API real de LLM (Gemini / Groq)
6. Comparação entre versões de prompt com métricas reais (latência e tokens)
"""

import os
import sys
import json
import time
import re
import warnings
from typing import List, Literal, Tuple, Dict, Any
import pandas as pd
import numpy as np
from pydantic import BaseModel, Field
from dotenv import load_dotenv, find_dotenv

if sys.platform.startswith("win"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

warnings.filterwarnings("ignore")
load_dotenv(find_dotenv(usecwd=True))

pd.set_option("display.max_columns", None)
pd.set_option("display.float_format", lambda x: f"{x:.2f}")

class ParecerPLD(BaseModel):
    cliente_id: str = Field(..., description="ID do cliente")
    nivel_risco: Literal["baixo", "medio", "alto"] = Field(..., description="Nível de risco")
    tipologia_suspeita: str = Field(..., description="Tipologia identificada")
    red_flags: List[str] = Field(default_factory=list, description="Lista de red flags")
    justificativa: str = Field(..., description="Justificativa da classificação")

def extrair_contexto(cliente_id: str, df: pd.DataFrame) -> dict:
    df_c = df[df["cliente_id"] == cliente_id]
    return {
        "cliente_id": cliente_id,
        "total_operacoes": int(len(df_c)),
        "volume_total_brl": float(df_c["valor_brl"].sum()),
        "mediana_brl": float(df_c["valor_brl"].median()),
        "flags_regra_1": int(df_c["flag_regra_1"].sum()),
        "flags_regra_2": int(df_c["flag_regra_2"].sum()),
        "datas_fracionamento": df_c[df_c["flag_regra_1"]]["data"].dropna().unique().tolist(),
        "canais": df_c["canal"].value_counts().to_dict(),
        "contrapartes": df_c["contraparte"].unique().tolist(),
        "operacoes": df_c[["id", "data", "valor_brl", "canal", "tipo", "contraparte", "flag_regra_1", "flag_regra_2"]].to_dict(orient="records")
    }

def aplicar_regras(df: pd.DataFrame) -> pd.DataFrame:
    df_out = df.copy()
    
    # Regra 1: Fracionamento
    df_validas = df_out[df_out["data_valida"]].copy()
    grp_dia = df_validas.groupby(["cliente_id", "data"]).agg(
        n_ops=("valor_brl", "count"),
        soma_dia=("valor_brl", "sum"),
        max_op=("valor_brl", "max")
    ).reset_index()
    
    grp_dia["flag_regra_1"] = (
        (grp_dia["n_ops"] >= 3) &
        (grp_dia["soma_dia"] > 50000.00) &
        (grp_dia["max_op"] < 20000.00)
    )
    
    fracionados = grp_dia[grp_dia["flag_regra_1"]][["cliente_id", "data"]].drop_duplicates()
    fracionados["flag_regra_1"] = True
    
    df_out = df_out.merge(fracionados, on=["cliente_id", "data"], how="left")
    df_out["flag_regra_1"] = df_out["flag_regra_1"].fillna(False)
    
    # Regra 2: Valor atípico
    stats_cli = df_out.groupby("cliente_id").agg(
        n_ops_cli=("valor_brl", "count"),
        mediana_cli=("valor_brl", "median")
    ).reset_index()
    
    df_out = df_out.merge(stats_cli, on="cliente_id", how="left")
    df_out["limiar_outlier"] = df_out["mediana_cli"] * 5.0
    
    df_out["flag_regra_2"] = (
        (df_out["n_ops_cli"] >= 4) &
        (df_out["valor_brl"] > df_out["limiar_outlier"])
    )
    
    return df_out

def analisar_com_llm(system_prompt: str, user_prompt: str, cliente_id: str, contexto: dict) -> Tuple[ParecerPLD, float, Dict[str, Any], str]:
    t0 = time.time()
    
    gemini_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")
    groq_key = os.getenv("GROQ_API_KEY")
    provider = os.getenv("LLM_PROVIDER", "gemini").lower()
    
    fonte = "mock"
    texto_resposta = ""
    tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    
    if (provider == "gemini" and gemini_key) or (gemini_key and not groq_key):
        fonte = "gemini"
        import google.generativeai as genai
        genai.configure(api_key=gemini_key)
        
        prompt_completo = f"{system_prompt}\n\n{user_prompt}"
        model = genai.GenerativeModel("gemini-3.6-flash")
        resp = model.generate_content(prompt_completo)
        texto_resposta = resp.text
        
        tokens["prompt_tokens"] = getattr(resp.usage_metadata, "prompt_token_count", 0)
        tokens["completion_tokens"] = getattr(resp.usage_metadata, "candidates_token_count", 0)
        tokens["total_tokens"] = getattr(resp.usage_metadata, "total_token_count", 0)
        
    elif provider == "groq" and groq_key:
        fonte = "groq"
        from groq import Groq
        client = Groq(api_key=groq_key)
        completion = client.chat.completions.create(
            model="llama-3.3-70b-versatile",
            messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
            temperature=0.1,
            response_format={"type": "json_object"}
        )
        texto_resposta = completion.choices[0].message.content
        tokens["prompt_tokens"] = completion.usage.prompt_tokens
        tokens["completion_tokens"] = completion.usage.completion_tokens
        tokens["total_tokens"] = completion.usage.total_tokens
    else:
        print("[AVISO] Nenhuma API key encontrada. Rodando em MODO MOCK. Resultados abaixo não vêm de um LLM real.")
        fonte = "mock"
        texto_resposta = json.dumps({
            "cliente_id": cliente_id,
            "nivel_risco": "alto",
            "tipologia_suspeita": "Fracionamento de Recursos (Smurfing / Structuring)",
            "red_flags": ["Múltiplas transações em mesmo dia somando > R$ 50.000"],
            "justificativa": "Parecer estruturado emitido em modo mock."
        }, ensure_ascii=False)
        tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
        
    latencia_ms = round((time.time() - t0) * 1000, 2)
    
    try:
        match = re.search(r"\{.*\}", texto_resposta, re.DOTALL)
        dados = json.loads(match.group(0)) if match else json.loads(texto_resposta)
        if "nivel_risco" in dados:
            dados["nivel_risco"] = str(dados["nivel_risco"]).lower().strip()
            if "médio" in dados["nivel_risco"]:
                dados["nivel_risco"] = "medio"
    except Exception:
        dados = {
            "cliente_id": cliente_id,
            "nivel_risco": "alto",
            "tipologia_suspeita": "Fracionamento de Recursos",
            "red_flags": ["Falha no parser JSON da resposta"],
            "justificativa": texto_resposta[:200]
        }
        
    return ParecerPLD(**dados), latencia_ms, tokens, fonte

def main():
    caminhos = [
        os.path.join(os.path.dirname(__file__), "..", "dados", "dados_nivel_1.json"),
        os.path.join("dados", "dados_nivel_1.json")
    ]
    caminho_dados = next((p for p in caminhos if os.path.exists(p)), "dados/dados_nivel_1.json")

    with open(caminho_dados, "r", encoding="utf-8") as f:
        dados_json = json.load(f)

    taxa_cambio = float(dados_json.get("taxa_cambio_usd_brl", 5.4))
    df_raw = pd.DataFrame(dados_json["operacoes"])

    print("=" * 80)
    print("1. TRATAMENTO E LIMPEZA DOS DADOS")
    print("=" * 80)
    print(f"Total de registros brutos: {len(df_raw)}")
    print(f"Taxa USD/BRL: {taxa_cambio}")

    df_limpo = df_raw.drop_duplicates(subset=["id"], keep="first").copy()
    for col in ["id", "cliente_id", "moeda", "canal", "tipo", "contraparte", "observacao"]:
        df_limpo[col] = df_limpo[col].fillna("").astype(str).str.strip()

    df_limpo["valor"] = pd.to_numeric(df_limpo["valor"], errors="coerce").fillna(0.0)
    df_limpo["valor_brl"] = np.where(
        df_limpo["moeda"].str.upper() == "USD",
        df_limpo["valor"] * taxa_cambio,
        df_limpo["valor"]
    ).round(2)

    df_limpo["data_dt"] = pd.to_datetime(df_limpo["data"], errors="coerce")
    df_limpo["data_valida"] = df_limpo["data_dt"].notnull()
    print(f"Total de registros após deduplicação: {len(df_limpo)}")
    print(df_limpo[["id", "cliente_id", "data", "valor_brl", "canal", "tipo", "contraparte"]].to_string(index=False))

    print("\n" + "=" * 80)
    print("2. AGREGAÇÕES ESTATÍSTICAS")
    print("=" * 80)
    volume_cliente = df_limpo.groupby("cliente_id").agg(
        total_operacoes=("valor_brl", "count"),
        volume_total_brl=("valor_brl", "sum"),
        ticket_medio_brl=("valor_brl", "mean"),
        mediana_brl=("valor_brl", "median"),
        maior_operacao_brl=("valor_brl", "max"),
        menor_operacao_brl=("valor_brl", "min")
    ).reset_index().sort_values(by="volume_total_brl", ascending=False)
    print("Volume transacionado por cliente:")
    print(volume_cliente.to_string(index=False))

    ops_canal = df_limpo.groupby("canal").agg(
        quantidade=("id", "count"),
        volume_total_brl=("valor_brl", "sum")
    ).reset_index().sort_values(by="quantidade", ascending=False)
    print("\nOperações por canal:")
    print(ops_canal.to_string(index=False))

    print("\n" + "=" * 80)
    print("3. REGRAS DETERMINÍSTICAS DE PLD")
    print("=" * 80)
    df_flagged = aplicar_regras(df_limpo)
    print(df_flagged[["id", "cliente_id", "data", "valor_brl", "canal", "tipo", "flag_regra_1", "flag_regra_2"]].to_string(index=False))

    print("\n" + "=" * 80)
    print("4. VALIDAÇÃO DAS REGRAS")
    print("=" * 80)
    print("Validação CLI-A-1 (Fracionamento detectado):")
    print(df_flagged[(df_flagged["cliente_id"] == "CLI-A-1") & (df_flagged["data"] == "2026-03-09")][
        ["id", "cliente_id", "data", "valor_brl", "flag_regra_1"]
    ].to_string(index=False))

    print("\nValidação CLI-A-2 (Soma > 50k, mas apenas 2 operações e valores >= 20k -> Flag False):")
    print(df_flagged[df_flagged["cliente_id"] == "CLI-A-2"][
        ["id", "cliente_id", "data", "valor_brl", "flag_regra_1"]
    ].to_string(index=False))

    print("\nValidação CLI-A-3 (3 operações < 20k, mas soma < 50k -> Flag False):")
    print(df_flagged[df_flagged["cliente_id"] == "CLI-A-3"][
        ["id", "cliente_id", "data", "valor_brl", "flag_regra_1"]
    ].to_string(index=False))

    print("\nValidação CLI-A-4 (Regra 2 - Outlier > 5x a mediana):")
    print(df_flagged[df_flagged["cliente_id"] == "CLI-A-4"][
        ["id", "cliente_id", "data", "valor_brl", "mediana_cli", "limiar_outlier", "flag_regra_2"]
    ].to_string(index=False))

    print("\n" + "=" * 80)
    print("5. ANÁLISE COM LLM E SAÍDA ESTRUTURADA (CLI-A-1)")
    print("=" * 80)
    contexto_cli_a1 = extrair_contexto("CLI-A-1", df_flagged)
    sys_p = "Você é um auditor de PLD/AML. Responda estritamente em JSON com: cliente_id, nivel_risco (baixo/medio/alto), tipologia_suspeita, red_flags (lista), justificativa."
    usr_p = f"Analise os dados do cliente CLI-A-1:\n{json.dumps(contexto_cli_a1, indent=2, ensure_ascii=False)}"
    parecer_cli, latencia, tok, fonte = analisar_com_llm(sys_p, usr_p, "CLI-A-1", contexto_cli_a1)
    print(f"Fonte: {fonte} | Tempo de resposta: {latencia} ms | Tokens totais: {tok['total_tokens']}")
    print(json.dumps(parecer_cli.model_dump(), indent=2, ensure_ascii=False))

    print("\n" + "=" * 80)
    print("6. COMPARAÇÃO ENTRE DUAS VERSÕES DE PROMPT")
    print("=" * 80)
    p1_sys = "Você é um assistente de IA. Analise as transações financeiras e responda em JSON com as chaves: cliente_id, nivel_risco (baixo/medio/alto), tipologia_suspeita, red_flags (lista), justificativa."
    p1_usr = f"Dados do cliente CLI-A-1: {json.dumps(contexto_cli_a1, ensure_ascii=False)}"
    parecer_v1, lat_v1, tok_v1, fonte_v1 = analisar_com_llm(p1_sys, p1_usr, "CLI-A-1", contexto_cli_a1)

    p2_sys = (
        "Você é um auditor especialista em Prevenção à Lavagem de Dinheiro (PLD/AML).\n"
        "Diretrizes:\n"
        "1. Baseie-se estritamente nos fatos observados no dossiê.\n"
        "2. Avalie se as operações caracterizam fracionamento de transações (smurfing/structuring).\n"
        "3. Identifique as contrapartes e canais utilizados.\n"
        "4. Responda em JSON com os campos: cliente_id, nivel_risco (baixo/medio/alto), tipologia_suspeita, red_flags, justificativa."
    )
    p2_usr = f"Dossiê financeiro do cliente CLI-A-1:\n{json.dumps(contexto_cli_a1, indent=2, ensure_ascii=False)}"
    parecer_v2, lat_v2, tok_v2, fonte_v2 = analisar_com_llm(p2_sys, p2_usr, "CLI-A-1", contexto_cli_a1)

    df_comparacao = pd.DataFrame([
        {
            "Versão": "Versão 1 (Zero-Shot Básico)",
            "Fonte": fonte_v1,
            "Nível de Risco": parecer_v1.nivel_risco.upper(),
            "Tipologia": parecer_v1.tipologia_suspeita,
            "Red Flags": len(parecer_v1.red_flags),
            "Latência (ms)": lat_v1,
            "Tokens": tok_v1["total_tokens"],
            "Justificativa": parecer_v1.justificativa
        },
        {
            "Versão": "Versão 2 (Especializado)",
            "Fonte": fonte_v2,
            "Nível de Risco": parecer_v2.nivel_risco.upper(),
            "Tipologia": parecer_v2.tipologia_suspeita,
            "Red Flags": len(parecer_v2.red_flags),
            "Latência (ms)": lat_v2,
            "Tokens": tok_v2["total_tokens"],
            "Justificativa": parecer_v2.justificativa
        }
    ])
    print(df_comparacao[["Versão", "Fonte", "Nível de Risco", "Tipologia", "Red Flags", "Latência (ms)", "Tokens"]].to_string(index=False))
    print("\nJustificativa Versão 1:\n", parecer_v1.justificativa)
    print("\nJustificativa Versão 2:\n", parecer_v2.justificativa)

if __name__ == "__main__":
    main()
