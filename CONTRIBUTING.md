# 贡献指南 (Contributing Guide)

感谢您有兴趣为学术文献处理工具链项目做贡献！本文档提供了有关如何参与该项目的详细信息。

## 行为准则

请遵守我们的行为准则，营造友好、包容的贡献环境。

## 开发环境设置

### 1. 克隆项目

```bash
git clone <repository-url>
cd academic-literature-toolkit
```

### 2. 安装依赖

```bash
pip install -r requirements.txt
```

### 3. 配置开发环境

- 确保 Python 版本 >= 3.8
- 推荐使用虚拟环境
- 安装开发依赖（如有）

## 贡献方式

### 报告 Bug

当报告 Bug 时，请包含：

1. **清晰的标题和描述**
2. **复现步骤** - 尽可能详细
3. **预期行为** - 您认为应该发生什么
4. **实际行为** - 实际发生了什么
5. **环境信息** - 操作系统、Python 版本、包版本等
6. **相关截图或日志**（如适用）

### 提出功能请求

当提出功能请求时，请包含：

1. **功能描述** - 您希望添加什么功能
2. **使用场景** - 为什么需要此功能
3. **实现建议** - 如有想法，可提供实现方案

### 代码贡献

#### 1. Fork 项目

点击 GitHub 页面上的 "Fork" 按钮创建项目的分支。

#### 2. 创建功能分支

```bash
git checkout -b feature/amazing-feature
```

或

```bash
git checkout -b bugfix/issue-description
```

#### 3. 提交更改

```bash
git add .
git commit -m 'Add some amazing feature'
```

#### 4. 推送到分支

```bash
git push origin feature/amazing-feature
```

#### 5. 创建 Pull Request

在 GitHub 上创建 Pull Request。

## 代码规范

### Python 规范

- 遵循 PEP 8 编码规范
- 使用有意义的变量和函数名
- 添加适当的类型注解
- 编写清晰的文档字符串

### Git 提交规范

- 使用清晰、简洁的提交信息
- 遵循格式：`type(scope): description`
  - `type`: feat, fix, docs, style, refactor, test, chore
  - `scope`: 受影响的模块或功能
  - `description`: 简洁的描述

## 开发指南

### 添加新功能

1. **理解现有架构**：熟悉四个核心组件的交互方式
2. **编写测试**：为新功能编写单元测试
3. **文档更新**：更新相关文档
4. **代码审查**：确保代码质量和一致性

### 修复 Bug

1. **添加测试**：首先添加测试用例复现 Bug
2. **修复问题**：编写代码解决问题
3. **运行测试**：确保所有测试通过
4. **文档更新**：如需要，更新相关文档

### 代码审查清单

提交 Pull Request 前，请检查：

- [ ] 代码遵循项目编码规范
- [ ] 新功能有足够的测试
- [ ] 文档已更新
- [ ] 代码没有明显的性能问题
- [ ] 所有测试通过
- [ ] 提交信息清晰、规范

## 项目结构

```
academic-literature-toolkit/
├── README.md
├── LICENSE
├── CONTRIBUTING.md
├── requirements.txt
├── skills/
│   ├── references-seacher/     # 检索指令生成器
│   ├── PICOS-catcher/         # PICOS框架提取器
│   ├── scholar-crawler/       # 学术文献爬虫
│   └── PICOS-screener/        # 文献筛选器
└── examples/
```

## 技术栈

- **Python** 3.8+
- **Semantic Scholar API** - 主要学术搜索引擎
- **Google Scholar** - 补充搜索源
- **pandas** - 数据处理
- **BM25算法** - 相关性评分
- **PRISMA流程** - 文献筛选标准

## 测试

运行测试套件：

```bash
# 运行所有测试
python -m pytest

# 运行特定模块测试
python -m pytest tests/test_module.py
```

## 问题和疑问

如果您有任何问题或需要帮助：

1. 查看现有 Issues 和 Pull Requests
2. 创建新 Issue
3. 在 Discussion 区域提问

## 特别感谢

我们感谢所有为项目做出贡献的人，无论贡献大小。您的努力使这个项目变得更好！

---
*此贡献指南基于最佳实践制定，如有建议，请随时提出。*