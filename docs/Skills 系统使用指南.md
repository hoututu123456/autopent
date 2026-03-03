# Skills 系统使用指南

## 概述

Skills 文档用于为 AI 提供可检索的“战术动作/工具用法”。当前项目的运行时检索入口为 `search_knowledge`（RAG 语义检索；不可用时自动降级关键词检索），会扫描并索引：
- `data/skills`
- `data/knowledge`
- `data/vulndb`
- `data/playbooks`

## Skills 结构

当前项目以“顶层文件”为主进行管理：Skills 默认位于 `data/skills/` 下的 `.md/.txt` 文件（不是每个 skill 一个目录）。大量条目时建议维护一个“索引 Skill”（目录页）用于导航。

```
data/skills/
├── sql-injection-testing.md
├── xss-testing.md
└── ...
```

## Skill 文档格式

Skill 文件支持 YAML front matter（可选）：

```markdown
---
name: skill-name
description: Skill 的简短描述
---

# Skill标题

这里是skill的详细内容，可以包含：
- 测试方法
- 工具使用
- 最佳实践
- 示例代码
- 等等...
```

如果不使用 front matter，整个文件内容都会被作为 Skill 内容。

## 在角色中配置Skills

在角色配置文件中添加 `skills` 字段：

```yaml
name: 渗透测试
description: 专业渗透测试专家
user_prompt: 你是一个专业的网络安全渗透测试专家...
tools:
  - nmap
  - sqlmap
  - burpsuite
skills:
  - sql-injection-testing
  - xss-testing
enabled: true
```

`skills`字段是一个字符串数组，每个字符串是skill目录的名称。

## 工作原理

1. **内容维护（源文档）**：建议将技能文档在独立目录中结构化维护。
2. **运行时加载（RAG 索引）**：RAG 实际索引目录为 `data/skills`、`data/knowledge` 与 `data/vulndb`（递归索引 `**/*.md`）。
3. **UI 列表展示**：Web API 的 `GET /api/skills` 当前只列出 `data/skills` 顶层文件（不递归子目录），因此建议将可用技能以顶层 `.md` 的形式镜像到 `data/skills`。
4. **AI 使用方式**：当需要技能细节时，Agent 调用 `search_knowledge` 检索并引用相关片段，而不是通过独立的 `read_skill` 工具读取单个 skill 文件。

## 示例Skills

### sql-injection-testing

包含SQL注入测试的专业方法、工具使用、绕过技术等。

### xss-testing

包含XSS测试的各种类型、payload、绕过技术等。

## 创建自定义Skill

1. 在技能目录下创建新目录，例如`my-skill`
2. 在该目录下创建`SKILL.md`文件
3. 编写skill内容
4. 在角色配置中添加该skill名称

```bash
mkdir -p skills/my-skill
cat > skills/my-skill/SKILL.md << 'EOF'
---
name: my-skill
description: 我的自定义技能
---

# 我的自定义技能

这里是技能内容...
EOF
```

## 注意事项

- **重要**：运行时使用的是 `data/skills` 的内容，请确保新增/更新后同步到 `data/skills`，否则 UI 列表与 RAG 检索可能无法命中。
- Skill内容应该清晰、结构化，便于AI理解
- 可以包含代码示例、命令示例等
- 建议每个skill专注于一个特定领域或技能
- 建议在skill的YAML front matter中提供清晰的 `description`，帮助AI判断是否需要读取该skill
