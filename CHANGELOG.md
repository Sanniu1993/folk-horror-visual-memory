# CHANGELOG

记录每次逻辑/功能改动:改了什么、为什么、如何验证。最新在最上面。

---

## 2026-07-27

### 开源发布准备

- **改了什么**:重写 README(定位、现状横幅、功能、快速开始、已知局限、路线图)、新增 MIT LICENSE、
  docs/demo_frames.jpg 演示截帧;与姊妹仓库互相链接;.gitignore 排除 .idea / BGM 音乐文件。
- **为什么**:项目被社区推荐,需要可公开的仓库地址。
- **如何验证**:全工作区与 git 历史扫描无密钥(仅 .env.example 占位符);.env / 数据库 / 上传图未入库。

### 前端精简:去掉 Mock 模式 + 故事测试页,批量分析加实时进度

- **为什么**:检索改由 ai-horror-generator 通过 `/api/retrieve` 对接测试,本系统内的「故事测试」页
  不再需要;链路已跑通,默认走真实 AIHubMix VLM(不再需要 Mock 开关)。批量分析原来只在按钮上显示
  「分析中…」、结束弹 alert,过程无反馈,图多时不知进度。
- **改了什么**(纯前端 `frontend/index.html`):
  - 删除顶部「Mock 模式」勾选框及 `mock()`;`/api/analyze` 调用不再带 `?mock=`,一律真实分析。
  - 删除「④ 故事测试」标签页与其面板/JS(后端 `/api/story`、`/api/retrieve` 接口保留)。
  - 「批量分析」改为客户端逐张调用 `/api/analyze/{id}`:进度条 + 文案「分析中 X/N · 素材 #id」+
    当前卡片蓝框高亮 + 顶部统计实时刷新;完成显示汇总,4s 后自动收起进度条。
- **如何验证**:浏览器点批量分析,进度从「1/23 · #42」推进到「3/23 · #40」,当前卡片依次高亮,
  顶部「已分析」实时 0→2→… 递增;真实 VLM 落库(非 mock)。

### 新增:对外检索接口 `POST /api/retrieve`(供 ai-horror-generator 松耦合对接)

- **为什么**:ai-horror-generator 出图时想按分镜内容检索本库的真实民俗视觉素材来增强 prompt。
  需要一个稳定、只读、无副作用的对外接口,让它松耦合地调用(对方 fail-open,本服务可随时下线)。
- **改了什么**:新增 `POST /api/retrieve`,入参 `{query, top_k?}`,复用 `memory_mod.retrieve`
  做纯向量检索,返回 Top-K 记忆(含 title/description/各类 tags/region/era/score + 图片 url)。
  不触发理解/审核/写库,天然幂等只读。原有 `/api/story`(带 LLM 故事拆解)保持不变。
- **如何验证**:`curl POST /api/retrieve -d '{"query":"贵州 道士做法事镇尸","top_k":3}'`
  返回「道士驱邪现场 0.677 / 茅山道士 0.644 / 道士惊觉阴气 0.612」,visual_tags 齐全。

### 新增:「Memory 库」独立页,已入库图片与审核队列分离

- **原因**:已审核入库(reviewed)的图片一直混在「审核」页里,每次上传后都要在一堆已入库图中
  找待处理的;且没有地方集中查看/编辑/删除已入库的 Memory。
- **改了什么**:
  - 后端 `memory.list_materials` 增加 `exclude_reviewed` 参数;新增 `list_memories()`(联表返回
    已审核视觉记忆 + 文件路径)与 `delete_memory(memory_id, remove_material=True)`(删 visual_memory,
    默认连同 source_material 与图片文件一并删除;传 False 则退回 analyzed 状态)。
  - 新增路由 `GET /api/memories`、`DELETE /api/memory/{id}`;`GET /api/materials` 支持
    `exclude_reviewed`。
  - 前端新增「③ Memory 库」标签页:网格展示已入库图,点卡片编辑(复用审核弹窗 `renderReviewModal`),
    右上角 🗑 删除(带二次确认)。「审核」页改为只拉 `exclude_reviewed=true`,不再显示已入库图。
- **如何验证**:浏览器实测——「审核」页仅剩 4 张 analyzed(#19/#9/#5/#4),15 张 reviewed 全部移入
  「Memory 库」页并可点开编辑;`GET /api/memories` 返回 15 条、`materials?exclude_reviewed=true`
  返回 4 条,与 DB 中 status/reviewed 一致。

### 修复:单张上传点击无反应

- **原因**:后端 `/api/collect/upload` 正常(curl 实测能建素材);前端在未选文件时
  `if(!f)return` 静默返回,表现为"点了没反应"。
- **改了什么**:上传按钮改为点击即弹选图框,`<input type=file>` 隐藏并绑 `onchange` 自动上传,
  加实时状态反馈(上传中/成功素材号/失败原因)+ 可选「原始描述」字段。
- **如何验证**:curl 上传接口返回 material_id 正常;前端改为选图即传、有明确反馈。

### 新增 run.sh 一键启动 + 端口占用兼容

- **改了什么**:新增 `run.sh`——环境自检(.venv/.env)+ 端口占用自动顺延(默认 8100 起,最多探 20 个)
  + 打印实际地址;支持 `./run.sh <port>` 指定起始端口、`--kill` 结束占用进程。
- **为什么**:反复调试常遇端口被占,手动换端口烦。
- **如何验证**:占住 8100 后跑 `./run.sh`,自动顺延到 8101 并成功启动。

### VLM + Embedding 改走 AIHubMix

- **改了什么**:视觉理解与向量化从 DashScope 原生接口改为 **AIHubMix**(OpenAI 兼容聚合网关)。
  base_url→`https://aihubmix.com/v1`;key→`AIHUBMIX_API_KEY`;模型 ID 按 AIHubMix 实际命名:
  VLM=`qwen3-vl-plus`(批量可换 `qwen3-vl-flash`)、Embedding=`text-embedding-v4`。
  config 段 `dashscope`→`aihubmix`,providers/vlm、embed、memory 同步。
- **为什么**:用户统一走 AIHubMix 一个 key。
- **附带加固**:检索时按 query 维度过滤存量向量,避免 mock 哈希向量(1024)与真 embedding 维度
  不一致时 np.stack 崩溃。
- **如何验证**:核对 AIHubMix 模型列表拿到确切 ID;mock 链路复测收录→分析→审核→检索命中 3 条;
  无残留 dashscope 引用。真 key 调用待用户填 key 后验证。

### V1 脚手架落地:收录→理解→审核→Memory→检索→增强 全链路跑通

- **改了什么**:
  - 建项目 `folk-horror-memory`,独立 venv(Python 3.9)。
  - 后端 FastAPI + 6 模块:`collection`(批量收录)/`memory`(理解落库+审核定稿+检索)/
    `prompt_enhance`(综合增强)/`providers.{vlm,embed,llm}`。
  - 数据层:SQLite 三表(source_material / visual_memory / collection_log);向量以 float32 blob
    存入 visual_memory,检索用 numpy 暴力余弦 KNN。
  - VLM=Qwen-VL、Embedding=text-embedding-v3(均 DashScope 兼容接口),故事拆解=DeepSeek。
  - 前端单页三区(收录 / 审核 / 故事测试),带 Mock 开关。
- **关键决策**:
  - **不用 sqlite-vec**:macOS 系统 Python 3.9 的 sqlite3 禁用了扩展加载,改 numpy 暴力 KNN
    (500~数千条 <1ms,功能等价,零依赖坑),仍是轻量嵌入式、免 Docker。
  - **Embedding 改用 DashScope**(而非原计划本地 BGE):与 VLM 同 key、免装 2GB torch。
  - 全链路带**无 key 兜底**:VLM mock + 哈希 embedding,保证先跑通再接 key。
- **如何验证**:
  - 依赖安装通过;sqlite-vec 扩展加载失败 → 切 numpy KNN 验证 top-k 正确。
  - 端到端(mock):建 3 张测试图 → 批量导入 → 批量分析 → 审核入库 → 检索命中 3 条。
  - uvicorn 起服务,curl 实测 health/collect/analyze_batch/materials/review/stats 全通;
    reviewed 计数 0→3;前端页面正常返回。
- **未验证**:`/api/story`(故事拆解+增强)需 DeepSeek key;真 VLM/Embedding 需 DashScope key。
