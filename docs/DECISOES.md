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

<a name="nivel_3"></a><a name="mcp"></a>
## 5. Decisões Técnicas e Planejamento: Nível 3 (Trilha B - MCP)

O Nível 3 (Trilha B: Servidor Model Context Protocol) não foi implementado. Abaixo está o planejamento detalhado da arquitetura, ferramentas expostas, trade-offs e metodologia de teste.

### 5.1. Contexto e Objetivos da Trilha B
Implementar um servidor MCP padronizado em Python (`nivel_3/mcp_server.py`) para expor as ferramentas determinísticas e os dados consolidados de PLD/AML para clientes MCP (como Claude Desktop, Cursor ou agentes de triagem bancária), permitindo que qualquer assistente de compliance consulte regras, métricas e dossiês de forma desacoplada e segura.

### 5.2. Trade-offs Planejados
- **FastMCP vs. Low-Level Protocol**: Utilização do `FastMCP` do SDK oficial da Anthropic/ModelContextProtocol para Python. O FastMCP gera schemas JSON de ferramentas e recursos automaticamente a partir de type hints e docstrings do Python, reduzindo código boilerplate e minimizando risco de inconsistências de schema.
- **Transporte stdio vs. SSE (Server-Sent Events)**: Implementação inicial sobre transporte padrão `stdio` (focado em execução local e integração direta com o Claude Desktop), mantendo a arquitetura das funções isolada para futura transição para transporte `SSE/HTTP` em caso de microsserviço corporativo.
- **Servidor Desacoplado do Provedor de LLM**: O servidor MCP atua estritamente como provedor de contexto e ferramentas analíticas (não realiza chamadas diretas a LLMs); a inteligência e o raciocínio ficam sob responsabilidade do cliente MCP conectado.

### 5.3. Ferramentas e Recursos (Tools & Resources)
O servidor exporia as seguintes interfaces:

1. **Ferramentas (Tools)**:
   - `consultar_historico_cliente(cliente_id: str)`: Retorna contagem de operações, volume total em BRL, mediana, tickets extremos e datas de transação.
   - `verificar_regras_pld(cliente_id: str)`: Executa as Regras 1 (fracionamento), 2 (outlier) e 3 (integridade/espécie), devolvendo as flags acionadas e justificativas determinísticas.
   - `extrair_dossie_consolidado(cliente_id: str)`: Monta o payload estruturado completo do cliente (operações, contrapartes e canais) para suporte à redação de pareceres técnicos.

2. **Recursos (Resources)**:
   - `pld://normas/bacen_3978`: Recurso estático com diretrizes da Circular BACEN nº 3.978/2020 e parâmetros de comunicação ao COAF.
   - `pld://regras/catalogo`: Catálogo formal com a definição matemática e regras de negócio de cada flag de monitoramento.

### 5.4. Limitações e Governança de Dados
- **Privacidade e Sigilo Bancário (LC 105/2001 e LGPD)**: O servidor deve operar em modo somente-leitura e mascarar dados sensíveis de contrapartes ou identificadores pessoais quando exportados para clientes externos.
- **Arquitetura Stateless**: Para garantir escalabilidade e concorrência, o servidor mantém estado nulo, consultando bases em memória (DataFrames indexados) ou banco relacional sem bloqueios de escrita.

### 5.5. Plano de Implementação e Validação
- **Arquivo Principal**: `nivel_3/mcp_server.py`.
- **Configuração de Integração**: Arquivo de exemplo `claude_desktop_config.json` apontando para o interpretador Python do projeto e o script do servidor.
- **Validação Prática**:
  - Teste de conformidade de protocolo utilizando o `mcp-inspector` (`npx @modelcontextprotocol/inspector python nivel_3/mcp_server.py`).
  - Execução de casos de teste sintéticos (invocando `consultar_historico_cliente` e `verificar_regras_pld` para `CLI-A-1` a `CLI-A-5`) para garantir que os retornos batem exatamente com as saídas do Nível 1.
