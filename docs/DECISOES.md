# Decisões Técnicas, Trade-offs e Planejamento

Este documento consolida as decisões arquiteturais tomadas no Nível 1, as limitações identificadas e o planejamento detalhado para o Nível 2 e Nível 3.

---

## 1. Decisões e Trade-offs: Nível 1

- **Deduplicação por ID com Auditoria de Conteúdo**:
  Em vez de deduplicar cegamente por linha inteira ou descartar registros silenciosamente por ID, o sistema inspeciona se há divergências de conteúdo entre IDs repetidos (alerta para revisão manual) e remove apenas duplicações 100% idênticas (`OP-0007`), mantendo registro na trilha de auditoria.

- **Separação Rígida entre Pandas e LLM**:
  Evitou-se delegar cálculos matemáticos (somas, contagens e medianas) ao modelo de linguagem. O motor em Pandas processa os dados, aplica as Regras 1 e 2 exigidas pelo desafio e a sinalização adicional de qualidade de dados de forma determinística, injetando os fatos consolidados no contexto do LLM apenas para a redação do parecer técnico estruturado.

- **Tratamento de Falhas Técnicas de IA (Erro de Validação vs. Risco Alto)**:
  Em caso de falha de parsing ou resposta fora de conformidade de schema pelo modelo de linguagem, o sistema atribui `status_parecer: "erro_validacao"` e define o `nivel_risco: "indeterminado"`, preservando o texto bruto da resposta para auditoria humana. Evitou-se categorizar falhas de infraestrutura/parsing como "risco alto" para não inflacionar indevidamente a volumetria de alertas e relatórios regulatórios.

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
## 5. Nível 3 - Trilha B (Servidor MCP local)

O Nível 3 não foi implementado. Esta seção descreve o planejamento: por que a trilha B foi escolhida, a arquitetura prevista, as ferramentas e como o funcionamento seria validado.

### 5.1. Justificativa da escolha da trilha

Entre as três trilhas, a B (servidor MCP) foi escolhida porque reaproveita diretamente o trabalho já planejado no Nível 2: as três ferramentas (`historico_cliente`, `operacoes_do_dia`, `perfil_canal`) já seriam implementadas como funções Python puras, e expô-las via MCP é uma mudança de camada de transporte, não uma reescrita de lógica. As trilhas A (multiagente) e C (interface conversacional) exigiriam construir componentes novos do zero (orquestração de estado entre agentes, ou uma camada de UI), com risco maior de não terminar dentro do prazo. A trilha B também tem valor prático mais direto para o time de PLD/AML: um servidor MCP permite que qualquer cliente compatível (Claude Desktop, outro agente interno) consulte a base de operações sem acoplamento direto ao código Python, o que se aproxima mais de como essa ferramenta seria de fato consumida em produção.

### 5.2. Arquitetura

- Um processo `nivel_3/mcp_server.py`, usando o SDK oficial do Model Context Protocol para Python, expondo via **stdio** as três ferramentas do Nível 2 como *tools* MCP, cada uma com schema de entrada validado (Pydantic, reaproveitando o padrão já usado no `ParecerPLD`).
- O `agente.py` do Nível 2 deixaria de importar `tools.py` diretamente e passaria a se conectar ao servidor como um cliente MCP, descobrindo as ferramentas dinamicamente via `list_tools` e chamando-as via `call_tool`, em vez de chamada de função Python direta.
- O servidor rodaria como processo filho, iniciado pelo próprio cliente MCP (padrão stdio do protocolo), sem necessidade de porta de rede exposta.

### 5.3. Ferramentas

- `mcp` (SDK Python oficial da Anthropic) para implementar o servidor.
- Reaproveitamento do `pandas` já usado no Nível 2 para a lógica interna de cada tool, sem duplicar código.
- Documentação de conexão em `docs/ARQUITETURA.md` (ou seção dedicada no README), explicando o comando exato para subir o servidor e como apontar um cliente MCP (Claude Desktop ou um cliente MCP de teste em Python) para ele.

### 5.4. Como seria validado

1. **Teste de descoberta de ferramentas**: subir o servidor isoladamente e confirmar, via um cliente MCP de teste, que as três ferramentas aparecem com o schema esperado (nomes de parâmetros, tipos).
2. **Paridade de resultado**: rodar a mesma consulta (ex: `historico_cliente("CLI-A-1")`) via import direto (Nível 2) e via chamada MCP, comparando se o resultado é idêntico, para garantir que a troca de camada de transporte não alterou o comportamento.
3. **Teste de integração ponta a ponta**: rodar o `agente.py` adaptado, sobre um subconjunto pequeno de clientes, e confirmar que o parecer final gerado é equivalente ao obtido no Nível 2 com chamada direta, validando que o agente consegue de fato orquestrar chamadas de ferramenta através do protocolo, não só localmente.
4. **Teste de falha controlada**: derrubar o servidor propositalmente durante uma chamada e confirmar que o agente trata o erro de conexão de forma explícita, em vez de falhar silenciosamente.
