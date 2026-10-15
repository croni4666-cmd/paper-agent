# paper-agent 使用指南

本指南介绍常见的本地文献工作流：检索、整理参考文献、处理有权访问的论文，以及生成综述或稿件草稿。检索、下载、补全元数据和同步等命令可能会连接外部服务；paper-agent 不会对生成的综述提供科学有效性认证。

网关记账及 v3 到 v4 的迁移说明见 [v4 网关操作与迁移指南](gateway-v4.md)。要查看当前安装版本支持的命令和参数，请运行 `pa --help` 或 `pa <命令> --help`。

## 1. 安装

需要 Python 3.10 或更高版本。在本地克隆的仓库目录中运行：

```console
python -m pip install -e .
pa --version
pa --help
```

基础安装可用于核心 CLI 流程。部分集成和可选功能需要额外依赖或凭据；只安装实际需要的扩展，切勿将 API 密钥、访问令牌或私密配置提交到代码仓库。

## 2. 检索并保存参考文献

检索支持的学术元数据来源，并将 BibTeX 保存供后续步骤使用：

```console
pa search "人工智能素养" --year-min 2020 --limit 20 --format bibtex -o refs.bib
```

需要机器可读的检索结果时，可保存 JSON（默认格式）：

```console
pa search "人工智能素养" --year-min 2020 --limit 20 -o results.json
```

使用 `--engine` 选择来源，使用 `--year-min` / `--year-max` 限制发表年份，使用 `--limit` 限制每个来源返回的记录数。检索结果受各来源覆盖范围和可用性影响；在使用前请核对记录，并按需要去重和修正。部分来源的完整访问或元数据补全可能需要 API 密钥。可运行 `pa keys --help` 查看密钥管理功能。

## 3. 获取有权访问的论文

获取单篇论文时，根据论文来源和你的访问权限选择渠道。例如，适用时可优先尝试 Unpaywall 或 arXiv：

```console
pa fetch 10.1234/example --prefer unpaywall --output-dir ./pdfs
pa fetch 10.48550/arXiv.2401.01234 --prefer arxiv --output-dir ./pdfs
```

以上 DOI 仅为示例。运行 `pa fetch --help` 查看支持的渠道、缓存、超时和来源选择。下载流程可能会访问多个服务；请仅使用你获准使用的来源，并遵守服务提供方、出版方及所在机构的条款。

批量处理时，paper-agent 接受 BibTeX 文件：

```console
pa fetch-batch refs.bib --out-dir ./pdfs --skip-existing --report fetch-report.md
```

批量运行前，请先阅读 `pa fetch-batch --help`，了解其渠道和行为。下载失败不代表无法通过图书馆或所在机构获取论文。

## 4. 从本地 PDF 生成综述草稿

将你获准处理的 PDF 放入目录，然后生成 Markdown 工作草稿：

```console
pa review ./pdfs --output literature-review.md
```

输出内容是待人工核验的草稿。请对照论文原文核查引文、出处、提取的论断、研究特征和排除项。系统综述的筛选决定与 PRISMA 数量必须反映真实的审查过程，工具无法替你认证这些信息。

也可以根据已核实的数量生成 PRISMA 流程图：

```console
pa prisma --identified 100 --after-screening 30 --after-eligibility 20 --included 15 -o prisma.md
```

## 5. 根据自己的稿件生成排版文件

先根据 BibTeX 创建提纲，再编辑成自己的稿件、检查引用键并生成输出文件：

```console
pa scaffold refs.bib --out skeleton.md
# 编辑 skeleton.md，撰写并核验稿件内容。
pa cite-check refs.bib skeleton.md --strict
pa build refs.bib --skeleton skeleton.md --out manuscript.docx
```

`build` 会排版你提供的 Markdown 文稿，不会替你撰写或验证学术论证。输出格式取决于已安装工具；生成 PDF 可能需要额外的 PDF 引擎，详情见 `pa build --help`。

## 6. 按主题管理项目

项目可以将某一主题的参考文献及相关本地状态放在一起：

```console
pa project init "ai-literacy" --title "AI literacy"
pa project status "ai-literacy"
pa project --help
```

各子命令支持的操作不同。导入或删除数据前，请运行 `pa project --help` 及 `pa project <子命令> --help` 查看选项。

## 7. 可选集成

Zotero 和 Obsidian 均为可选集成。它们可能会在本地项目之外读取或写入数据；执行写入前，请核对目标文库或 vault 以及具体命令参数。

```console
pa zotero --help
pa zotero check --help
pa zotero push --help
pa obsidian --help
```

Zotero API 操作需要 `ZOTERO_API_KEY`、`ZOTERO_LIBRARY_ID` 等凭据。请在安全的本地配置中保存密钥，不要把真实凭据写入 shell 历史、示例、报告或版本控制。

## 8. v4 网关记账

网关在本地评估请求，并使用事务型 SQLite 日志记录预留额度；网关本身不会调用外部服务。查看现有日志可使用 `status`、`doctor` 和 `audit`。迁移旧版 v3 账本前，请先阅读[迁移指南](gateway-v4.md)。不得让 v3 与 v4 写入进程同时操作同一记账域。

## 故障排查

- **找不到 `pa` 命令：** 激活安装了 paper-agent 的 Python 环境，或改用 `python -m pa_cli`。
- **来源无结果或报错：** 查看输出中的来源状态，稍后重试、缩小查询范围或改选其他来源。网络、配额和来源 API 都可能变化。
- **下载失败：** 核对 DOI，并尝试你获准使用的其他渠道，包括图书馆或机构访问途径。
- **命令选项不一致：** 当前安装版本输出的 `--help` 是该版本的准确说明。
- **存在 v3 网关账本：** 停止旧版本写入进程，按 [gateway-v4.md](gateway-v4.md) 的备份与迁移步骤处理后，再使用 v4 评估请求。

## 验证范围

真实语料、人类标注和依赖语料的评估目前无限期搁置。自动化检查与生成的测试样例只能支持软件一致性判断，不能证明摘要、排序、论断提取或科学结论准确。
