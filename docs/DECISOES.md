# Decisões Técnicas, Trade-offs e Limitações

Este documento consolida as decisões arquiteturais, trade-offs técnicos, limitações identificadas e o planejamento de evolução para a esteira de Prevenção à Lavagem de Dinheiro (PLD/AML).

---

## 1. Trade-offs

- **Deduplicação por ID com Alerta de Divergência de Conteúdo**:
  Poderia ter sido realizada a deduplicação comparando a linha inteira, mas isso esconderia um cenário de alto risco em auditoria: dois registros com o mesmo ID e valores ou atributos divergentes. Optou-se por inspecionar os IDs repetidos, isolar inconsistências para revisão manual e deduplicar automaticamente apenas os registros comprovadamente 100% idênticos (`OP-0007`), mantendo a rastreabilidade na trilha de auditoria.

- **Separação Rígida entre Cálculos Determinísticos e Redação com LLM**:
  Evitou-se delegar cálculos matemáticos de somatórios ou medianas ao LLM (suscetíveis a alucinações). Todas as agregações e enquadramentos de regras (Regras 1, 2 e 3) são executados via Pandas e repassados como fatos auditáveis ao modelo para a redação do parecer técnico.

---

## 2. Limitações Identificadas

- **Detecção de Fracionamento Restrita ao Mesmo Dia**:
  A regra determinística atual agrupa transações por `cliente_id` e data exata (`YYYY-MM-DD`). Caso um agente malicioso distribua as operações em dias consecutivos (ex: 2 ou 3 dias subsequentes) para burlar o teto diário de R$ 50.000,00, o agrupamento pontual não sinalizará o fracionamento temporalmente diluído.

- **Comparação Textual Exata de Contrapartes (Sem Fuzzy Matching)**:
  O pipeline atual trata o nome das contrapartes como string literal. Variações como "Alfa Comercio LTDA", "Alfa Comércio Ltda." ou erros de digitação não são unificados automaticamente. Em cenários reais, isso prejudica a identificação de redes de favorecidos comuns que recebem recursos de múltiplos clientes.

---

## 3. O que Eu Faria com Mais Tempo

- **Fracionamento em Janela Deslizante (Rolling Window)**:
  Substituir o agrupamento diário fixo por uma janela deslizante temporal (soma móvel de 3 a 5 dias por cliente) utilizando `rolling()` no Pandas.
  *Validação*: Criação de base de teste sintética com operações fracionadas distribuídas em 3 dias para confirmar a captura da regra, além de teste com perfis legítimos de alto volume (ex: folha de pagamento) para calibrar a taxa de falsos positivos.

- **Matching Fuzzy e Normalização de Contrapartes**:
  Implementar biblioteca de similaridade de strings (como `rapidfuzz` ou distância de Levenshtein) para agrupar entidades com pequenas variações antes da execução das regras, com fila de revisão humana para casos limítrofes.
  *Validação*: Criação de conjunto de dados rotulado com variações conhecidas para medir métricas de precisão e revocação do agrupamento de entidades.

- **Enriquecimento Cadastral Automatizado**:
  Inclusão de renda/faturamento declarado e atividade econômica do cliente no payload de triagem para avaliar a compatibilidade patrimonial do volume transacionado.

---

<a name="nivel_2"></a>
## 4. Planejamento para o Nível 2 (Agente ReAct e Escala)
- Implementação de ferramentas especializadas em `nivel_2/tools.py` para consulta de regras, histórico e enriquecimento cadastral.
- Construção de agente autônomo em `nivel_2/agente.py` para processamento de filas e lotes de clientes com geração de saída em `outputs/lote.csv`.

<a name="nivel_3"></a>
## 5. Planejamento para o Nível 3 (Trilha B - MCP)
- Exposição do motor determinístico e do avaliador de risco como servidor Model Context Protocol (MCP) para integração com assistentes de triagem e ferramentas externas de compliance.
