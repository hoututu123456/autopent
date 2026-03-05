一款由大语言模型（LLM）驱动的自动化渗透测试框架。它结合了现代 AI 技术（RAG、ReAct）与传统安全工具，能够按照标准的渗透测试流程（信息收集 -> 漏洞探测 -> 漏洞利用 -> 权限维持 -> 横向移动）自动执行任务。

本项目旨在辅助安全研究人员和渗透测试工程师，通过 AI 自动化执行繁琐的扫描和探测任务，提高工作效率。(当前产品默认不支持英文)

## 核心功能

*   **AI 驱动的决策引擎**: 基于 ReAct 范式的智能 Agent，能够根据当前环境和任务状态自主规划下一步行动。
*   **双模型并行策略**: 采用云端AI+本地AI双模型运行模式，云端主AI与本地副AI协同工作，进一步强化AI Agent能力。
*   **自我学习与进化**: 具备互联网搜索能力，遇到未知漏洞时可自动搜索最新 CVE 详情与 Exploit，并将其沉淀到本地知识库中，实现能力的持续进化。
*   **Agent RAG (检索增强生成)**: 采取Agent RAG检索增强生成架构，产品内置丰富的渗透测试知识库（MITRE ATT&CK, OWASP, CVE 详情等），AI 在决策时可实时检索相关知识，确保操作的专业性和准确性。
*   **MoE (混合专家模型架构)**: 采用MoE混合专家模型架构，让AI自主更改当前角色，以适应目标环境的实时变化。
*   **广泛的工具集成**: 支持 100+ 种常见安全工具（Nmap, SQLMap, Metasploit, Nuclei, Hydra 等），并通过 YAML 配置文件灵活管理。
*   **自动化证据收集**: 在发现关键风险（如后台登录页、Webshell）时，自动截图并保存证据；支持 OCR 文字提取，方便后续分析。
*   **标准化工作流**: 严格遵循渗透测试杀伤链（Kill Chain），确保测试过程的逻辑性和完整性。
*   **Web 可视化界面**: 提供直观的 Web UI，实时展示任务进度、工具输出、发现的漏洞以及生成的报告。
*   **自动化报告**: 测试结束后自动生成详细的 HTML 渗透测试报告。
*   **Docker 友好**: 支持在 Docker 容器中运行，易于部署和隔离。
*   **多AI模型支持能力**: 支持用户自行选择DeepSeek&ChatGPT模型。
*   **基于Kali Linux系统CLI**: 通过基于Kali Linux系统的CLI命令行运行，能无限制调用Kali Linux系统原生内置工具，彻底解决工具调用失败的问题。

## 技术栈

*   **后端**: Python 3.12+, FastAPI, Uvicorn
*   **AI/LLM**: OpenAI API (支持 GPT-4, DeepSeek 等), LangChain 思想
*   **向量数据库**: ChromaDB (用于 RAG 知识库)
*   **嵌入模型**: Sentence Transformers (all-MiniLM-L6-v2)
*   **前端**: HTML5, CSS3, JavaScript (原生)

## 前置要求

*   **操作系统**: 推荐 Linux (尤其是 Kali Linux)，Windows (需手动配置工具路径)
*   **Python**: >= 3.12
*   **外部工具**: 项目依赖多种安全工具（如 `nmap`, `sqlmap` 等），请确保这些工具已安装并在系统 PATH 中，或通过 Docker 运行。

## 快速开始

### 1. 克隆项目(支持国外GitHub与国内Gitee)

```bash
git clone https://github.com/JXJZJWHCM/AutoPentestAI.git
git clone https://gitee.com/APATeam/AutoPentestAI.git
cd AutoPentestAI
```

### 2. 安装依赖

建议使用虚拟环境：

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 3. 配置环境

复制示例配置文件并填写必要的 API Key：

```bash
cp .env.example .env
```

编辑 `.env` 文件，填入你的 LLM API Key (OpenAI 或 DeepSeek) 以及其他配置：

```ini
# .env 示例
AI_PROVIDER=deepseek  # 或 openai
DEEPSEEK_API_KEY=sk-xxxxxxxxxxxx
# OPENAI_API_KEY=sk-xxxxxxxxxxxx
AI_MODEL=deepseek-reasoner
```

### 4. 运行项目

启动后端 API 服务：

```bash
python src/main.py
```

或者使用 uvicorn 直接运行：

```bash
uvicorn src.api.server:app --host 0.0.0.0 --port 8000 --reload
```

产品也支持通过一键启动脚本启动：

```bash
./run-Kali专用启动脚本.sh
./run-Linux通用启动脚本.sh
```

### 5. 访问 Web UI

服务启动后，打开浏览器访问：

`http://localhost:8000/web/index.html`

## 进阶使用

*   **工具指令**: 详细的工具使用说明和参数参考，请阅读 [config/tool_instructions.md](config/tool_instructions.md)。
*   **添加自定义工具**: 可在 `config/tools/` 目录下参考现有 YAML 文件添加新的工具配置。

## 项目结构

```text
AutoPentestAI/
├── config/              # 配置文件
│   ├── tools/           # 工具定义 (YAML)
│   └── ...
├── data/                # 数据存储
│   ├── knowledge/       # 知识库文档 (Markdown)
│   ├── vulndb/          # 漏洞数据库
│   └── ...
├── src/                 # 源代码
│   ├── agent/           # AI Agent 核心逻辑
│   ├── api/             # FastAPI 接口
│   ├── tools/           # 工具执行与管理
│   ├── utils/           # 通用工具函数 (RAG, 报告生成等)
│   └── main.py          # 程序入口
├── web/                 # Web 前端资源
├── tests/               # 单元测试
├── requirements.txt     # Python 依赖
└── .env                 # 环境变量
```

## 免责声明

本工具仅供**授权的安全测试**和**教育研究**使用。

*   请勿在未获授权的目标上使用本工具。
*   开发者不对因使用本工具造成的任何非法行为或损害承担责任。
*   使用本工具即表示您同意遵守当地法律法规。

## 贡献

*   感谢APA安全团队成员的鼎力合作。
*   感谢CyberStrikeAI、KaliGpt、Hexstrike、Autopt 、MPET、LeakDetector、RedAgent、Vulhub、AI-Vanguard、Nora等产品提供的技术灵感与部分文件内容支持。
*   欢迎您提交 Issue 和 Pull Request！如果您有新的工具集成建议或功能想法，请随时告知。

## 许可证

*   本产品采用并遵循麻省理工学院的MIT许可 [MIT License](LICENSE) ，但禁止用于商业用途

## 联系我们

*   **邮箱**: jxjzjwhcm@foxmail.com或201566269@qq.com
*   **微信**: phenomenal233或A15350000292
*   **项目仓库(国外GitHub)**: https://github.com/JXJZJWHCM/AutoPentestAI
*   **项目仓库(国内Gitee)**: https://gitee.com/APATeam/AutoPentestAI
*   **团队官网**: https://www.apateam.top
*   **团队名称**: APA安全团队
*   **团队产品公开交流群**: 
*   ![微信图片_20260302134831_156_158](https://github.com/user-attachments/assets/266913b9-1d46-4609-a14b-29176314efa2)


## 其他

*   **项目状态**: 持续开发迭代中
*   **最新开源版本**: 1.2.0(1.3.0正在开发测试中，后续会开源至GitHub与Gitee)
*   **最新商业闭源版本**: 2.0.0商用专业版(已经开发完成，可以通过邮箱、官网、微信或公开群联系我们)
*   **团队其他产品**: 夜曲自动化信息收集平台、C2框架等产品正在开发中。
