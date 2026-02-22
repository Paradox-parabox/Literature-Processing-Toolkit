# 学术文献处理工具链 (Academic Literature Processing Toolkit)

一个完整的学术文献处理工具链，旨在自动化从研究构思到文献筛选的全过程，提高科研工作者的效率。

## 项目概述

这个工具链包含四个核心组件，形成了从研究框架提取到文献筛选的完整闭环，它们是基于 Trae AI 技能系统的 Anthropic 规范的 Agent 技能。

### 1. references-seacher
智能文献检索指令生成器，从学术文本中逐句提取断言，分析语义意图，生成标准化的文献检索指令。

- **功能**：逐句审计与断言拆解 → 意图识别与原语调用 → 生成检索指令
- **适用场景**：为研究草稿中的学术断言寻找文献支持
- **输出**：包含 SEED（滚雪球）和 QUERY（关键词）指令的 Markdown 搜索计划
- **技能格式**：遵循 Anthropic 技能规范，可在 Trae AI 环境中直接使用

### 2. PICOS-catcher
自动从研究文档中提取PICOS标准（研究对象、干预措施、对照、结果、研究设计），生成纳入/排除准则。

- **功能**：领域识别 → 逐句审计 → 提取PICOS → 生成准则 → 输出标准化文档
- **适用场景**：明确研究范围、定义文献筛选标准，为系统性文献综述构建框架
- **输出**：包含完整五要素分析和筛选准则的 Markdown 文件
- **技能格式**：遵循 Anthropic 技能规范，可在 Trae AI 环境中直接使用

### 3. scholar-crawler
学术文献爬虫，优先使用 Semantic Scholar API，Google Scholar 作为补全策略。

- **功能**：从搜索计划提取指令 → Semantic Scholar 搜索 → Google Scholar 补全 → 过滤与排名
- **适用场景**：获取大量相关文献，特别是高影响力或最新研究
- **输出**：包含 GB/T 7714 引用格式的 CSV 文献数据库和摘要报告
- **技能格式**：遵循 Anthropic 技能规范，可在 Trae AI 环境中直接使用

### 4. PICOS-screener
基于PICOS标准的文献筛选器，执行两阶段筛选（标题摘要筛选+全文筛选），生成PRISMA流程图。

- **功能**：输入验证与去重 → 加载PICOS标准 → 第一阶段筛选 → 第二阶段筛选 → 依据映射
- **适用场景**：根据研究标准对大量文献进行精准筛选
- **输出**：筛选结果 CSV、纳入论文清单和筛选报告（含 PRISMA 流程图数据）
- **技能格式**：遵循 Anthropic 技能规范，可在 Trae AI 环境中直接使用

## 安装

### 方法一：作为独立工具使用

```bash
# 克隆项目
git clone <repository-url>
cd academic-literature-toolkit

# 安装依赖
pip install -r requirements.txt
```

### 方法二：作为 Trae AI 技能安装（推荐）

这些工具是为 Trae AI 环境设计的 Anthropic 规范 Agent 技能，可以直接安装到 Trae AI 技能系统中：

1. **复制技能文件夹**：将 `skills` 目录下的四个技能文件夹（`references-seacher`、`PICOS-catcher`、`scholar-crawler`、`PICOS-screener`）复制到 Trae AI 的技能目录：
   ```
   C:\Users\<username>\.trae-cn\skills\
   ```

2. **验证安装**：重启 Trae AI 环境，技能将自动加载

### 依赖项

```txt
semanticscholar
scholarly
pandas
requests
beautifulsoup4
rank_bm25
fake-useragent
```

## 配置

### Semantic Scholar API Key（推荐）

Semantic Scholar 提供免费的 API Key，可以获得更高的请求速率限制。

1. **申请 API Key**：访问 [Semantic Scholar API](https://www.semanticscholar.org/product/api) 免费申请
2. **配置方式**：
   - **配置文件**：编辑 `config.json` 文件
   - **环境变量**：设置 `SEMANTIC_SCHOLAR_API_KEY` 环境变量
   - **命令行参数**：运行时通过 `--api-key` 参数指定

## 使用方法

### 方法一：在 Trae AI 环境中使用（推荐）

这些技能专为 Trae AI 环境设计，可以直接调用：

1. **使用 PICOS-catcher**：
   ```python
   # 在 Trae AI 中直接调用
   PICOS-catcher
   # 从研究文档提取PICOS框架
   # 生成标准化的纳入/排除准则
   ```

2. **使用 references-seacher**：
   ```python
   # 在 Trae AI 中直接调用
   references-seacher
   # 从研究草稿提取断言
   # 生成检索指令
   ```

3. **使用 scholar-crawler**：
   ```python
   # 在 Trae AI 中直接调用
   scholar-crawler
   # 执行文献检索
   # 处理 search_plan.md 文件
   ```

4. **使用 PICOS-screener**：
   ```python
   # 在 Trae AI 中直接调用
   PICOS-screener
   # 筛选文献
   # 生成PRISMA流程图
   ```

### 方法二：作为独立工具使用

#### 完整工作流程

1. **使用 PICOS-catcher**：
   ```bash
   # 从研究文档提取PICOS框架
   # 生成标准化的纳入/排除准则
   ```

2. **使用 references-seacher**：
   ```bash
   # 从研究草稿提取断言
   # 生成检索指令
   ```

3. **使用 scholar-crawler**：
   ```bash
   # 执行文献检索
   python scholar-crawler/scripts/scholar_crawler.py --input search_plan.md
   ```

4. **使用 PICOS-screener**：
   ```bash
   # 筛选文献
   # 生成PRISMA流程图
   ```

#### 独立工具示例

```bash
# 从搜索计划文档检索文献
python scholar-crawler/scripts/scholar_crawler.py --input "search_plan.md" --max-results 20

# 直接查询
python scholar-crawler/scripts/scholar_crawler.py --queries "\"Fractional Cahn-Hilliard\" AND \"porous media\""

# 指定输出目录
python scholar-crawler/scripts/scholar_crawler.py --input "search_plan.md" --output-dir "./literature/"
```

## 项目结构

### 源代码结构

```
academic-literature-toolkit/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── requirements.txt
├── skills/
│   ├── references-seacher/     # 检索指令生成器（Trae AI 技能）
│   ├── PICOS-catcher/         # PICOS框架提取器（Trae AI 技能）
│   ├── scholar-crawler/       # 学术文献爬虫（Trae AI 技能）
│   └── PICOS-screener/        # 文献筛选器（Trae AI 技能）
└── examples/
    ├── search_plan_example.md
    └── output_examples/
```

### Trae AI 技能安装后结构

安装到 Trae AI 系统后，技能将位于：

```
C:\Users\<username>\.trae-cn\skills\
├── references-seacher/         # 检索指令生成器
├── PICOS-catcher/             # PICOS框架提取器
├── scholar-crawler/           # 学术文献爬虫
└── PICOS-screener/            # 文献筛选器
```

## 贡献

欢迎任何形式的贡献！请参阅 [CONTRIBUTING.md](CONTRIBUTING.md) 了解详细信息。

## 许可证

本项目采用 [MIT License](LICENSE)，详情请参见 LICENSE 文件。

## 鸣谢

- 感谢 Semantic Scholar 提供的学术API
- 感谢 Google Scholar 的学术搜索功能
- 感谢所有为学术研究做出贡献的研究人员

## 伦理声明

本工具仅供学术文献回顾目的使用，优先使用官方API，遵守服务条款。