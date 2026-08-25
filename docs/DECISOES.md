# Decisões Técnicas, Trade-offs e Planejamento

Este documento consolida as decisões arquiteturais tomadas no Nível 1, as limitações identificadas e o planejamento detalhado para o Nível 2 e Nível 3.

---

## 1. Decisões e Trade-offs: Nível 1

- **Deduplicação por ID com Auditoria de Conteúdo**:
  Em vez de deduplicar cegamente por linha inteira ou descartar registros silenciosamente por ID, o sistema inspeciona se há divergências de conteúdo entre IDs repetidos (alerta para revisão manual) e remove apenas duplicações 100% idênticas (`OP-0007`), mantendo registro na trilha de auditoria.

- **Separação Rígida entre Pandas e LLM**:
  Evitou-se delegar cálculos matemáticos (somas, contagens e medianas) ao modelo de linguagem. O motor em Pandas processa os dados, aplica as Regras 1, 2 e 3 de forma determinística e injeta os fatos consolidados no contexto do LLM apenas para a redação do parecer técnico estruturado.

---

## 2. Limitações Identificadas: Nível 1

- **Fracionamento Restrito ao Mesmo Dia**:
  A Regra 1 agrupa operações por cliente e data exata (`YYYY-MM-DD`). Fracionamentos intencionalmente distribuídos ao longo de dias consecutivos não são capturados pela regra diária pontual.

- **Correspondência Textual Exata de Contrapartes**:
  O código compara strings literais, não unificando automaticamente variações cadastrais ou erros tipográficos (ex: "Alfa Comercio LTDA" vs "Alfa Comércio Ltda.").

---

## 3. O que Eu Faria com Mais Tempo

- **Janela Deslizante (Rolling Window)**:
  Substituir o agrupamento diário fixo por soma móvel de 3 a 5 dias via `rolling()` no Pandas, validando contra bases sintéticas e perfis legítimos de alto volume (ex: folha de pagamento).

- **Fuzzy Matching de Contrapartes**:
  Integrar bibliotecas de similaridade de strings (`rapidfuzz` / Levenshtein) para agrupar entidades correlatas antes da aplicação das regras, com fila de revisão humana para casos limítrofes.

- **Enriquecimento Cadastral**:
  Incorporar dados de faturamento/renda declarada e CNAE para validação de compatibilidade patrimonial.

---

<a name="nivel_2"></a>
## 4. Decisões Técnicas e Planejamento: Nível 2

O Nível 2 não foi implementado. Abaixo está o planejamento estruturado das decisões, limitações previstas e plano de continuidade:

### 4.1. Trade-offs Planejados
- **Módulo Compartilhado vs. Reescrita**: Extração do tratamento de dados e das regras determinísticas para um módulo comum (`common/regras.py`), garantindo reuso testado entre os níveis e consistência analítica na base ampliada de 320 operações e 30 clientes (`dados_nivel_2.json`).
- **Chamada Seletiva de Ferramentas (Agente ReAct) vs. Consulta Incondicional**: O agente avaliará o contexto inicial do cliente para decidir quais ferramentas consultar sob demanda (`historico_cliente`, `operacoes_do_dia`, `perfil_canal`), otimizando o consumo de tokens e respeitando limites de requisição por minuto (RPM) das APIs.

### 4.2. Limitações Previstas
- **Rate Limits de Provedores Gratuitos**: O processamento em lote de múltiplos clientes com múltiplas ferramentas por cliente exige controle de taxa (rate limiting) e camada de cache para evitar bloqueios por throttling.
- **Subjetividade no Critério de Confronto**: A taxa de concordância depende da matriz de referência definida (ex: duas regras acionadas = risco alto); por isso, a justificativa qualitativa do modelo é mais relevante que a métrica isolada.

### 4.3. Plano de Implementação (Partes A a D)
- **Parte A (Regras em Escala)**: Execução das regras via Pandas sobre os 30 clientes, ranqueando os 10 clientes mais sinalizados (com volume total como critério de desempate) e validação de regressão com os casos do Nível 1.
- **Parte B (Ferramentas e Agente)**: Construção de `tools.py` com funções puras em Python e `agente.py` utilizando function calling nativo do provedor (Gemini/Groq), evitando o overhead desnecessário de frameworks pesados.
- **Parte C (Execução em Lote)**: Processamento dos 10 clientes selecionados com persistência em `outputs/lote.csv`, registrando parecer estruturado, latência real e tokens consumidos.
- **Parte D (Confronto Regra vs. Modelo)**: Implementação de `confronto.py` para calcular a taxa de concordância e documentar a análise qualitativa das divergências (identificando eventuais falsos positivos das regras determinísticas).

---

<a name="nivel_3"></a>
## 5. Planejamento: Nível 3 (Trilha B - MCP)
- Exposição da esteira de regras e do motor de inferência via servidor Model Context Protocol (MCP), permitindo a conexão padronizada com assistentes e clientes de triagem de compliance.
