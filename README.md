# Desafio de Prevenção à Lavagem de Dinheiro (PLD/AML)

## Resumo do Projeto
Este projeto implementa a esteira de auditoria de dados transacionais, aplicação de regras determinísticas de monitoramento e emissão de pareceres técnicos de triagem com IA Generativa sobre a base de dados legados.

A solução contempla:
1. **Auditoria e Limpeza de Dados**: Deduplicação estrita com verificação de divergências de conteúdo, tratamento de operações sem data e normalização cambial (USD para BRL).
2. **Estatísticas e Volumetria**: Agregações de volume financeiro, contagem de transações, ticket médio e mediana por cliente e por canal.
3. **Regras Determinísticas de PLD/AML**:
   - Regra 1: Detecção de fracionamento de valores (smurfing/structuring).
   - Regra 2: Detecção de valor atípico (> 5x a mediana histórica do cliente).
   - Regra 3: Sinalização de integridade de dados e canal vulnerável (depósito em espécie / data nula).
4. **Validação das Regras**: Confronto explícito entre casos capturados e casos limítrofes não capturados.
5. **Pareceres com LLM e Saída Estruturada**: Integração via API real com schema Pydantic (`ParecerPLD`), relatório de proveniência (`fonte`), medição de latência e consumo de tokens.
6. **Comparação de Prompts**: Comparação empírica entre a versão Zero-Shot Básica e a versão Especializada em Compliance.

## O que foi entregue

- Nível 1 - tratamento, regras, análise com LLM: completo
- Nível 2 - escala, ferramentas, agente, lote, confronto: não implementado; plano em docs/DECISOES.md#nivel_2
- Nível 3: não implementado; plano em docs/DECISOES.md#nivel_3

## Como Rodar

### 1. Pré-requisitos
- Python 3.10 ou superior
- Chave de API do Google Gemini (`GEMINI_API_KEY`)

### 2. Instalação das Dependências
```bash
pip install -r requirements.txt
```

### 3. Configuração do Ambiente (.env)
Copie o template de variáveis de ambiente:
```bash
cp .env.example .env
```
No Windows PowerShell:
```powershell
Copy-Item .env.example .env
```
Abra o arquivo `.env` e configure sua chave de API:
```env
GEMINI_API_KEY=sua_chave_gemini_aqui
GOOGLE_API_KEY=sua_chave_gemini_aqui
LLM_PROVIDER=gemini
```

### 4. Execução do Projeto

- **Execução via Script Python**:
  Executa a esteira ponta a ponta, imprime as validações e salva todos os artefatos gerados em `outputs/`:
  ```bash
  python nivel_1/analise_dados.py
  ```

- **Execução via Jupyter Notebook**:
  Abra e execute todas as células de [nivel_1/nivel_1.ipynb](nivel_1/nivel_1.ipynb) para visualizar o fluxo interativo, gráficos de volumetria e saídas dos modelos.

## Estrutura do Projeto

```text
├── dados/
│   ├── dados_nivel_1.json
│   └── dados_nivel_2.json
├── docs/
│   ├── DECISOES.md
│   └── USO_DE_IA.md
├── nivel_1/
│   ├── analise_dados.py
│   └── nivel_1.ipynb
├── nivel_2/
│   ├── agente.py
│   ├── confronto.py
│   └── tools.py
├── outputs/
│   ├── auditoria_duplicidades.json
│   ├── base_tratada_nivel_1.csv
│   ├── comparacao_prompts_cli_a1.csv
│   ├── parecer_cli_a1.json
│   ├── volume_por_canal.csv
│   └── volume_por_cliente.csv
├── .env.example
├── .gitignore
├── ENTREGA.yaml
├── README.md
└── requirements.txt
```
