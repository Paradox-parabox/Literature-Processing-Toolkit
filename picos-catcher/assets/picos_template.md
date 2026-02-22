# PICOS筛选准则

## 文档元信息

| 项目 | 内容 |
|------|------|
| 来源文档 | {source_file} |
| 提取时间 | {timestamp} |
| 研究主题 | {research_topic} |

---

## PICOS框架

### P (Population) - 研究对象

**核心对象**：
- {core_population}

**扩展对象**：
- {extended_population}

**排除对象**：
- {excluded_population}

---

### I (Intervention) - 研究方法

**核心方法**：
- {core_intervention}

**相关方法**：
- {related_intervention}

**排除方法**：
- {excluded_intervention}

---

### C (Comparison) - 对比参照

**主要对比**：
- {primary_comparison}

**次要对比**：
- {secondary_comparison}

---

### O (Outcomes) - 研究产出

**核心产出**：
- {core_outcomes}

**相关产出**：
- {related_outcomes}

---

### S (Study design) - 研究类型

**接受类型**：
- [ ] 数值模拟
- [ ] 实验研究
- [ ] 理论分析
- [ ] 综述文章
- [ ] 其他：{other_types}

**排除类型**：
- {excluded_types}

---

## 纳入标准

### 必须满足（全部）

- [ ] P: 研究对象符合核心范围
- [ ] I: 采用核心方法或相关方法
- [ ] O: 涉及核心产出或相关产出
- [ ] S: 研究类型在接受范围内

### 可选满足（至少一项）

- [ ] 研究对象为扩展范围
- [ ] 采用创新方法
- [ ] 提供重要对比数据
- [ ] 高引用或高影响力

---

## 排除标准

满足以下任一条件即排除：

1. **研究对象不符**：{p_exclusion}
2. **研究方法不符**：{i_exclusion}
3. **研究类型不符**：{s_exclusion}
4. **其他排除**：{other_exclusion}

---

## 筛选建议

### 定量指标

| 指标 | 建议阈值 | 说明 |
|------|----------|------|
| BM25_Score | > {bm25_threshold} | 相关性筛选 |
| Year | >= {year_threshold} | 时效性要求 |
| Citations | >= {citation_threshold} | 影响力要求 |

### 筛选流程

```
1. 初筛（标题+摘要）
   - 按纳入标准快速判断
   - 标记：Yes / Maybe / No

2. 复筛（Maybe论文）
   - 阅读摘要全文
   - 必要时查看全文

3. 终筛（全文）
   - 阅读全文确认
   - 记录排除原因
```

---

## 附录：关键词列表

### 纳入关键词
{include_keywords}

### 排除关键词
{exclude_keywords}

---

*本准则由PICOS-catcher自动生成，请根据实际情况调整。*
