# 批量阅读协议

## 先建清单再阅读

扫描文件夹后生成 `reading-manifest.json`。默认仅包含 PDF；除非用户明确要求递归，否则只扫描顶层。默认按文件名自然排序，使 `2.pdf` 排在 `10.pdf` 前。

每项至少包含：

```yaml
order:
source_path:
sha256:
title_guess:
selection: included | excluded | uncertain
selection_reason:
mode: deep | coarse
status: pending | in_progress | completed | skipped | download_failed | read_failed
read_scope:
output_path:
error:
```

## 筛选

支持精确文件名、文件名通配符、子文件夹、作者、年份、会议期刊、题目关键词、研究主题和与研究画像的相关性。

- 文件名或路径条件可确定性筛选。
- 作者、年份和出版物优先使用已核验元数据。
- 主题类别或相关性筛选先做题目/摘要级预扫描，结果分为 `included`、`excluded`、`uncertain`。
- `uncertain` 不得自动丢弃；长批次开始前展示给用户确认。
- 记录每个排除理由，不删除或移动源文件。

## 去重

依次使用文件 SHA-256、规范 DOI、规范化题目加年份判断重复。哈希相同可自动去重；仅题目近似时标记 `uncertain_duplicate`，不要自动删除。

## 续跑与故障隔离

- 开始一篇前写 `in_progress`，成功写 `completed`，异常写明确失败状态和原因。
- 已完成且输出存在的项默认跳过；用户要求重做时才覆盖，覆盖前保留旧产物或使用新版本名。
- 单篇失败不终止整个批次。
- 每完成一篇就保存清单和产物，不把全部状态只保留在对话上下文中。
- 批量精读每篇使用独立目录；批量粗读维护同一份完整行数据，逐篇更新版本化工作簿，保留旧产物和人工修改。
- 清单脚本保留逐篇模式和语义筛选决定；改变阅读模式或语义条件时应明确更新这些字段，不能假设重新扫描已完成重新判断。

## 进度汇报

对较长批次定期报告 `已完成/总数`、当前论文和新增失败项。结束时分别统计全文、部分章节、摘要、元数据、失败和跳过数量。
