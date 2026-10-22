# Pipeline de Conexão Judicial: DataJud CNJ, DJEN, Decodificação CMAP e Streaming de Terabytes

> **Especificação Arquitetural e Biblioteca de Conexão Judicial de Alto Desempenho**  
> *Padrão de Conformidade: ISO/IEC 27037:2012, NIST SP 800-86 e Práticas de Segurança Zero-Trust.*

---

## 1. Visão Geral e Propósito de Engenharia

Este repositório fornece uma biblioteca de engenharia agnóstica e de alto rendimento para conectar sistemas jurídicos e analíticos aos tribunais brasileiros (**DataJud CNJ**, **DJEN / Comunica PJe** e instâncias **PJe / e-SAJ / Projudi / Eproc**).

O pipeline foi projetado para permitir que qualquer advogado constituído autentique nos tribunais, consulte e extraia centenas de terabytes de documentos processuais aos quais possui acesso legítimo, delegando a análise de forma estritamente controlada para o **Assistente Técnico (AT)** contratado pela defesa, entregando os fluxos decodificados e higienizados diretamente para clusters de processamento de Inteligência Artificial.

---

## 2. Princípios Arquiteturais Centrais

### 1. Ingestão em Streaming de Terabytes sem Esgotamento de Memória
A leitura de acervos massivos contendo dezenas de milhares de páginas em PDF é inviável por carregamento monolítico em memória RAM.
- O pipeline processa o fluxo de dados em **blocos atômicos de 64 KB**.
- Realiza o cravamento concorrente de assinaturas criptográficas duplas (**SHA-256** e **SHA-512**) em tempo real à medida que os dados trafegam pela rede.
- Permite que o supercomputador/cluster de IA processe o acervo em trânsito com consumo estável e previsível de memória.

### 2. Motor CMAP Nativo C/C++ (MuPDF Core) e Resolução Tipográfica
Documentos PDF emitidos por sistemas de processo eletrônico frequentemente utilizam subconjuntos de fontes proprietárias sem tabelas `/ToUnicode` aderentes ao padrão.
- **Núcleo Compilado em C/C++ (MuPDF Core via PyMuPDF):** Processa entre 300 e 800 páginas por segundo por núcleo de processador, permitindo que processadores modernos de última geração decodifiquem dezenas de milhares de páginas por minuto.
- **Resolução de Ligaduras Tipográficas:** Converte sequências fundidas (`\ufb00` $\rightarrow$ `ff`, `\ufb01` $\rightarrow$ `fi`, `\ufb02` $\rightarrow$ `fl`, `\ufb03` $\rightarrow$ `ffi`, `\ufb04` $\rightarrow$ `ffl`, etc.) em texto canônico UTF-8.
- **Normalização Canônica NFKC:** Elimina anomalias visuais e glifos especiais.
- **Recomposição de Hifenizações de Fim de Linha:** Detecta e une quebras tipográficas de diagramação (ex: `"mani-\nfestação"` $\rightarrow$ `"manifestação"`).
- Garante fidelidade textual absoluta para indexação e análise por clusters de Inteligência Artificial com 100 GB+ de RAM.

### 3. Isolamento Criptográfico Zero-Trust (Advogado vs. Assistente Técnico)
- O **Assistente Técnico (AT)** contratado **NUNCA** recebe a senha, o certificado digital A1 (.pfx) nem o cookie de sessão do advogado.
- O advogado se autentica institucionalmente em sessão mantida exclusivamente em **memória volátil (Zero-Storage em disco)**.
- Para cada processo solicitado, o sistema gera uma autorização granular pontual (`CaseGrant`) e emite um **Token Efêmero HMAC-SHA256**.
- O AT acessa exclusivamente o acervo documental parametrizado para o caso, dispondo de mecanismo de **revogação instantânea em tempo real $O(1)$**.

### 4. Proteção de Rede Anti-Bloqueio (Rate Pacer + Circuit Breaker)
> **O verdadeiro gargalo nunca é o seu servidor, é o firewall do tribunal.**  
> Se o seu cluster disparar 1.000 requisições por segundo contra o CNJ ou TJ, o tribunal acionará o WAF (Cloudflare, F5 BIG-IP) e banirá o seu IP por HTTP 429 (*Too Many Requests*).
> 
> O `PacerAdaptativoVazao` controla o fluxo milissegundo a milissegundo com janela deslizante de latência P95 e disjuntor de proteção. Ele extrai a taxa máxima que o tribunal tolera entregar sem derrubar a conexão.

- **Janela Deslizante P95:** Medição contínua da latência dos endpoints dos tribunais em tempo real.
- **Semáforo Assíncrono:** Garante concorrência segura (2 a 4 conexões por IP de saída).
- **Disjuntor de Circuito (Circuit Breaker):** Transita para `OPEN` em caso de erros repetidos do tribunal, evitando o bloqueio definitivo do IP da sua infraestrutura.

---

## 3. Estrutura do Projeto

```
.
├── core/
│   ├── __init__.py
│   ├── auth_advogado_tribunal.py         # Sessão volátil do advogado (Zero-Storage A1 / SSO)
│   ├── conector_datajud.py               # Cliente ElasticSearch DSL para DataJud CNJ
│   ├── conector_djen.py                  # Cliente da API pública do DJEN (Comunica PJe)
│   ├── conectores_datajud_djen.py        # Rate Pacer adaptativo, medição P95 e Circuit Breaker
│   ├── custodia_streaming_terabytes.py   # Streaming em chunks de 64 KB com duplo hash (SHA-256/512)
│   ├── decodificador_cmap.py             # Motor CMAP ToUnicode, normalizador NFKC e ligaduras
│   ├── delegacao_assistente_tecnico.py   # Concessão granular ao AT, tokens HMAC e revogação O(1)
│   └── livro_razao_auditoria.py          # Livro-razão imutável de eventos e trilha de auditoria
├── tests/
│   ├── __init__.py
│   └── test_pipeline_integracao.py       # Bateria de testes de integração automatizados
├── .env.example                          # Modelo de configuração de variáveis de ambiente
├── .gitignore                            # Proteção contra commit acidental de chaves ou credenciais
├── pipeline_demonstracao_completa.py     # Execução ponta a ponta demonstrando todos os módulos
├── README.md                             # Documentação técnica e arquitetural
└── requirements.txt                      # Dependências mínimas de execução
```

---

## 4. Guia de Execução e Homologação

### 1. Clonar e Instalar Dependências
```bash
git clone <URL_DO_REPOSITORIO>
cd pipeline_api
python -m venv .venv
source .venv/bin/activate  # No Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### 2. Executar a Demonstração Completa
```bash
python pipeline_demonstracao_completa.py
```

### 3. Executar os Testes Automatizados
```bash
pytest tests/ -v
```

---

## 5. Diretrizes de Integração no Novo Ambiente

1. **Configuração de Chaves:** As credenciais e endpoints devem ser injetados exclusivamente via variáveis de ambiente (`DATAJUD_API_KEY`, etc.). O conector DataJud possui fallback embutido para a API pública do CNJ caso nenhuma chave seja configurada.
2. **Buffer de Tokens:** Em arquiteturas distribuídas, armazene as autorizações (`CaseGrant`) em banco relacional e grave a lista de revogações em cache em memória (ex: Redis Set) com TTL idêntico à validade do token HMAC emitido.
3. **Pacing com Tribunais:** Mantenha a concorrência assíncrona entre 2 e 4 requisições simultâneas por IP público para evitar engatilhamento de regras de proteção contra automação dos tribunais.
