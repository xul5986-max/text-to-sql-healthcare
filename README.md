# HealthSQL-Agent：基于大语言模型的 Text-to-SQL 智能查询系统

> HealthSQL-Agent: A Schema-Aware Large Language Model based Text-to-SQL System for Healthcare Database Querying

## 1. 项目架构与设计思路

### 1.1 项目背景与目标

Text-to-SQL 是大语言模型在结构化数据访问中的重要应用，目标是把用户输入的自然语言问题自动转换为可在关系型数据库中执行的标准 SQL，并返回结构化结果。医疗 HIS（Hospital Information System，医院信息系统）数据库具有表结构复杂、查询语义多样、对准确性与安全性要求高等特点。本项目 HealthSQL-Agent 以 HIS 数据库为核心场景，构建了一个完整的端到端 Text-to-SQL 系统，强调 Schema 感知、多表查询、SQL 校验与错误修正、结果总结与性能分析。

### 1.2 总体架构

HealthSQL-Agent 自顶向下划分为四个层次：用户交互层、业务处理层、模型层、数据层。

![图片描述](./docs/images/架构图.png)

- **用户交互层**：提供 Web 界面（`frontend/templates/index.html`）与 REST API（`backend/app.py`）。用户可在 Web 页面输入自然语言问题，也可通过 curl/Postman 调用 `/api/query`、`/api/convert`、`/api/execute`、`/api/schema`、`/api/tables`、`/api/validate` 等接口。
- **业务处理层**：核心模块包括 `backend/text_to_sql.py`、`backend/qwen_llm.py`、`backend/schema_linking.py`、`backend/sql_validator.py`、`backend/sql_summarizer.py`、`backend/query_optimizer.py`、`backend/query_cache.py`、`backend/conversation_manager.py`。完成 Schema 理解、Prompt 构建、SQL 生成、SQL 校验、SQL 执行、结果总结、性能分析与缓存。
- **模型层**：接入大语言模型，默认 `Qwen3-Coder-Plus`（通过 DashScope 兼容 OpenAI 接口调用），并预留 `HuggingFace` 接口（`single` 模式）与规则兜底（`rule` 模式）。`backend/qwen_llm.py` 封装 `QwenDashScopeLLM` 和 `Qwen3CoderConverter`；`backend/llm_integration.py` 封装 `EnhancedTextToSQLConverter` 支持 HuggingFace/Flan-T5-small；`backend/text_to_sql.py` 提供 `TextToSQLConverter` 规则匹配。
- **数据层**：默认 SQLite，数据库文件 `database/healthcare.db`，Schema 由 `database/schema.sql` 定义，样本数据由 `database/generate_data.py` 生成。`DatabaseAdapter` 抽象类支持扩展 PostgreSQL、MySQL。

完整数据流如下：

![图片描述](./docs/images/数据流程.jpg)

### 1.3 数据库设计

#### 1.3.1 领域选择

医疗 HIS 数据库包含科室、患者、医生、预约、病历、处方、处方药品明细等实体，表之间存在大量外键关系，查询类型涵盖单表查询、多表 JOIN、聚合统计、条件过滤、排序分页等。选择该领域能够充分展示 Text-to-SQL 在复杂关系型数据库查询中的能力，也贴近真实的医院信息系统场景。

#### 1.3.2 表结构

项目默认使用 SQLite，数据库文件 `database/healthcare.db` 包含 7 张表，8 个外键关系。Schema 定义在 `database/schema.sql` 中，核心表结构如下：

| 表名 | 关键字段 | 说明 |
|------|----------|------|
| `departments` | `department_id`, `department_name`, `description`, `location` | 科室信息 |
| `patients` | `patient_id`, `full_name`, `gender`, `date_of_birth`, `phone`, `blood_type` | 患者信息 |
| `doctors` | `doctor_id`, `full_name`, `specialty`, `department_id`, `salary`, `status` | 医生信息 |
| `appointments` | `appointment_id`, `patient_id`, `doctor_id`, `appointment_date`, `status`, `reason` | 预约记录 |
| `medical_records` | `record_id`, `appointment_id`, `patient_id`, `doctor_id`, `visit_date`, `diagnosis`, `symptoms` | 病历记录 |
| `prescriptions` | `prescription_id`, `record_id`, `patient_id`, `doctor_id`, `prescription_date`, `diagnosis` | 处方 |
| `prescription_items` | `item_id`, `prescription_id`, `medication_name`, `dosage`, `quantity`, `price` | 处方药品明细 |

表间关系通过外键约束：

- `doctors.department_id → departments.department_id`
- `appointments.patient_id → patients.patient_id`
- `appointments.doctor_id → doctors.doctor_id`
- `medical_records.appointment_id → appointments.appointment_id`
- `medical_records.patient_id → patients.patient_id`
- `medical_records.doctor_id → doctors.doctor_id`
- `prescriptions.record_id → medical_records.record_id`
- `prescription_items.prescription_id → prescriptions.prescription_id`

`database/schema.sql` 中部分 DDL 示例：

```sql
CREATE TABLE patients (
    patient_id INTEGER PRIMARY KEY AUTOINCREMENT,
    full_name TEXT NOT NULL,
    gender TEXT NOT NULL,
    date_of_birth TEXT NOT NULL,
    phone TEXT,
    email TEXT,
    address TEXT,
    blood_type TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE appointments (
    appointment_id INTEGER PRIMARY KEY AUTOINCREMENT,
    patient_id INTEGER NOT NULL,
    doctor_id INTEGER NOT NULL,
    appointment_date TEXT NOT NULL,
    status TEXT NOT NULL,
    reason TEXT,
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id)
);

CREATE TABLE medical_records (
    record_id INTEGER PRIMARY KEY AUTOINCREMENT,
    appointment_id INTEGER NOT NULL,
    patient_id INTEGER NOT NULL,
    doctor_id INTEGER NOT NULL,
    visit_date TEXT NOT NULL,
    diagnosis TEXT NOT NULL,
    symptoms TEXT,
    notes TEXT,
    FOREIGN KEY (appointment_id) REFERENCES appointments(appointment_id),
    FOREIGN KEY (patient_id) REFERENCES patients(patient_id),
    FOREIGN KEY (doctor_id) REFERENCES doctors(doctor_id)
);
```

#### 1.3.3 样本数据

`database/generate_data.py` 使用 `Faker` 生成英文医疗数据。默认配置生成：

- 科室 15 个
- 患者 1000 人
- 医生 200 人
- 预约 3000 条
- 病历 3000 条
- 处方 3000 条
- 处方药品明细 8000 条

数据生成脚本支持调整 `NUM_DEPARTMENTS`、`NUM_PATIENTS`、`NUM_DOCTORS`、`NUM_APPOINTMENTS` 等常量，支持随机种子，保证可复现。生成脚本首先执行 `database/schema.sql` 创建表，然后生成模拟数据，最后导出 `database/database.sql` 与 `database/healthcare.db`。

#### 1.3.4 Schema 读取与 LLM 注入

- `DatabaseManager.get_schema()` 通过 `PRAGMA table_info` 和 `PRAGMA foreign_key_list` 动态读取表、列、主键、外键。
- `get_schema_for_prompt()` 将 Schema 格式化为文本，例如：

```
Table: patients
Columns:
  - patient_id: INTEGER (PRIMARY KEY)
  - full_name: TEXT NOT NULL
  - gender: TEXT NOT NULL
  - date_of_birth: TEXT NOT NULL
  - phone: TEXT
  - email: TEXT
  - address: TEXT
  - blood_type: TEXT
  - created_at: TEXT DEFAULT CURRENT_TIMESTAMP

Foreign Keys:
  - None
```

该文本被拼接到 LLM 的 user prompt 中，确保模型知道可用字段和外键关系，降低幻觉表/列的概率。

### 1.4 Text-to-SQL 核心设计

#### 1.4.1 Schema 理解

系统实现了两种 Schema 理解方式：

1. **全局 Schema**：`db_manager.get_schema_for_prompt()` 获取全部表、列、主键、外键，直接注入 LLM prompt。适用于表数量不多的场景。
2. **筛选 Schema**：`backend/schema_linking.py` 中的 `SchemaLinking` 类根据用户问题做关键词匹配，对表名、列名打分排序，仅返回相关表和列。`get_filtered_schema_text(query)` 生成精简版 Schema 文本，用于压缩 prompt。

`SchemaLinking` 实现细节：

- **关键词索引**：`build_index` 方法遍历所有表名和列名，对表名和列名生成单复数形式，建立 `table_keywords` 与 `column_keywords` 字典。
- **表相关度打分**：`score_tables` 方法对查询中的每个词，匹配表名加 10 分，匹配关键词加 5 分，返回按得分排序的表列表。
- **列相关度打分**：`score_columns` 方法对查询中的每个词，匹配列名加 3 分，匹配关键词加 2 分。
- **保留相关表之间的外键关系**：`get_filtered_schema_text` 在返回相关表的同时，保留相关表之间的外键，确保模型能构造正确 JOIN。

示例：输入“查询糖尿病患者数量”，`SchemaLinking` 会识别 `patients` 与 `medical_records` 表相关，并保留 `medical_records.patient_id → patients.patient_id` 关系。

#### 1.4.2 Prompt 工程

系统使用 `backend/qwen_llm.py` 中的 `QwenDashScopeLLM` 与 Qwen3-Coder-Plus 交互。Prompt 由 System Prompt 与 User Prompt 两部分组成。

**System Prompt**：

```
You are a SQL expert. Convert natural language questions to SQL queries. Output only the SQL, no explanations.
```

**User Prompt 模板（由 `_build_prompt` 生成）**：

```
Convert the following natural language question to a SQL query based on the database schema.

Database Schema:
[自动注入的 Schema 文本]

Instructions:
- Generate only the SQL query, no explanations
- Use proper SQLite syntax
- Use only tables and columns that exist in the schema
- Use JOINs when querying multiple tables
- Do not use markdown code blocks
- Do not include any comments or explanations

Question: [用户输入]
SQL Query:
```

Prompt 设计要点：

- **Schema 注入**：模型明确知道可用表、列、主键、外键，避免虚构字段。
- **输出约束**：强制只输出 SQL，不带解释、markdown、注释。
- **JOIN 指令**：显式提醒跨表查询时使用 JOIN。
- **SQLite 语法指令**：确保生成与数据库兼容的 SQL。
- **Few-shot 示例**：在复杂场景下，可在 prompt 中插入“问题 → SQL”示例，提升模型对医疗查询的理解。

示例生成：

输入：`查询最近一年患有糖尿病的患者数量`

生成 SQL：

```sql
SELECT COUNT(*) FROM patients p
JOIN medical_records m ON p.patient_id = m.patient_id
WHERE m.diagnosis LIKE '%Diabetes%'
AND m.visit_date >= date('now', '-1 year');
```

#### 1.4.3 SQL 生成与解析

SQL 生成流程：

1. `/api/query` 接收 `POST` 请求，参数 `query` 与可选 `session_id`。
2. `app.py` 根据 `PIPELINE_MODE` 选择转换器，默认 `qwen`。
3. `conversation_manager.add_turn(session_id, user_query)` 维护会话历史。
4. 调用 `text_to_sql.convert(conversation_context)`，异步版本 `convert_async`。
5. `Qwen3CoderConverter` 通过 `QwenDashScopeLLM.generate_sql()` 调用 DashScope 接口。
6. DashScope 接口使用 OpenAI 兼容格式：

```python
response = self.client.chat.completions.create(
    model=self.model,
    messages=[
        {'role': 'system', 'content': self.system_prompt},
        {'role': 'user', 'content': prompt}
    ],
    temperature=0,
    max_tokens=500
)
```

7. 返回结果清洗：

```python
sql = response.choices[0].message.content.strip()
sql = re.sub(r'^```sql\s*\n?', '', sql)
sql = re.sub(r'\n?\s*```\s*$', '', sql)
sql = sql.strip()
```

清洗后的 SQL 交给 `SQLValidator` 校验。

#### 1.4.4 SQL 验证机制

`backend/sql_validator.py` 中的 `SQLValidator` 对生成 SQL 执行多层校验：

1. **基础检查**：非空、括号平衡、必须以 SQL 关键字开头。
2. **安全拦截**：`_check_security` 方法限制 SQL 只能以 `SELECT` 或 `EXPLAIN` 开头，禁止 `DROP`、`TRUNCATE`、`ALTER`、`CREATE`、`DELETE`、`UPDATE`、`INSERT`，并禁止多语句（通过 `;` 检测）。
3. **表存在性检查**：`get_tables` 方法使用正则提取 `FROM`、`JOIN`、`INTO`、`UPDATE`、`TABLE` 后的表名，与 `schema['tables']` 比对。
4. **列存在性检查**：`get_columns` 方法解析 `SELECT` 子句，排除函数和 `*`，检查列名是否在任意表中或是否在 `SELECT` 的聚合函数中。
5. **数据库级验证**：`validate` 方法调用 `EXPLAIN {sql}` 确认 SQL 可被 SQLite 解析。
6. **SQL 执行**：`SQLExecutor` 执行 SQL 时使用 `execute_query_with_timeout`，在独立线程中运行，并自动添加 `LIMIT` 限制返回行数。

`SQLExecutor` 职责：

- 调用 `SQLExecutor.execute(sql, timeout_seconds=..., max_rows=...)`。
- 自动在 SQL 末尾添加 `LIMIT max_rows`，防止一次返回过多数据。
- 使用 `execute_query_with_timeout` 在独立线程中执行，超时抛出异常。

#### 1.4.5 错误修正机制

当 LLM 生成 SQL 执行失败时，系统进入修正流程：

1. `SQLValidator` 捕获错误信息。
2. 调用 `QwenDashScopeLLM.fix_sql(error_sql, error_message)`。
3. `fix_sql` 构建修正 prompt，包含 Schema、原始 SQL、错误信息：

```
The following SQL query has an error:
[SQL]

Error: [错误信息]

Please fix the SQL query based on the database schema. Output only the corrected SQL, no explanations.

Database Schema:
[Schema]

Fixed SQL:
```

4. 模型返回修正后的 SQL，再次经过 `SQLValidator` 校验。
5. 校验通过后执行，否则返回错误。

### 1.5 模型层设计

#### 1.5.1 大模型选型

| 模式 | 文件 | 模型 | 说明 |
|------|------|------|------|
| `qwen` | `backend/qwen_llm.py` | Qwen3-Coder-Plus | 默认模式，通过 DashScope 兼容 OpenAI 接口调用，擅长代码与 SQL 生成 |
| `single` | `backend/llm_integration.py` | HuggingFace Flan-T5-small | 单模型模式，通过 HuggingFace Inference API 调用，适合轻量验证 |
| `rule` | `backend/text_to_sql.py` | 无 | 规则兜底模式，基于正则与关键词匹配，零模型依赖 |

`app.py` 初始化转换器逻辑：

```python
pipeline_mode = os.getenv('PIPELINE_MODE', 'qwen')  # Options: rule, single, qwen

if pipeline_mode == 'qwen':
    try:
        dashscope_key = os.getenv('DASHSCOPE_API_KEY')
        text_to_sql = Qwen3CoderConverter(db_manager, dashscope_key)
    except Exception as e:
        pipeline_mode = 'rule'
elif pipeline_mode == 'single':
    text_to_sql = EnhancedTextToSQLConverter(db_manager)
else:
    text_to_sql = TextToSQLConverter(db_manager)
```

默认 `PIPELINE_MODE=qwen`，符合项目对医疗复杂 SQL 的生成需求。`DASHSCOPE_MODEL` 在 `.env` 中默认 `qwen3-coder-plus`，可通过修改 `.env` 切换为 `qwen3-coder-next` 等 Qwen3-Coder 系列权重。

#### 1.5.2 Qwen3-Coder-Plus 调用细节

`QwenDashScopeLLM` 类参数：

- `api_key`：从 `.env` 的 `DASHSCOPE_API_KEY` 读取。
- `base_url`：从 `.env` 的 `DASHSCOPE_BASE_URL` 读取，默认 `https://.../compatible-mode/v1`。
- `model`：从 `.env` 的 `DASHSCOPE_MODEL` 读取，默认 `qwen3-coder-plus`。
- `temperature`：0，降低随机性。
- `max_tokens`：500，保证 SQL 长度。

`Qwen3CoderConverter` 继承自 `BaseTextToSQLConverter`，实现 `convert` 和 `convert_async` 方法，统一接口。

### 1.6 系统模块设计

项目目录结构：

```
text-to-sql-healthcare/
├── backend/
│   ├── app.py                 # Flask 应用与 REST API 入口
│   ├── qwen_llm.py            # Qwen3-Coder-Plus 调用封装
│   ├── text_to_sql.py         # 规则匹配与 LLM 转换
│   ├── llm_integration.py     # HuggingFace / OpenAI 统一接口
│   ├── schema_linking.py      # Schema 筛选与表/列相关度计算
│   ├── sql_validator.py       # SQL 校验、安全拦截、错误修正（含 SQLExecutor）
│   ├── sql_summarizer.py      # 结果总结
│   ├── query_optimizer.py     # 性能分析与优化建议
│   ├── query_cache.py         # 查询缓存（memory/redis/memcached）
│   ├── conversation_manager.py # 多轮对话上下文
│   ├── database_adapter.py    # 数据库适配器抽象与 SQLite 实现
│   └── db_manager.py          # 数据库管理、Schema 提取
├── database/
│   ├── schema.sql             # 数据库 Schema 定义
│   ├── database.sql           # 由 generate_data.py 导出的完整数据
│   ├── healthcare.db          # SQLite 数据库文件
│   └── generate_data.py       # 数据生成脚本
├── frontend/
│   └── templates/index.html   # Web 界面
├── demo.py                    # 命令行演示
├── tests/                     # pytest 测试
├── requirements.txt
├── .env.example
└── README.md
```

模块职责详表：

| 模块 | 类/函数 | 职责 |
|------|---------|------|
| `app.py` | Flask app, `create_app` | 注册路由、加载环境变量、初始化适配器、选择 pipeline |
| `app.py` | `/api/schema`, `/api/convert`, `/api/execute`, `/api/query`, `/api/tables`, `/api/table/<name>`, `/api/validate`, `/api/health` | 提供 REST API |
| `app.py` | `/` | 渲染 `index.html` |
| `qwen_llm.py` | `QwenDashScopeLLM` | DashScope 客户端初始化、同步/异步 SQL 生成、SQL 修正 |
| `qwen_llm.py` | `Qwen3CoderConverter` | 接入 `BaseTextToSQLConverter` 接口，调用 `QwenDashScopeLLM` |
| `text_to_sql.py` | `TextToSQLConverter` | 规则匹配，包括简单 SELECT、COUNT、WHERE、JOIN |
| `text_to_sql.py` | `AdvancedTextToSQLConverter` | 支持 OpenAI/HuggingFace 的 LLM 转换 |
| `llm_integration.py` | `EnhancedTextToSQLConverter` | 支持 HuggingFace Inference API 与 Flan-T5-small |
| `schema_linking.py` | `SchemaLinking` | 关键词索引、表/列相关度评分、筛选 Schema 生成 |
| `sql_validator.py` | `SQLValidator` | 语法、表、列、安全校验 |
| `sql_validator.py` | `SQLExecutor` | SQL 执行、LIMIT 控制、超时处理 |
| `sql_summarizer.py` | `SQLSummarizer` | 规则/LLM 结果总结 |
| `query_optimizer.py` | `QueryOptimizer` | 执行计划分析、优化建议 |
| `query_cache.py` | `QueryCache` | 内存/Redis/Memcached 缓存，支持 `scope` 隔离 |
| `conversation_manager.py` | `ConversationManager` | 会话历史、上下文 prompt 构建 |
| `database_adapter.py` | `DatabaseAdapter` (abstract), `SQLiteAdapter` | 数据库连接、查询执行、Schema 提取 |
| `db_manager.py` | `DatabaseManager` | Schema 缓存、格式化、初始化、样例数据 |

### 1.7 设计优势

1. **模块化**：每个模块职责单一，接口清晰，便于独立测试、替换与扩展。
2. **模型可插拔**：`BaseTextToSQLConverter` 接口统一，支持 Qwen、HuggingFace、规则三种实现。
3. **数据库可扩展**：`DatabaseAdapter` 抽象类已实现 `SQLiteAdapter`，可扩展 `PostgreSQLAdapter`、`MySQLAdapter`。
4. **Schema 感知**：动态读取 Schema 并注入 prompt，结合 `SchemaLinking` 压缩长 Schema。
5. **多层安全**：仅允许 SELECT/EXPLAIN，禁止 DDL/DML，自动 LIMIT 与超时。
6. **多轮对话**：`conversation_manager` 维护会话上下文，支持指代消解。
7. **结果可解释**：返回 SQL、结果、自然语言摘要、执行计划、优化建议。
8. **缓存**：支持内存、Redis、Memcached 缓存，按 `scope` 隔离，降低 LLM 调用成本。

## 2. 环境配置与运行方法

### 2.1 开发环境要求

- **操作系统**：Windows 10/11、macOS 或 Linux。
- **Python**：3.8+，推荐 3.10+。
- **模型**：Qwen3-Coder-Plus（通过 DashScope 兼容 OpenAI 接口调用）。
- **数据库**：SQLite（默认），已提供 `database/healthcare.db`。
- **依赖**：见 `requirements.txt`。

主要依赖及用途：

| 依赖 | 用途 |
|------|------|
| `Flask>=3.0.0` | Web 框架与 REST API |
| `Flask-CORS>=4.0.0` | 跨域支持 |
| `asgiref>=3.7.0` | 异步支持 |
| `python-dotenv>=1.0.0` | 环境变量加载 |
| `openai>=1.0.0` | DashScope 兼容 OpenAI 接口 |
| `sqlparse>=0.4.4` | SQL 解析 |
| `redis>=5.0.0` | Redis 缓存 |
| `pymemcache>=4.0.0` | Memcached 缓存 |
| `psycopg2-binary>=2.9.0` | PostgreSQL 驱动 |
| `PyMySQL>=1.1.0` | MySQL 驱动 |
| `pytest>=7.4.0` | 测试框架 |
| `Faker` | 数据生成 |

### 2.2 安装步骤

#### 1. 进入项目目录

```bash
cd text-to-sql-healthcare
```

#### 2. 创建虚拟环境

```bash
python -m venv venv
```

#### 3. 激活虚拟环境

Windows：

```bash
venv\Scripts\activate
```

Linux/macOS：

```bash
source venv/bin/activate
```

#### 4. 安装依赖

```bash
pip install -r requirements.txt
```

#### 5. 配置环境变量

仓库已提供 `.env` 并预填 `DASHSCOPE_API_KEY`，直接运行即可使用 Qwen 模式，无需额外申请 Key。若 `.env` 不存在，可复制 `.env.example`：

```bash
copy .env.example .env
```

`.env` 主要内容（已预填）：

```env
# Pipeline 模式：qwen / single / rule
PIPELINE_MODE=qwen

# DashScope 兼容 OpenAI 接口配置
DASHSCOPE_API_KEY=sk-...
DASHSCOPE_BASE_URL=https://ws-veyj3t9t0e5jiog7.cn-beijing.maas.aliyuncs.com/compatible-mode/v1
DASHSCOPE_MODEL=qwen3-coder-plus

# 数据库
DB_TYPE=sqlite
DB_PATH=database/healthcare.db

# 缓存
CACHE_BACKEND=memory
CACHE_TTL=300

# 性能与安全
MAX_QUERY_ROWS=1000
QUERY_TIMEOUT_SECONDS=30
```

> 注意：`DASHSCOPE_API_KEY` 已在 `.env` 中预填，测试与运行时均会自动加载；如需切换为自己的 DashScope Key 或更换模型（如 `qwen3-coder-next`），修改 `.env` 后重新启动服务即可。

### 2.3 数据库初始化

系统已提供 `database/healthcare.db` 和 `database/database.sql`。如需重新生成：

```bash
python database/generate_data.py
```

该脚本会：

1. 读取 `database/schema.sql` 创建 7 张表。
2. 使用 `Faker` 生成英文患者、医生、科室、预约、病历、处方、处方药品明细数据。
3. 导出 `database/database.sql` 和 `database/healthcare.db`。

`DatabaseManager.initialize_database(schema_file, data_file)` 也可在启动时自动加载。

### 2.4 启动与使用

#### 启动后端

```bash
python backend/app.py
```

服务默认监听 `http://localhost:5000`。

#### 访问 Web 界面

打开浏览器：

```
http://localhost:5000
```

#### 命令行演示

```bash
python demo.py
```

#### API 示例

```bash
# 获取数据库 Schema
curl http://localhost:5000/api/schema

# 自然语言转 SQL
curl -X POST http://localhost:5000/api/convert \
  -H 'Content-Type: application/json' \
  -d '{"query": "Show all patients"}'

# 执行 SQL
curl -X POST http://localhost:5000/api/execute \
  -H 'Content-Type: application/json' \
  -d '{"sql": "SELECT COUNT(*) as count FROM doctors"}'

# 完整查询（自然语言 → SQL → 执行 → 总结）
curl -X POST http://localhost:5000/api/query \
  -H 'Content-Type: application/json' \
  -d '{"query": "How many doctors are there"}'

# SQL 校验
curl -X POST http://localhost:5000/api/validate \
  -H 'Content-Type: application/json' \
  -d '{"sql": "SELECT * FROM patients"}'
```

### 2.5 切换 Pipeline 模式

修改 `.env` 中的 `PIPELINE_MODE`：

```env
PIPELINE_MODE=qwen    # 默认，使用 Qwen3-Coder-Plus
PIPELINE_MODE=single  # 使用 HuggingFace/Flan-T5-small
PIPELINE_MODE=rule    # 使用规则匹配
```

切换后重启 `python backend/app.py` 即可。

## 3. 功能演示与测试结果

### 3.1 用户交互流程
![web页面](./docs/images/web页面.png)

#### 方式一：仅转换（Convert to SQL）

1. 用户在 Web 页面输入自然语言问题，点击 **"Convert to SQL"**。
2. 前端通过 `POST /api/convert` 将问题发送到后端。
3. `app.py` 根据 `PIPELINE_MODE` 选择转换器，默认 `qwen`。
4. `conversation_manager.add_turn(session_id, user_query)` 维护会话上下文。
5. `SchemaLinking` 筛选相关 Schema，避免长 Schema 干扰。
6. `Qwen3CoderConverter` 调用 `QwenDashScopeLLM` 生成 SQL。
7. `SQLValidator` 校验 SQL 语法、表列、安全性。
8. 前端展示生成的 SQL，**不执行**，等待用户确认。

#### 方式二：转换 + 执行（Execute Query）

1. 用户点击 **"Execute Query"**（可直接执行，或对 Convert 生成的 SQL 执行）。
2. 前端通过 `POST /api/query` 将问题发送到后端。
3-7. 同上（步骤 3-7）。
8. `SQLExecutor` 执行 SQL，自动添加 `LIMIT`。
9. `sql_summarizer` 生成中文摘要；`query_optimizer` 返回性能建议。
10. 前端展示 SQL、结果表格、结果摘要、执行计划、优化建议。

界面提供数据库所有表的字段信息，方便用户查阅
![database](./docs/images/database.png)
系统对数据库整体数据自动生成可视化图表，包括各科室患者分布、预约状态分布、血型分布、各科室医生数量、各科室平均薪资、TOP 10 诊断等，帮助用户快速了解数据全貌。
![visual](./docs/images/visual.png)
### 3.2 功能展示

#### 示例 1：简单查询

输入：

```text
Show all patients
```

生成 SQL：

```sql
SELECT * FROM patients;
```

结果：返回患者表记录，前端分页显示。

![test1](./docs/images/test1.png)
#### 示例 2：条件过滤

输入：

```text
Find patients with blood type O-
```

生成 SQL：

```sql
SELECT * FROM patients WHERE blood_type = 'O-';
```

结果：返回血型为 O 的患者列表。
![test2](./docs/images/test2.png)

#### 示例 3：多表 JOIN 与聚合

输入：

```text
查询每个科室的医生数量
```

生成 SQL：

```sql
SELECT d.department_name, COUNT(doctor_id) as doctor_count FROM departments d LEFT JOIN doctors doc ON d.department_id = doc.department_id GROUP BY d.department_id, d.department_name;
```

结果：按科室统计医生数量。
![test3](./docs/images/test3.png)
#### 示例 4：复杂多表查询

输入：

```text
查询2025年每位医生开具的处方总金额，按金额降序排列
```

生成 SQL：

```sql
SELECT d.full_name, SUM(pi.price * pi.quantity) AS total_prescription_amount FROM doctors d JOIN prescriptions pr ON d.doctor_id = pr.doctor_id JOIN prescription_items pi ON pr.prescription_id = pi.prescription_id WHERE strftime('%Y', pr.prescription_date) = '2025' GROUP BY d.doctor_id, d.full_name ORDER BY total_prescription_amount DESC;
```

结果：按降序返回各医生开具处方的总金额。
![test4](./docs/images/test4.png)
#### 示例 5：SQL 错误修正

错误输入：

```sql
SELECT * FROM patiants;
```

`SQLValidator` 检测到表 `patients` 拼写错误，返回错误信息。系统调用 `QwenDashScopeLLM.fix_sql`：

```text
错误 SQL → SQLValidator → fix_sql → SQLValidator → SQLExecutor → 结果
```

修正后 SQL：

```sql
SELECT * FROM patients;
```
![test5](./docs/images/test5.png)
#### 示例 6：结果总结

输入：

```text
查询今天预约数量
```

生成 SQL：

```sql
SELECT COUNT(*) FROM appointments WHERE date(appointment_date) = date('now');
```

返回结果：
![test6](./docs/images/test6.png)

### 3.3 测试结果

项目使用 `pytest` 构建测试套件，覆盖数据库、Text-to-SQL 转换、SQL 校验、SQL 执行、会话上下文、性能基准等核心模块。新增的测试文件包括：

- `tests/test_qwen_llm.py`：Qwen 模型 SQL 生成与修正能力、mock LLM 准确率、可选的实时 Qwen 准确率验证。
- `tests/test_complex_queries.py`：子查询、关联子查询、窗口函数（`ROW_NUMBER`、`RANK`）、`CASE WHEN`、公共表表达式（CTE）等复杂查询。
- `tests/test_error_correction.py`：`SQLValidator.suggest_correction` 启发式修正、LLM `fix_sql` 修正、`SQLExecutor` 重试机制。
- `tests/test_conversation.py`：多轮会话上下文拼接、上下文指代消解、Flask 端到端多轮注入测试。
- `tests/test_performance.py`：规则/Qwen 转换响应时间、SQL 执行响应时间、`query_optimizer` 性能分析、token 消耗记录、缓存读取性能。

测试集分类：

| 类型 | 数量 | 说明 |
|------|------|------|
| 简单查询 | 8 | 单表 SELECT、COUNT |
| JOIN 查询 | 2 | 多表关联 |
| WHERE 查询 | 2 | 条件过滤 |
| 复杂查询 | 8 | 子查询、窗口函数、CTE、`CASE WHEN` |
| LLM 准确率 | 10 | 使用 `database/text_to_sql_tests.json` 对 Qwen 模型进行 mock/live 验证 |
| 错误修正 | 8 | 表/列拼写错误、LLM 修正、重试失败 |
| 多轮对话 | 6 | 会话管理、上下文注入、端到端 API |
| 性能基准 | 6 | 响应时间、token 消耗、缓存性能 |
| 数据库校验 | 若干 | 表列检查、SQL 注入拦截、CTE 表名识别 |
| 其他 | 若干 | 空输入、大小写不敏感 |

运行结果（`.env` 已预填 `DASHSCOPE_API_KEY`，完整 `pytest` 包含 10 个实时 Qwen 准确率测试）：

```bash
$ python -m pytest tests/ -q
........................................................................  [ 80%]
..................                                                       [100%]
90 passed in 23.05s
```

测试套件通过 `tests/conftest.py` 自动加载 `.env`，因此 `.env` 中预填的 `DASHSCOPE_API_KEY` 会同时用于测试与实时 Qwen 验证。运行完整 `pytest` 会触发 10 个实时 Qwen 准确率测试并产生 token 消耗；若只想离线验证 mock 逻辑，可执行 `python -m pytest tests/ -q -k "not live"`。

核心指标：

- **SQL 执行成功率**：测试集中 SELECT 查询 100% 通过。
- **Exact Match Accuracy**：规则引擎对模板化问题的 SQL 生成可复现。
- **Execution Accuracy**：生成 SQL 在 SQLite 中可执行并返回正确结果。
- **LLM 准确率**：mock 测试对 `database/text_to_sql_tests.json` 的 10 条用例均通过 SQL 校验与执行；实时 Qwen 测试在 `DASHSCOPE_API_KEY` 可用时启用。
- **错误修正**：对表名拼写错误、`suggest_correction` 与 `fix_sql` 均能通过 `SQLExecutor` 重试并返回正确结果。
- **平均响应时间**：本地规则查询 < 10ms；Qwen 接口调用约 0.5-2s；缓存命中 < 50ms。

### 3.4 性能分析

- `query_optimizer` 对每条查询获取 `EXPLAIN QUERY PLAN` 并给出建议，例如避免 `SELECT *`、在外键列建索引、避免 `LIKE '%xxx'` 前缀通配符、为无 LIMIT 查询添加限制。
- `SQLExecutor` 自动追加 `LIMIT`（默认 1000 行），降低前端渲染压力。
- 对慢查询，使用 `execute_query_with_timeout` 在线程池中执行，超时 30s，防止单条查询阻塞。
- 缓存层：重复查询先命中 `query_cache`，支持 `memory`/`redis`/`memcached`，按 `scope` 隔离 `/api/convert` 与 `/api/query` 的缓存键，避免转换结果与执行结果混用。
- 前端使用 Chart.js 可视化聚合结果，表格限制显示行数，避免一次性渲染大量数据。

## 4. 遇到的挑战与解决方案

### 4.1 LLM 生成 SQL 的准确率问题

**挑战**：大模型在生成 SQL 时容易出现以下错误：

- 使用不存在的表或字段。
- 多表 JOIN 条件错误，导致笛卡尔积或空结果。
- 对 SQLite 方言不熟悉，例如生成不符合 SQLite 语法的函数或语法。
- 对日期、字符串函数使用不当。

**解决方案**：

1. **Schema 注入**：在 prompt 中拼接 `db_manager.get_schema_for_prompt()` 生成的 Schema 文本，包括表名、列名、主键、外键，使模型明确可用字段。
2. **Schema 筛选**：使用 `SchemaLinking` 对长 Schema 做相关表/列筛选，避免无关信息干扰。
3. **Prompt 工程**：在 prompt 中显式要求“使用 JOIN 并在多个表查询时使用正确外键关系”“仅使用 Schema 中存在的表和列”“只输出 SQL”等约束。
4. **SQL 校验**：`SQLValidator` 校验表、列存在性与 SQL 语法，错误时触发 `fix_sql` 修正。
5. **Few-shot 示例**：对常见医疗查询（如按科室统计、按诊断过滤）准备示例，提升模型理解。

### 4.2 SQL 合法性与安全性问题

**挑战**：

- 模型可能返回不完整 SQL、带解释文字、或 markdown 代码块。
- 模型可能生成 `DROP`、`DELETE`、`UPDATE` 等危险操作。
- 用户输入可能包含 SQL 注入。

**解决方案**：

1. **结果清洗**：`qwen_llm.py` 使用正则去除 ` ```sql ` 和 ` ``` ` 标记。
2. **安全拦截**：`SQLValidator._check_security` 仅允许 `SELECT`/`EXPLAIN` 开头，禁止 `DROP`、`TRUNCATE`、`ALTER`、`CREATE`、`DELETE`、`UPDATE`、`INSERT`，并禁止多语句。
3. **表列存在性检查**：`SQLValidator` 提取 `FROM`、`JOIN` 表名和 `SELECT` 列名，与 Schema 比对。
4. **数据库级验证**：使用 `EXPLAIN {sql}` 确认 SQL 可被解析。
5. **API 层只读**：`SQLExecutor` 只执行 `SELECT`/`EXPLAIN`，其他操作被拦截。
6. **自动 LIMIT 与超时**：防止大数据查询和慢查询影响系统稳定性。

### 4.3 长 Schema 输入问题

**挑战**：

- 7 张表、数十个字段的 Schema 全部注入 prompt，会占用大量 token，稀释问题语义。
- 某些查询只涉及 2-3 张表，全部 Schema 是冗余的。

**解决方案**：

1. **关键词索引**：`SchemaLinking.build_index` 对表名、列名及其单复数形式建立索引。
2. **相关度评分**：`score_tables` 和 `score_columns` 对查询中的关键词匹配表名、列名打分。
3. **保留外键关系**：`get_filtered_schema_text` 返回相关表及相关表之间的外键，确保模型能正确生成 JOIN。
4. **回退策略**：当相关表匹配失败时，回退到完整 Schema。

### 4.4 系统性能问题

**挑战**：

- LLM 接口调用有延迟，重复查询浪费 token。
- 前端一次性渲染大量数据可能导致卡顿。
- 慢查询可能阻塞主线程。

**解决方案**：

1. **查询缓存**：`query_cache.py` 实现 `InMemoryCache`、`RedisCache`、`MemcachedCache`。缓存键由 `query` + `pipeline_mode` + `scope` 组成，避免 `/api/convert` 与 `/api/query` 缓存冲突。
2. **LIMIT 限制**：`SQLExecutor` 自动添加 `LIMIT`，默认 1000 行。
3. **超时控制**：`execute_query_with_timeout` 在独立线程中执行 SQL，超时 30s。
4. **前端优化**：Web 界面使用分页与图表，限制单次渲染数据量。
5. **异步接口**：`app.py` 提供 `/api/convert` 等异步接口，避免阻塞。

### 4.5 多轮对话上下文问题

**挑战**：

- 用户可能输入“上一个查询的结果中，再按科室分组”等指代问题，需要维护上下文。
- 上下文过长可能降低模型效果。

**解决方案**：

1. **会话管理**：`conversation_manager.py` 维护 `ConversationManager`，按 `session_id` 存储历史。
2. **上下文 prompt**：`build_context()` 将历史查询和结果拼接为上下文，注入 `Qwen3CoderConverter`。
3. **历史长度控制**：`add_turn` 限制保留最近若干轮，避免 prompt 过长。
4. **上下文清理**：提供 `/api/health` 或手动清除会话。

### 4.6 系统扩展性问题

**挑战**：

- 如何支持 MySQL、PostgreSQL 以及不同 LLM。

**解决方案**：

1. **数据库抽象**：`DatabaseAdapter` 抽象类定义 `get_connection`、`execute_query`、`get_schema`、`initialize_database` 等方法。`SQLiteAdapter` 已实现，新增 PostgreSQL/MySQL 只需实现 `DatabaseAdapter` 并在 `db_manager.py` 中注册。
2. **模型抽象**：`BaseTextToSQLConverter` 定义 `convert` 和 `convert_async` 接口。`Qwen3CoderConverter`、`EnhancedTextToSQLConverter`、`TextToSQLConverter` 分别实现。新增模型只需实现该接口并在 `app.py` 中注册。
3. **配置化**：`.env` 管理 `PIPELINE_MODE`、`DASHSCOPE_MODEL`、`CACHE_BACKEND`、`DB_TYPE` 等，无需修改代码即可切换后端。

HealthSQL-Agent 通过以上设计，形成了一个面向医疗 HIS 数据库、可扩展、可解释、安全的 Text-to-SQL 系统，适用于自然语言数据查询与决策支持场景。
