# Obsidian 输出规范

## 目录

每篇论文一个目录，目录名优先使用安全的 `第一作者-年份-题目短名`：

```text
obsidian/
└── Author-Year-ShortTitle/
    ├── Author-Year-ShortTitle.md
    └── assets/
        ├── fig-01-method-overview.png
        ├── fig-02-main-results.png
        └── fig-03-ablation.png
```

文件名移除 Windows 非法字符，保持稳定，不覆盖同名旧笔记；冲突时增加 DOI 短码或版本号。

## Markdown

从 `assets/obsidian-paper-note-template.md` 复制结构并填充。默认用相对当前笔记的 Markdown 图片链接，避免不同论文中同名图片的 wikilink 歧义：

```markdown
![图 1：方法框架](assets/fig-01-method-overview.png)
```

同时写普通文本图注，保证脱离图片仍能理解图号、页面和用途。内部章节链接使用 Obsidian 兼容标题；不要依赖只能在特定主题中显示的 HTML/CSS。

“内嵌正文显示”与“图像二进制保存在 .md 文件内部”不同：标准交付是 `.md` 加相对路径附件，在阅读视图直接显示图片。把整篇目录放入 Obsidian 库即可保持引用。不要把 `assets` 当成让用户另行打开的图库，也不要只交付 `.md` 导致附件丢失。默认不用 Base64/data URI 冒充通用 Obsidian 支持；若用户明确要求单文件自包含，说明取舍并另提供其同意的 HTML/PDF 等格式。

方法框图放在整体框架/相应模块旁；仅公式的裁图放在损失函数旁。整页截图不是默认插图形式，裁剪与检查遵循精读工作流。不能用 Markdown 预览器未显示附件的现象推断 Obsidian 也不能显示；应核查相对链接和实际图片。

## 元数据

YAML 中数组使用合法 YAML 列表，空值保留为空，不写“未知”字符串。`source_file` 使用可追踪路径或 URL。`read_scope` 和 `source_status` 必填。

## 完整性检查

- Markdown 文件存在且 UTF-8 编码。
- 每个图片链接相对该 Markdown 文件解析后，指向实际存在的图片；若采用 wikilink，必须使用唯一且可解析的库内路径。
- 图片文件非空，名称唯一。
- 摘要原文与译文分开。
- 关键图均有原图号、页码和解释。
- 方法框图、损失公式均为合适的局部裁图，且在相应正文位置内嵌；逐张检查内容边界和可读性。
- 问题/贡献来自引言逻辑；相关工作有分类逻辑；方法有作者选型原因与预期效果；实验设置完整、结果按实际验证维度概述。
- 英文论文的选型原因/预期作用有对应英文原句和来源定位；无明确原句时保留未说明状态，不把中文分析回译成“原文”。
- 没有占位符、工具内部令牌或未完成的模板字段。
