# 🤖 Agentic SQL Core: Structural Query Engine (LangGraph & SQLite)

An intelligent data pipeline and Agentic SQL application that transforms flat datasets into normalized structures and provides a natural language interface for querying and visualizing business data. This repository demonstrates how to architect a deterministic, robust multi-agent system using LangGraph for strict schema adherence and reliable SQL generation.

## 🏗️ The "Why": Architectural Design Choices

When building Text-to-SQL systems, hallucinated column names and dangerous DML operations (like `DROP TABLE`) are the greatest risks. I explicitly chose **LangGraph** for this core structural engine because it provides **fine-grained, stateful control over the agentic flow**. 

Unlike standard conversational agents that decide their own path, LangGraph enforces a strict, deterministic DAG (Directed Acyclic Graph) workflow:
- **State Management**: Every node passes a typed `GraphState` containing the query, generated code, execution status, and AST-parsed security flags.
- **Explicit Routing**: A Supervisor agent statically routes simple lookup queries away from the heavy analytical pipeline, saving LLM tokens and reducing latency.
- **Fail-Safe Pipelines**: If the Code Generator hallucinates a column, the execution node catches the SQL error and can pass the exact traceback back into the graph state for an automated retry loop.

### Comparative Approach: LangGraph vs. LlamaIndex
*(See my complementary repository: **[Agentic SQL Advanced: Semantic RAG & Review Engine](https://github.com/2001anshkaushik/Agentic_SQL_Advanced_LlamaIndex)**)*

While LangGraph excels at strict, deterministic pipelines—making it perfect for structural SQL generation where precision is critical—it requires significant boilerplate and explicit state management. In contrast, **LlamaIndex** (used in my Advanced RAG repository) excels at rapid tool-chaining and semantic vector search, making it ideal for unstructured data like customer reviews. 

Here, **LangGraph ensures 100% deterministic routing for structural tabular data**, preventing the agent from ever deviating from the explicitly defined analytical pipeline.

## 🗄️ Database Strategy

For this project, I selected **SQLite** as the database engine. This ensures the project is entirely self-contained and portable. The `robot_vacuum.db` file is included in this repository so anyone pulling the project can immediately run the application without needing a local database server setup!

## 🚀 How to Install & Run

**Important**: All commands should be run from the `Agentic_SQL_Core_LangGraph/` root directory unless otherwise specified.

### Step 1: Install Dependencies

Using `uv` (recommended):

```bash
uv pip install --system -r src/requirements.txt
```

Alternatively, using standard `pip`:

```bash
pip install -r src/requirements.txt
```

### Step 2: Run the ETL Pipeline (Optional)

**Note**: The repository includes a pre-populated `robot_vacuum.db`. Running the ETL is only necessary if you want to rebuild the database from the source CSV.

```bash
cd src
python -m etl.db_loader
```

This command will:
- Load the CSV data from `data/RobotVacuumDepot_MasterData.csv` using Polars
- Normalize the flat data into 3NF entities
- Create a SQLite database (`robot_vacuum.db`) with Postgres-compatible DDL

### Step 3: Configure Environment

Create a `.env` file in the `src/` directory:

```env
OPENAI_API_KEY=your_openai_api_key_here
```

### Step 4: Launch the Streamlit Application

```bash
cd src
streamlit run app.py
```

The application will open in your default web browser at `http://localhost:8501`.

## 📂 Project Structure

```
Agentic_SQL_Core_LangGraph/
├── doc/
│   ├── README.md (this file)
│   └── screenshots/ (screenshots/demo videos)
├── src/
│   ├── .env (environment variables - not in git)
│   ├── requirements.txt (Python dependencies)
│   ├── app.py (Streamlit UI)
│   ├── robot_vacuum.db (SQLite database - included for easy setup)
│   ├── data/
│   │   └── RobotVacuumDepot_MasterData.csv (source data)
│   ├── etl/
│   │   ├── loader.py, transformer.py, db_loader.py
│   ├── agents/
│   │   ├── state.py, supervisor.py, specialized.py, post_processor.py
│   │   ├── ast_transformer.py, llm_utils.py, security.py
│   │   ├── tools.py, graph.py
│   └── ui/
│       ├── components.py, styles.py, utils.py
```

## 🔄 Application Flow

### Runtime Query Processing Flow

1. **User Query**: Natural language processed by Streamlit UI.
2. **Agent A0 (Supervisor)**: Analyzes complexity. Routes Simple vs Complex.
3. **Agent A1 (Router)**: Maps semantic intent (e.g. `REVENUE_TRENDS`).
4. **Agent A2 (Code Generator)**: Generates SQL or Python code injected with schema contexts.
5. **Agent A3 (Post-Processor)**: AST transformations, security checks.
6. **Agent A4 (Executor)**: Executes SQL/Python, formats charts + tables.

### ETL Pipeline Flow (One-Time Setup)

```
┌─────────────────────────────┐
│  RobotVacuumDepot_          │
│  MasterData.csv             │
│  (Raw CSV Data)             │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  Loader (loader.py)         │
│  • Polars CSV reading       │
│  • Data cleaning            │
│  • Date format parsing      │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  Transformer                │
│  (transformer.py)           │
│  • 3NF normalization        │
│  • Entity creation          │
│  • Derived fields calc      │
│    (TotalAmount,            │
│     DeliveryStatus)         │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  Database Loader            │
│  (db_loader.py)             │
│  • SQLite DB creation       │
│  • Schema creation          │
│  • Data insertion           │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  robot_vacuum.db            │
│  (Normalized 3NF Database)  │
└─────────────────────────────┘
```

### Runtime Query Processing Flow

```
┌─────────────────────────────┐
│  User Query                 │
│  (Natural Language)         │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  Streamlit UI (app.py)      │
│  • Initializes GraphState   │
│  • Invokes LangGraph        │
└──────────────┬──────────────┘
               │
               ▼
┌─────────────────────────────┐
│  Agent A0: Supervisor       │
│  (supervisor.py)            │
│  • Analyzes complexity      │
│  • Routes: Simple/Complex   │
└──────────────┬──────────────┘
               │
       ┌───────┴───────┐
       │               │
   Simple          Complex
       │               │
       ▼               ▼
┌──────────┐   ┌─────────────────────┐
│ Direct   │   │ Agent A1: Router    │
│ SQL      │   │ (specialized.py)    │
│ Gen &    │   │ • Maps to Intent    │
│ Execute  │   │ • Semantic routing  │
└────┬─────┘   └──────────┬──────────┘
     │                    │
     │                    ▼
     │           ┌─────────────────────┐
     │           │ Agent A2:           │
     │           │ Code Generator      │
     │           │ (specialized.py)    │
     │           │ • Generates SQL/    │
     │           │   Python code       │
     │           │ • Schema injection  │
     └───────────┼─────────────────────┘
                 │
                 ▼
     ┌─────────────────────┐
     │ Agent A3:           │
     │ Post-Processor      │
     │ (post_processor.py) │
     │ • AST transforms    │
     │ • Security checks   │
     │ • Code fixes        │
     └──────────┬──────────┘
                │
                ▼
     ┌─────────────────────┐
     │ Agent A4: Executor  │
     │ (specialized.py)    │
     │ • Executes SQL/     │
     │   Python code       │
     │ • Generates charts  │
     │ • Formats results   │
     └──────────┬──────────┘
                │
                ▼
     ┌─────────────────────┐
     │ Results             │
     │ • Tables/DataFrames │
     │ • Plotly charts     │
     │ • SQL metadata      │
     └──────────┬──────────┘
                │
                ▼
     ┌─────────────────────┐
     │ Streamlit UI        │
     │ • Renders visuals   │
     │ • Shows tables      │
     │ • "View Logic"      │
     │   expander          │
     └─────────────────────┘
```

## 🧠 Logic and Features

My ETL pipeline transforms raw CSV data into a normalized 3NF database using Polars for high-performance data processing. The agent architecture includes:

1. **No Hard-Coding**: All SQL/Python code is generated dynamically based on schema introspection, intent detection, and user queries. 
2. **Schema Injection**: The code generator receives a complete schema description at runtime, ensuring it never hallucinates column names or table structures.
3. **AST-Based Code Transformation**: Instead of fragile regex-based fixes, I use Python's AST module to reliably transform generated code, ensuring correct date formatting and handling edge cases.
4. **Security Validation**: All SQL queries are validated to prevent dangerous operations (DROP, DELETE, TRUNCATE, etc.). Only SELECT queries are allowed.

### Python REPL & Technical Deep-Dive
To transition from mere data retrieval (SQL) to analytical insights (Charts), the agent writes and executes Python code dynamically.
1. **Context Hydration**: The agent generates a SQL query, executes it, and loads the result into a Pandas DataFrame (`df`).
2. **Code Generation**: The LLM writes a Python script utilizing `plotly.express` assuming `df` is already in memory.
3. **AST Validation**: Before the string is passed to `exec()`, Python's `.ast` module parses the code tree to ensure no malicious modules are imported.
4. **Execution**: The code maps the DataFrame to a `plotly.graph_objects.Figure` which Streamlit renders inline.

### UI Features
**"View Logic" Expander**: I implemented a traceability feature that exposes the underlying SQL and data used to generate results. It helps developers understand exactly how the natural language query was translated into SQL.

## ✅ Types of Supported Queries

- **Simple Queries (Direct SQL)**: "How many orders are there?"
- **Analytical Queries (Charts)**: "Show me monthly revenue trends" → Line chart
- **Distributions**: "What is the distribution of delivery statuses?" → Pie chart
- **Data Exploration (Tables)**: "Which warehouses have products below restock threshold?"

## Verification
To verify the system works correctly, test the fundamental queries in the Streamlit UI. The "View Logic" expander allows you to inspect the generated SQL for traceability.

**Author**: Ansh Kaushik
