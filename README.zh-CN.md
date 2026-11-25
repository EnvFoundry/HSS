# HSS

**Humanities and Social Sciences：按研究任务组合的人文社会科学环境。**

[English](README.md) · [完整目录](docs/catalogue.md) · [使用方式](docs/usage.md) · [系统接入](docs/hosts.md) · [安装位置](docs/layout.zh-CN.md)

HSS 将研究知识、方法、软件、Skills、提示词、工作流和文献数据连接组织成可选择、可安装、可复用的研究能力。领域和方向提供浏览入口，同一个模块可以服务多个领域。软件依赖按共享组件准备，研究者可以选择整个领域、一个方向、一个研究组合或几个具体模块。

它包括 14 个研究领域与一个公共研究入口、60 个方向、91 个共享模块、8 个研究组合，以及 19 份知识指南、8 个 Skills 和 7 条工作流。方法参考收录 40 个方法族、371 张方法卡和 241 个任务分支；其中 32 个分支连接了本地统计实现，其余明确说明使用外部软件还是开展研究论证。这里的分类用于导航，允许跨学科重叠。

## 当前实现范围

| 部分 | 当前状态 |
|---|---|
| 领域、方向、模块 | 已建立导航、共享依赖和研究资源映射；91 个模块并不等于 91 套独立实现的分析软件 |
| 环境准备 | 已实现选择、依赖展开、解释器复用、资源安装、移除和路径映射 |
| 内置计算 | 24 项统计操作、10 项材料与采集操作；具体输入和适用范围见[执行范围](docs/execution.md) |
| 更广泛的方法 | 371 张方法卡、外部软件配方与 11 个 R 脚本生成器；尚未逐项完成外部软件安装与数值执行实测 |
| Agent 与产品接口 | Python、CLI/JSON、MCP、插件导出、TypeScript 客户端与模块选择组件已实现 |
| 正式产品集成 | Qiushi Engine、Origo 等宿主中的下载入口、任务调度与配置注册尚待接入 |

这是可运行、可扩展的人文社科环境基础。全部源码公开，不表示所有学科的问题、方法与研究过程都已实现自动执行。各模块的 `operations`、`r_exports`、软件组件和研究指导分别说明其能力来自哪里。

## 语言与职责

| 职责 | 当前实现位置与语言 |
|---|---|
| 环境准备、研究任务、CLI 与 MCP | `src/hss/`，Python |
| 产品客户端、模块选择界面 | `packages/client/src/`，TypeScript；附编译后的 JavaScript |
| 安装记录、知识索引、文献库 | SQLite；SQL 定义与查询位于 `state.py`、`knowledge.py`、`materials.py` |
| 外部统计方法 | `r_export.py` 生成 R 代码，交给对应 R 环境执行 |
| Rust、C/C++ | 当前没有自写组件；宿主执行层与上游软件保持各自实现，不因接入 HSS 而重写 |

源码语言比例反映仓库自身代码，不能代表其可连接的软件生态或各模块的完成程度。

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
hss project /research/Projects/new-study --title "城市社区参与研究"
```

Windows 可使用 `D:\Research` 等路径；命令不在 PATH 时改用 `python -m hss`。模块可以单独安装，也可使用 `field:economics`、`direction:领域ID/方向ID`、`bundle:policy-study`。`all` 选择全部模块的默认实现，替代后端仍单独选择。

## 研究与执行

研究探索入口接收现象、问题、目标、范围和可获得材料，返回可比较的研究路径。Agent 根据相关知识和工作流继续与研究者讨论，形成问题、概念、对象、材料、设计、方法与输出相互衔接的方案。随后，计算任务以明确的 `study.json` 执行；解释、定性分析和理论工作沿各自工作流展开。

已实现的能力包括统计描述、随机实验、工具变量、AIPW、双重机器学习、两期双重差分、合成控制、回归、预测、降维、聚类、主题、网络、空间统计、研究综合，以及语料整理、文本校勘、关键词语境、访谈编码、编码一致性、论证结构、问卷和简单浏览器行为任务。更完整的方法通过所选 Python/R 软件及桌面或服务连接完成。

研究输出包含实际计算结果、数据表、材料定位、图文材料或研究工具。论文写作由宿主 Agent 使用这些输出完成；HSS 本身不内置语言模型，也不把空白论文框架当作已完成论文。

## 文件组织

| 内容 | 研究空间中的默认位置 |
|---|---|
| 软件、解释器与绑定 | `System/env/hss` |
| Skills | `System/skills/hss-*` |
| 知识指南 | `System/knowledge/hss` |
| 工作流与提示词 | `System/workflows/hss`、`System/prompts/hss` |
| 插件包 | 显式导出到 `System/plugins/hss` 等位置 |
| 知识数据库 | `System/databases/hss` |
| 下载缓存 | `System/cache/hss` |
| 数据、材料、分析与论文 | 显式指定的 `Projects/项目名` 等项目目录 |

这些目录可以由宿主映射。已有小写 `system` 时继续使用小写目录。HSS 负责资源组合和软件准备，Qiushi Engine、Origo 或其他宿主负责账户、任务调度、模型调用和产品界面。

接入包括 Python、CLI/JSON、MCP、可移动插件包和 TypeScript 选择界面。接口可以供不同 Agent 和 Harness 使用；特定产品的完整部署情况见[执行范围](docs/execution.md)。
