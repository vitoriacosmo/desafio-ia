# Uso de Inteligência Artificial

Este documento descreve como diferentes modelos de Inteligência Artificial foram utilizados no desenvolvimento da solução de triagem de Prevenção à Lavagem de Dinheiro (PLD/AML).

---

## 1. Ferramentas e Modelos Utilizados

1. **Gemini 3.7 Flash / Gemini 3.6 Flash (`google-ai-studio`)**:
   - **Papel**: Modelo principal de inferência automatizada para geração dos pareceres técnicos estruturados de PLD/AML no pipeline de execução do código (`nivel_1/nivel_1.ipynb` e `nivel_1/analise_dados.py`).
   - **Justificativa**: Alta velocidade de resposta, suporte a chamadas de API com controle de latência/tokens e geração de saídas estruturadas em formato JSON estrito compatível com schema Pydantic.

2. **Claude 3.5 Sonnet (`Anthropic`)**:
   - **Papel**: Análise crítica, avaliação de decisões técnicas de compliance, especificidade das regras determinísticas e formulação da esteira de auditoria de dados.
   - **Justificativa**: Elevada capacidade de raciocínio lógico e aderência a requisitos regulatórios financeiros (Circular BACEN nº 3.978/2020).

3. **ChatGPT (Modelo Free / OpenAI)**:
   - **Papel**: Engenharia de prompts, refinamento de instruções de sistema e estruturação da comparação entre a versão Zero-Shot Básica e a versão Especializada em Compliance.

---

## 2. Metodologia de Uso de IA

- **Separação Rígida entre Dados e Inferência**: O modelo de linguagem não calcula métricas matemáticas, somas ou agregações; os cálculos de volume, contagem de operações e flags determinísticas são executados exclusivamente em Pandas e injetados no contexto como fatos auditáveis.
- **Validação de Saída Estruturada**: Utilização de Pydantic (`ParecerPLD`) e tratamento resiliente de formato com regex para garantir que respostas malformadas não interrompam o fluxo.
- **Transparência e Métricas Reais**: Inclusão de metadados de proveniência (`fonte`), medição de latência real em milissegundos e contagem de tokens consumidos via `usage_metadata`.
