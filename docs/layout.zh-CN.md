# 安装到哪里

HSS 由宿主传入持久研究空间，例如 Windows 的 `D:\Research` 或 Linux 的 `/srv/research/users/alice`。这两个路径只是示例；实际路径由 Qiushi Engine、Origo 或其他宿主决定。研究空间与产品可执行程序的安装位置可以不同。

默认使用研究空间内的 `System`。如果其中已有小写 `system`、没有 `System`，就沿用小写目录。下面用 `<研究空间>/system` 表示这个位置。

| 内容 | 位置 | 何时写入 |
|---|---|---|
| Python 环境、Node 软件、原生程序 | `system/env/hss/software/<组件ID>/` | 准备所选模块且没有可复用的环境时 |
| R 包 | `system/env/hss/R/library/` | 已连接 R，并准备相应组件时 |
| 模块选择与软件绑定 | `system/env/hss/selection.json`、`registry.sqlite` | 准备、绑定或移除模块时 |
| Skills | `system/skills/hss-*/SKILL.md` | 准备相应模块时 |
| 知识指南 | `system/knowledge/hss/` | 准备相应模块时 |
| 工作流 | `system/workflows/hss/` | 准备相应模块时 |
| 提示词 | `system/prompts/hss/` | 准备相应模块时 |
| Origo 直接导入的环境插件 | `system/env/hss-research/` | 使用产品仓库导入时 |
| 可移动插件包 | 显式导出位置，例如 `system/plugins/hss/` | 调用 `export` 时 |
| MCP 配置 | 上述插件包中的 `mcp.json` | 导出插件包时，之后由宿主登记 |
| 本地知识索引 | `system/databases/hss/research.sqlite` | 调用 `index` 时 |
| 软件包缓存 | `system/cache/hss/pip/`、`npm/` | 安装相关组件时 |
| 研究项目 | 显式指定位置，例如 `Projects/community-study/` | 创建项目、加入材料或执行研究时 |

`system/mcp/hss` 是可映射的资源区域，当前安装器不会自动把 MCP 配置写入该目录。宿主可以从插件包中的 `mcp.json` 读取配置并登记到自己的 MCP 管理位置。

## 领域组合如何落地

领域、方向和模块构成浏览与选择关系。依赖解析后，每个实际组件、知识文件和 Skill 只准备一份；不会为经济学、社会学、教育学各复制整套统计环境。

例如同时选择访谈研究组合和政策研究组合，两者共同使用的研究引导会共享；各自需要的定性分析资源和统计组件分别加入上述区域。安装器把组合展开成模块，再根据模块的组件需求复用或准备环境。已有 SeedEnv 解释器满足要求时，直接记录其原位置，不移动或复制它。

Python 环境中的解释器位于 Linux 的 `bin/python` 或 Windows 的 `Scripts/python.exe`；宿主使用返回的命令路径执行任务。模块移除时，共享资源和外部解释器继续保留。移除后显式选择 `--prune` 可清理不再使用的托管软件目录；共享 R 包库保留。

目录浏览和安装计划不会创建研究空间。HSS 本体携带轻量目录和研究资源，便于浏览；所选模块的软件依赖在准备时安装。大型语料、模型与外部数据库内容不会随全部目录自动下载。研究材料由项目持有，外部服务通过相应连接器访问。

## 项目自己的内容

`hss project <项目路径>` 创建研究说明和计算任务文件，以及 `materials/`、`data/`、`analysis/`、`results/`、`writing/` 等项目目录。原始访谈、史料、问卷数据、分析输出与论文属于具体项目，不放进共享软件环境。

执行研究时，输出目录也由调用者明确指定：

```bash
hss --space /research prepare bundle:interview-study --resources-only
hss project /research/Projects/community-study --title "城市社区参与研究"
hss --space /research export bundle:interview-study --output /research/System/plugins/hss
```

宿主可以通过 JSON 接口的 `space` 和 `layout` 改写资源区域，例如保持现有的小写目录，或把软件和缓存放到容量更大的磁盘：

```json
{
  "action": "plan",
  "space": "D:/Research",
  "selections": ["bundle:interview-study"],
  "layout": {
    "env": "E:/ResearchSoftware/hss",
    "skills": "system/skills",
    "cache": "E:/ResearchCache/hss"
  }
}
```

相对路径基于研究空间，绝对路径直接使用。未设置的区域按默认布局解析。多用户部署由宿主为不同用户传入各自的研究空间；需要共享已有环境时，再通过解释器绑定实现复用。

Origo 通过仓库源导入根目录 `plugin.json`，会将插件放入 `System/env/hss-research`，再由插件中的 MCP 服务准备所选组件。该流程已使用产品真实插件加载代码完成安装与调用。插件源码与 `System/env/hss` 中的软件和状态分别存放。TypeScript 工作台也可单独运行或嵌入产品现有界面。
