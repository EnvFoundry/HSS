# HSS

**Humanities and Social Sciences：按研究任务组合的人文社会科学环境。**

[English](README.md) · [完整目录](docs/catalogue.md) · [使用方式](docs/usage.md) · [系统接入](docs/hosts.md) · [安装位置](docs/layout.zh-CN.md)

HSS 将研究知识、方法、软件、Skills、提示词、工作流和文献数据连接组织成可选择、可安装、可复用的研究能力。领域和方向提供浏览入口，同一个模块可以服务多个领域。软件依赖按共享组件准备，研究者可以选择整个领域、一个方向、一个研究组合或几个具体模块。

它包括 14 个研究领域与一个公共研究入口、60 个方向、91 个共享模块、8 个研究组合，以及 19 份知识指南、8 个 Skills 和 7 条工作流。方法参考收录 40 个方法族、371 张方法卡和 241 个任务分支；其中 32 个分支连接了本地统计实现，其余明确说明使用外部软件还是开展研究论证。这里的分类用于导航，允许跨学科重叠。

宿主包附带[仓库维护的中英文说明与资源位置](src/hss/data/environment.json)。宿主将 `package_path` 对应到实际安装目录；安装状态、软件位置和运行中的任务继续由各自原有的管理服务负责。刷新这些说明不会安装科研软件。

## 研究过程

工作台把环境选择、研究方案、任务执行和论文组织连接起来。每个方向都能展开为包含材料要求、研究输出、知识指南、工作流、软件和操作输入的研究路径。研究者与宿主 Agent 共同确定具体方案，HSS 执行其中明确的计算与材料处理任务，文稿接口将实际结果、正文与参考文献组织成 Markdown。

目前提供 41 种研究任务操作：24 种统计计算、13 种材料与原生文本操作，以及 SQL、R 分析、项目代码和已连接程序执行。43 个共享软件与服务组件按选择准备；同一个研究任务图可组合不同语言。371 张方法卡用于检索和方法设计，具体执行调用相应的内置操作或上游软件。

仓库根目录的 `plugin.json` 可直接供 Origo 的仓库导入入口识别。已使用 Origo 的实际插件加载代码完成安装和 MCP 调用，识别了 8 个 Skill 与研究服务。其他 Agent、Harness 和研究系统通过 MCP、CLI/JSON 或 TypeScript 客户端接入。

## 语言与职责

| 语言 | 实际功能 | 源码 |
|---|---|---|
| TypeScript | 类型化客户端、模块选择器、四步研究工作台、流式进度 | `packages/client/src/` |
| Rust | UTF-8 语料统计、关键词语境、字符与字节位置 | `src/hss/data/native/corpus.rs` |
| C++17 | Unicode 文本的精确编辑距离与校勘片段 | `src/hss/data/native/alignment.cpp` |
| SQL | 环境记录、知识索引、文献库及研究数据的关系查询 | `src/hss/data/sql/`、`examples/sql/` |
| Python | 按需准备、环境复用、研究任务、统计分析、材料处理与 CLI/MCP | `src/hss/` |
| R | 11 种上游分析适配、实际模型拟合与结果输出 | `src/hss/r_export.py`、`external.py` |

## 使用

```bash
python -m pip install .
hss browse
hss search "访谈"
hss plan bundle:interview-study
hss --space /research prepare bundle:interview-study --resources-only
hss context interview-coding
```

仅安装 HSS 本体时，不安装整套统计软件。浏览目录不创建研究空间；未选择模块就不安装。去掉 `--resources-only`，才会准备所选模块的软件依赖，并优先复用已有解释器。R、桌面软件和外部服务缺失时，结果会列为待连接。

```bash
hss --space /research prepare descriptive-statistics randomized-experiment
hss --space /research run examples/randomized-study.json --output /research/Projects/example/results/run-01
hss run examples/materials-study.json --output /research/Projects/materials/results/run-01
hss project /research/Projects/new-study --title "城市社区参与研究" --select bundle:interview-study
```

Windows 可使用 `D:\Research` 等路径；命令不在 PATH 时改用 `python -m hss`。模块可以单独安装，也可使用 `field:economics`、`direction:领域ID/方向ID`、`bundle:policy-study`。`all` 选择全部模块的默认实现，替代后端仍单独选择。

## 研究与执行

研究探索入口接收现象、问题、目标、范围和可获得材料，返回可比较的研究路径。Agent 根据相关知识和工作流继续与研究者讨论，形成问题、概念、对象、材料、设计、方法与输出相互衔接的方案。随后，计算任务以明确的 `study.json` 执行；解释、定性分析和理论工作沿各自工作流展开。

已实现的能力包括统计描述、随机实验、工具变量、AIPW、双重机器学习、两期双重差分、合成控制、回归、预测、降维、聚类、主题、网络、空间统计、研究综合，以及语料整理、文本校勘、关键词语境、访谈编码、编码一致性、论证结构、问卷和简单浏览器行为任务。更完整的方法通过所选 Python/R 软件及桌面或服务连接完成。

研究输出包含实际计算结果、数据表、材料定位、模型文件和研究工具。宿主 Agent 使用这些输出撰写正文，`manuscript` 接口将正文、实际结果表与已有文献组织成可排版文稿。模型调用和研究者对方案的选择继续由宿主负责。

## 文件组织

| 内容 | 研究空间中的默认位置 |
|---|---|
| 软件、解释器与绑定 | `System/env/hss` |
| Skills | `System/skills/hss-*` |
| 知识指南 | `System/knowledge/hss` |
| 工作流与提示词 | `System/workflows/hss`、`System/prompts/hss` |
| Origo 环境插件 | `System/env/hss-research`，与软件和研究状态分开 |
| 可移动插件包 | 显式导出到 `System/plugins/hss` 等位置 |
| 知识数据库 | `System/databases/hss` |
| 下载缓存 | `System/cache/hss` |
| 数据、材料、分析与论文 | 显式指定的 `Projects/项目名` 等项目目录 |

这些目录可以由宿主映射。已有小写 `system` 时继续使用小写目录。HSS 负责资源组合和软件准备，Qiushi Engine、Origo 或其他宿主负责账户、任务调度、模型调用和产品界面。

## 图形工作台

```bash
node packages/client/server.mjs --space /research --python python
```

打开 `http://127.0.0.1:8787`。已有编译好的 JavaScript，运行不需要先构建前端。产品可直接嵌入 `<hss-workbench>`，使用自身的请求传输与任务系统。

Rust/C++ 是明确选择的后端：

```bash
hss --space /research prepare corpus-assembly text-collation --backend corpus-assembly=rust --backend text-collation=cpp
hss --space /research run examples/native/study.json --output /research/Projects/native/results
hss run examples/sql/study.json --output /research/Projects/sql/results
```

原生后端用已有 Rust/C++ 编译器生成本地程序；Windows 也支持 CMake 与 Visual Studio。普通材料处理仍可直接使用 Python 实现。R 使用所连接的 Rscript，按选择安装包。数据库账号、受许可材料和外部服务连接由具体研究空间提供。

[完整研究工作台用法](docs/workbench.md) · [执行操作与测试范围](docs/execution.md)
