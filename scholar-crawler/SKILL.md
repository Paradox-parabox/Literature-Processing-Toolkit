---
name: scholar-crawler
description: 自动化学术文献爬虫，用于学术文献检索。从 references-searcher 生成的搜索计划文档中提取 SEED（滚雪球）和 QUERY（关键词）两种指令，优先使用 Semantic Scholar API（稳定、无封禁风险），Google Scholar 作为补全策略，生成带过滤和相关性分析的排序文献列表（CSV/Excel），并自动清洗不相关文献。使用场景：(1) 从搜索计划文档自动检索文献 (2) 需要系统性文献回顾 (3) 想要识别高影响力、近期论文 (4) 需要结构化数据用于文献数据库 (5) 清洗文献列表去除噪音
---

# 学术文献爬虫

## 概述

Scholar 爬虫是一款通用的学术文献检索工具。它接收由 `references-searcher` 技能生成的**两种指令类型**，**优先使用 Semantic Scholar API 进行搜索**（官方API、稳定、无封禁风险），当 Semantic Scholar 结果不足时自动使用 Google Scholar 作为补全，并生成带有智能过滤和排名的结构化文献数据库（CSV/Excel）。

**主要功能**：
- **支持两种指令类型**：
  - `SEED`: 滚雪球搜索（找到引用种子论文的论文）
  - `QUERY`: 直接关键词搜索
- 自动从搜索计划文档中提取指令
- **Semantic Scholar 优先**：使用官方API，稳定可靠，无封禁风险
- **Google Scholar 补全**：当结果不足时自动回退
- 过滤近期和高引用量论文
- 按引用量和相关性评分对论文进行排名
- **GB/T 7714 引用格式**：自动生成符合中国国标的引用格式
- 生成 CSV 数据库和摘要报告

## 指令类型说明

### SEED 指令（滚雪球搜索）

**用途**：当断言涉及知名方法、特定学者或经典理论时，使用滚雪球搜索找到引用该种子论文的最新研究。

**格式**：
```markdown
1. SEED: "Author Title Keywords (Year)" | FILTER: "keyword1" "keyword2" | SORT: "sort_value"
```

**关键要求**：
- SEED 必须包含**作者姓氏 + 标题关键词 + 年份**，标题关键词应选取论文标题中最具区分度的 2-4 个词，以确保爬虫能精准定位论文 ID。
- FILTER 为**关键词列表**（用空格分隔的引号字符串），爬虫将使用 **BM25 算法**计算每篇引用论文的相关性评分，并按评分排序输出。

**示例**：
- `SEED: "Raissi Physics-informed neural networks 2019" | FILTER: "multiphase flow" "porous media" | SORT: "influence"` ✅ 正确
- `SEED: "Raissi (2019)"` ❌ 错误（缺少标题关键词，无法精准匹配）
- `SEED: "Raissi Physics-informed neural networks 2019" | FILTER: "A" AND "B" | SORT: "influence"` ❌ 错误（FILTER 不应使用 AND，应使用空格分隔的关键词列表）

**SORT 可选值**：
| 值 | 含义 | 适用场景 |
|---|------|---------|
| `influence` | 按影响力排序 | 优先高 BM25 分数 + 高引用论文 |
| `recency` | 按最新发表排序 | 优先最新发表的高 BM25 分数论文 |

**工作原理**：
1. 在 Semantic Scholar 搜索种子论文（使用作者+标题关键词+年份），获取 `paperId`
2. **种子论文本身会被添加到结果列表最前面**，标记为 `SEED_SOURCE` 类型
3. 调用 Semantic Scholar Citations API 获取引用该论文的所有论文
4. 使用 FILTER 关键词通过 **BM25 算法**计算每篇论文的相关性评分
5. 按评分排序输出（种子论文始终在最前，引用论文按BM25排序）

**SEED_SOURCE 类型说明**：
- 种子论文本身会被自动添加到结果列表，标记为 `SEED_SOURCE`
- 种子论文**不受初筛过滤影响**，始终保留
- 种子论文会计算 BM25 分数，但始终排在结果列表最前面
- 这确保了"祖师爷"论文不会在滚雪球搜索中被遗漏

**BM25 评分说明**：
- BM25 是信息检索领域的经典算法，用于计算文档与查询词的相关性
- 评分考虑：词频（TF）、逆文档频率（IDF）、文档长度归一化
- 参数：k1=1.5（词频饱和度），b=0.75（长度归一化）
- 结果：每篇论文获得一个 BM25 分数，分数越高越相关

**FILTER 条件支持**：
- 年份过滤：`Year > 2023`、`Year >= 2020`、`Year < 2025`
- 关键词列表：`"multiphase flow" "PINNs" "porous media"`（空格分隔）
- 组合：`Year > 2020 "lattice Boltzmann" "multiphase"`

### QUERY 指令（关键词搜索）

**用途**：当断言描述具体数据关联、冷门应用或全新组合时，使用直接关键词搜索。

**格式**：
```markdown
1. QUERY: "Boolean Search String" | SORT: "sort_value"
```

**SORT 可选值**：
| 值 | 含义 | 适用场景 |
|---|------|---------|
| `citation` | 按引用量排序 | 寻找领域高引综述 |
| `relevance` | 按相关性排序 | 寻找字面最匹配的文献 |

**工作原理**：
1. 直接将查询字符串发送给 Semantic Scholar 搜索 API
2. 如果结果不足，自动回退到 Google Scholar

## 核心工作流程

### 第一步：安装依赖
```bash
pip install -r scripts/requirements.txt
pip install scholarly --upgrade
pip install fake-useragent
```

### 第一步半：配置 Semantic Scholar API Key（推荐）
Semantic Scholar 提供免费的 API Key，可以获得更高的请求速率限制（100 请求/5分钟，无 Key 时为 100 请求/5分钟但更容易触发限制）。

**配置方式（三选一）**：

1. **配置文件（推荐）**：编辑 `config.json` 文件：
   ```json
   {
       "semantic_scholar_api_key": "YOUR_API_KEY_HERE"
   }
   ```

2. **环境变量**：
   ```bash
   # Windows PowerShell
   $env:SEMANTIC_SCHOLAR_API_KEY = "YOUR_API_KEY_HERE"
   
   # Linux/Mac
   export SEMANTIC_SCHOLAR_API_KEY="YOUR_API_KEY_HERE"
   ```

3. **命令行参数**：
   ```bash
   python scripts/scholar_crawler.py --input search_plan.md --api-key "YOUR_API_KEY"
   ```

**申请 API Key**：访问 [Semantic Scholar API](https://www.semanticscholar.org/product/api) 免费申请。

### 第二步：输入准备

**选项 A：从搜索计划文档提取指令**（推荐）

爬虫自动从 `references-searcher` 生成的 Markdown 文件中提取 SEED 和 QUERY 指令。

**输入文件格式示例**：
```markdown
# 🧑‍💻 人类最高指令区

> 此区域供人类审阅者添加、修改或覆盖下方自动生成的查询。

## 手动添加的查询
1. SEED: "Raissi Physics-informed neural networks 2019" | FILTER: "Year > 2023" | SORT: "recency"
2. QUERY: "custom keyword search" | SORT: "citation"

---

> 原文：近期研究开始探索利用物理信息神经网络 (PINNs) 来加速多相流模拟。

- **Type**: Method/SOTA
- **Intent**: 寻找 PINNs 在多相流领域的最新应用
- **Strategy**: Snowballing (Seed: Raissi)

1. SEED: "Raissi Physics-informed neural networks 2019" | FILTER: "multiphase flow" "porous media" | SORT: "influence"
2. SEED: "Pang fractional PINNs 2019" | FILTER: "lattice boltzmann" "fractional" | SORT: "recency"
3. QUERY: "PINNs" AND "porous media" AND "multiphase" | SORT: "relevance"
```

**🧑‍💻 人类最高指令区优先处理**：
如果输入文档包含"人类最高指令区"（以 `# 🧑‍💻 人类最高指令区` 开头），爬虫会：
1. **优先读取**该区域中人类手动添加的指令
2. **尊重人类意图**：人类添加的指令优先级最高，不可被覆盖或忽略
3. **合并处理**：将人类指令与自动生成的指令合并，人类指令放在列表最前面

**选项 B：直接查询输入**
直接作为命令行参数提供查询（自动作为 QUERY 类型处理）。

### 第三步：运行爬虫
```bash
# 使用搜索计划文档（Semantic Scholar 优先）
python scripts/scholar_crawler.py --input "search_plan.md" --max-results 10

# 使用自定义输出目录
python scripts/scholar_crawler.py --input "search_plan.md" --output-dir "./literature/"

# 直接查询输入（自动作为 QUERY 类型）
python scripts/scholar_crawler.py --queries "\"Fractional Cahn-Hilliard\" AND \"porous media\"" "\"lattice Boltzmann\" AND surfactant"

# 仅使用 Google Scholar（当 Semantic Scholar 不可用时）
python scripts/scholar_crawler.py --input "search_plan.md" --google-only

# 仅使用 Semantic Scholar（禁用 Google Scholar 回退）
python scripts/scholar_crawler.py --input "search_plan.md" --no-fallback

# 测试模式（解析指令但不搜索）
python scripts/scholar_crawler.py --input "search_plan.md" --test-mode
```

**搜索策略说明**：
- **默认模式**：先在 Semantic Scholar 搜索，结果不足时自动使用 Google Scholar 补全
- **`--google-only`**：仅使用 Google Scholar（适用于 Semantic Scholar 无法找到特定文献时）
- **`--no-fallback`**：仅使用 Semantic Scholar（禁用 Google Scholar 回退）
- **延迟设置**：Semantic Scholar 搜索时延迟较短（1-2秒），Google Scholar 时自动增加延迟（2-5秒）

### 第四步：输出分析
爬虫生成两个文件：
1. **`literature_review_YYYYMMDD_HHMMSS.csv`** - 完整数据库
2. **`crawler_report_YYYYMMDD_HHMMSS.md`** - 摘要报告

### 第五步：文献清洗（Paper-Filter）

爬虫完成后，LLM 应自动执行文献清洗，根据用户的研究草稿过滤不相关文献。

#### 建立语义锚点
从用户提供的 **[Context/Draft]** 中提取 3-5 个核心研究主题：
- 关键方法论（如 LBM、相场模型、PINNs）
- 研究对象（如多孔介质、多相流）
- 特定技术（如分数阶导数、GPU并行）

#### 质量与相关性评估

**相关性检查**：
- **保留**：标题或摘要匹配核心主题
- **剔除**：标题包含明显无关领域词汇

**学术质量分级**：

| 级别 | 条件 | 处理 |
|------|------|------|
| 🥇 S级 | 近5年综述 或 引用>100 | 必须保留 |
| 🥈 A级 | 当前年份或前一年发表 | 必须保留（最新动态） |
| ❌ B级 | 超过5年且引用<10 | 剔除 |

#### 清洗输出格式

输出 Markdown 表格：

| 推荐度 | 年份 | 引用 | 标题 | 留选理由 |
| :--- | :--- | :--- | :--- | :--- |
| 🥇 S-Review | 2022 | 110 | Title... | 综述了核心主题的最新进展 |
| 🥈 A-New | 2025 | 0 | Title... | 最新发表，具有前沿性 |

**底部报告**：
- 共清洗: X 篇
- 保留: Y 篇
- 主要剔除原因: (具体说明)

## 详细用法

### 命令行参数

| 参数 | 描述 | 默认值 |
|------|------|--------|
| `--input`, `-i` | 搜索计划 .md 文件路径 | （如果没有查询则必需） |
| `--queries`, `-q` | 直接查询列表（作为 QUERY 类型） | （如果没有输入则必需） |
| `--max-results`, `-m` | 每个指令的最大论文数 | **20**（已增加） |
| `--output-dir`, `-o` | 输出目录 | 当前目录 |
| `--delay-min` | 请求间的最小延迟 | 1.1 秒 |
| `--delay-max` | 请求间的最大延迟 | 1.1 秒 |
| `--google-only` | 仅使用 Google Scholar（禁用 Semantic Scholar） | False |
| `--no-fallback` | 仅使用 Semantic Scholar（禁用 Google Scholar 回退） | False |
| `--test-mode` | 解析指令但不搜索 | False |
| `--api-key` | Semantic Scholar API key | 从配置文件或环境变量读取 |
| `--sort-by` | 排序方式：`relevance`、`citationCount:desc`、`year:desc` 等 | 默认相关性 |
| `--exact-title` | 精确标题匹配模式（用于查找特定论文） | False |

**SORT 优先级**：
1. **最高**：指令中的 `SORT` 标签
2. **次高**：命令行 `--sort-by` 参数
3. **默认**：相关性排序

### 提高匹配率的高级用法

#### 问题：关键词匹配但排序靠后

当目标文献存在但被其他高引文献挤到后面时，可使用以下策略：

**策略1：增加返回数量**
```bash
python scripts/scholar_crawler.py --input search_plan.md --max-results 30
```

**策略2：按年份排序（找最新研究）**
```bash
python scripts/scholar_crawler.py --input search_plan.md --sort-by "year:desc"
```

**策略3：按引用排序（找经典文献）**
```bash
python scripts/scholar_crawler.py --input search_plan.md --sort-by "citationCount:desc"
```

**策略4：精确标题搜索（找特定论文）**
```bash
# 直接搜索特定论文
python scripts/scholar_crawler.py --queries "Analysis and approximation of a fractional Cahn-Hilliard equation" --exact-title
```

**策略5：组合使用**
```bash
# 按年份排序 + 增加返回数量
python scripts/scholar_crawler.py --input search_plan.md --max-results 30 --sort-by "year:desc"
```

### 指令提取逻辑

脚本通过正则表达式从 .md 文件中提取指令：

**SEED 指令格式**：
```markdown
1. SEED: "Author Title Keywords (Year)" | FILTER: "keyword1" "keyword2" | SORT: "sort_value"
```
正则：`(\d+)\.\s*SEED:\s*"([^"]+)"\s*\|\s*FILTER:\s*(.+?)(?:\s*\|\s*SORT:\s*"([^"]+)")?(?=\n|$)`

**关键要求**：
- SEED 必须包含**作者姓氏 + 标题关键词 + 年份**，例如：
  - `SEED: "Raissi Physics-informed neural networks 2019"` ✅ 正确
  - `SEED: "Raissi (2019)"` ❌ 错误（缺少标题关键词）
- FILTER 为**关键词列表**（空格分隔的引号字符串），例如：
  - `FILTER: "multiphase flow" "porous media"` ✅ 正确
  - `FILTER: "A" AND "B"` ❌ 错误（不应使用 AND）

**QUERY 指令格式**：
```markdown
1. QUERY: "Boolean Search String" | SORT: "sort_value"
```
正则：`(\d+)\.\s*QUERY:\s*(.+?)(?:\s*\|\s*SORT:\s*"([^"]+)")?(?=\n|$)`

**SORT 标签映射**：
| SORT 值 | Semantic Scholar 参数 |
|---------|----------------------|
| `citation` | `citationCount:desc` |
| `relevance` | 默认（无需指定） |
| `influence` | `citationCount:desc` |
| `recency` | `year:desc` |

**SORT 优先级**：
1. **最高**：指令中的 `SORT` 标签
2. **次高**：命令行 `--sort-by` 参数
3. **默认**：相关性排序

**向后兼容**：SORT 标签为可选，旧格式指令仍可正常使用。

### 搜索源对比

| 特性 | Semantic Scholar | Google Scholar |
|------|------------------|----------------|
| **稳定性** | ✅ 官方API，无封禁风险 | ⚠️ 易被封禁 |
| **速度** | ✅ 快速 | ⚠️ 需要长延迟 |
| **覆盖面** | ⚠️ 部分领域较少 | ✅ 全面 |
| **引用数据** | ✅ 准确 | ✅ 准确 |
| **摘要** | ✅ 结构化数据 | ⚠️ 需解析 |
| **滚雪球搜索** | ✅ 原生支持 Citations API | ❌ 不支持 |

**推荐策略**：
- SEED 指令：必须使用 Semantic Scholar（需要 Citations API）
- QUERY 指令：默认使用 Semantic Scholar，结果不足时回退到 Google Scholar

### 过滤与排名

**过滤规则**：
1. **新星保护**：近 2 年的文章（如 2025-2026）无论引用多少全保留
2. **经典门槛**：老文章（2 年前）引用必须 > 10 次
3. **兜底规则**：年份解析失败但引用 > 10 次也保留

**排名算法**：
1. 主要：引用量（降序）
2. 次要：发表年份（降序）
3. 第三：相关性评分 = 引用量评分 + 0.5*年份评分

### 输出格式

#### CSV 列：
- `Query_Group`: 指令标识符（SEED_1 或 QUERY_1）
- `Directive_Type`: 指令类型（SEED 或 QUERY）
- `Seed_Paper`: 种子论文信息（仅 SEED 类型）
- `Filter_Applied`: 应用的过滤条件（仅 SEED 类型）
- `Sort_Method`: 排序方式（citation, relevance, influence, recency）
- `Title`: 论文标题
- `Authors`: 作者列表（分号分隔）
- `Year`: 发表年份
- `Citations`: 引用量
- `BM25_Score`: BM25 相关性评分（仅 SEED 类型）
- `Abstract_Summary`: 截断的摘要（200字符）
- `Link`: 论文链接（Semantic Scholar 或 Google Scholar）
- `Venue`: 期刊/会议名称
- `DOI`: 论文 DOI 标识符
- `Volume`: 期刊卷号
- `Issue`: 期刊期号
- `Pages`: 页码范围
- `Citation_GB`: GB/T 7714-2015 标准引用格式
- `Relevance_Score`: 综合相关性评分（BM25 + 引用 + 年份）
- `Source`: 数据来源，可能的值：
  - `"Semantic Scholar"`: 普通关键词搜索结果
  - `"Semantic Scholar (SEED)"`: SEED搜索的引用论文
  - `"Semantic Scholar (SEED_SOURCE)"`: 种子论文本身（始终保留，不受过滤影响）
  - `"Google Scholar"`: Google Scholar 回退结果

#### 报告内容：
- SEED 和 QUERY 结果统计
- 顶部 3 篇"必读"论文，含完整详情
- 查询组统计
- 搜索摘要和时间戳

## 故障排除

### 常见问题及解决方案

#### 问题： "scholarly 库未安装"
```bash
pip install scholarly --upgrade
pip install fake-useragent
pip install semanticscholar
pip install rank_bm25
```

#### 问题： BM25 评分全为 0
1. 检查 FILTER 是否包含关键词：`FILTER: "keyword1" "keyword2"`
2. 确保关键词用引号包裹并用空格分隔
3. 如果论文没有摘要，BM25 评分可能较低

#### 问题： Semantic Scholar 无结果
```bash
# 使用 Google Scholar 补全（仅对 QUERY 指令有效）
python scripts/scholar_crawler.py --input search_plan.md --google-only
```

#### 问题： SEED 搜索找不到种子论文
1. 检查种子格式是否正确：`"Author Title Keywords (Year)"` 必须包含标题关键词
2. 确保标题关键词具有区分度，避免使用过于通用的词
3. 尝试更具体的种子：`"Raissi Physics-informed neural networks deep learning 2019"`
4. 使用 QUERY 指令作为替代

#### 问题： Google Scholar 阻止请求
```bash
# 增加延迟（仅在使用 Google Scholar 时）
python scripts/scholar_crawler.py --input search_plan.md --google-only --delay-min 5 --delay-max 15

# 首先使用测试模式验证指令
python scripts/scholar_crawler.py --input search_plan.md --test-mode
```

#### 问题： 从 .md 文件中未提取指令
1. 确保指令格式正确：`1. SEED: "xxx" | FILTER: "yyy"` 或 `1. QUERY: "xxx"`
2. 检查是否使用了正确的引号（英文双引号）
3. 尝试直接查询输入：`--queries "your query"`

### 调试模式
```bash
# 详细输出
python scripts/scholar_crawler.py --input search_plan.md --max-results 5

# 检查将提取的指令
python scripts/scholar_crawler.py --input search_plan.md --test-mode
```

## 脚本

### `scripts/scholar_crawler.py`
包含所有功能的主要爬虫脚本。

### `scripts/requirements.txt`
Python 依赖项：
- `semanticscholar`: Semantic Scholar 官方 API（主要搜索源）
- `scholarly`: Google Scholar API 包装器（补全搜索源）
- `pandas`: 数据操作和 CSV 导出
- `requests`: HTTP 请求（备份）
- `beautifulsoup4`: HTML 解析（备份）
- `fake-useragent`: 用户代理生成
- `rank_bm25`: BM25 相关性评分算法

## 性能说明

- **API 限制**：Semantic Scholar API 限制为 1 RPS（每秒 1 次请求）
- **典型搜索时间**：
  - SEED 指令：~2-3 秒（需要 2 次 API 调用，每次 1.1 秒延迟）
  - QUERY 指令 (Semantic Scholar): ~1-2 秒
  - QUERY 指令 (Google Scholar): ~30 秒（含延迟）
- **内存使用**：最少（<100MB）
- **输出大小**：CSV 中每篇论文 ~1KB
- **推荐抓取上限**：300-500 篇（API 限制宽松，可放心抓取）
- **并发策略**：单线程（1 RPS 硬限制，多线程会导致 429 错误）

## 伦理考量

1. **优先使用 Semantic Scholar**：官方API，符合服务条款
2. **谨慎使用 Google Scholar**：使用最少 2-5 秒的延迟
3. **仅限学术用途**：用于研究中的文献回顾
4. **正确引用**：在您的参考文献中使用收集的论文

---

*注意： 此工具用于学术文献回顾目的。Semantic Scholar 为主要搜索源，支持 SEED（滚雪球）和 QUERY（关键词）两种指令类型。*