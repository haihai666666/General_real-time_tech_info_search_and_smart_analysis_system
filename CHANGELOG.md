# Changelog（情报库 / LightRAG 工程）

本文件用于记录我们对“情报库 + LightRAG（GraphRAG/RAG）”工程做的每一次可感知升级，并同时维护下一阶段的升级路线（Roadmap）。

约定：
- 一个“升级点”指一个可独立交付、可验证、可回滚的能力增量（例如：接入 Rerank、引入 Hybrid 检索、增加评测集与指标）。
- 每完成一个升级点：在对应版本的“已完成升级点”里补一条记录，并在“升级路线”里把状态改为 Done。
- 版本号采用里程碑方式（v0.x），不强制语义化；以能力演进为主。

---

## 升级路线（Roadmap）

| 升级点 ID | 名称 | 目标产出（验收口径） | 影响范围 | 状态 |
|---|---|---|---|---|
| RERANK-01 | 启用 Rerank 精排 | 查询时对候选 chunk/document 进行 rerank；可开关；效果可对比 | 检索链路 | Done |
| RETRIEVAL-01 | Hybrid 检索（向量 + 关键词） | 同一查询同时走语义与关键词召回并融合；支持权重/TopK 配置 | 检索链路 | Done |
| CHUNK-01 | 切片策略基线固化 | 形成一致的 chunk 规则（长度、overlap、元数据）；重建索引可复现 | 离线/索引 | Done |
| STORAGE-01 | 向量存储迁移 (Milvus) | 将默认的 NanoVectorDB 替换为生产级的 Milvus 向量库 | 基础设施 | Done |
| QUERY-01 | Query Rewrite / Expansion | 支持对用户 query 改写/扩写（可配置）；提升召回率 | 在线查询 | Planned |
| KG-01 | 实体规范化与同义归并 | 同一实体跨文档对齐（别名、缩写、同名消歧）；减少图谱碎片化 | KG/实体层 | Planned |
| KG-02 | 关系抽取稳定化（Schema） | 关系类型白名单 + 置信度 + 证据跨度；支持版本迭代 | KG/关系层 | Planned |
| EVAL-01 | 评测集与指标闭环 | 建立小规模 goldset；跟踪 Recall@K / nDCG@K / 命中证据率 | 质量保障 | Planned |
| OPS-01 | 可观测与回溯 | 查询日志、命中证据、rerank 分数可追踪；异常可定位 | 工程化 | Planned |

---

## [Unreleased]

### 计划中（Next Up）
- QUERY-01：Query Rewrite / Expansion

### 已完成升级点（Done）
- CHUNK-01：切片策略基线固化（段落优先 + token 兜底；写入 doc_status 便于复现与回溯）
- RETRIEVAL-01：Hybrid 检索（混合向量与本地 BM25 召回，利用 jieba 和 rank_bm25 实现内存级 BM25 补充）
- STORAGE-01：向量存储迁移（采用 Milvus Lite 替换 NanoVectorDB）
- RERANK-01：启用 Rerank 精排（基于阿里云 qwen3-rerank，默认开启）

---

## v0.1（当前基线）

### 已具备能力
- 文档入库与基础检索链路已跑通（LightRAG 可用）
- 具备实体抽取与结构化结果落盘的流程雏形（NER + LLM 结构化）

### 已知问题（Backlog）
- 召回结果相关性不稳定，需要 rerank 精排拉高 Top-K 的有效性

---

## RERANK-01 设计要点（用于实现时对齐口径）

目标：在“粗排召回（TopK）”之后引入“精排（Rerank）”，并保证可控、可对比、可回滚。

建议落地口径：
- 开关：支持按查询参数启用/关闭（默认开启或按环境配置）
- 候选集：先召回 TopK（例如 50~200），再 rerank 到 TopN（例如 5~10）供生成
- 兼容长文：对 token 有上限的 rerank 模型启用 chunking（按模型能力决定）
- 记录证据：保留 rerank 前后排名与分数（用于评测与回溯）

实施清单（完成后在上方 Roadmap 将 RERANK-01 标为 Done）：
- 选定 rerank 提供商与模型（Cohere/vLLM、Jina、阿里云等其一）
- 打通 rerank 配置（环境变量/配置文件）并验证服务可用
- 在查询链路开启 rerank（可按查询参数 enable_rerank 控制）
- 增加最小相关性阈值（可选）与回溯信息（分数、重排前后名次）
- 用同一组问题对比：rerank 开/关的命中证据与回答质量差异

配置项（示例，仅列变量名与形态，避免提交密钥）：
```bash
RERANK_BINDING=cohere        # 或 jina / aliyun
RERANK_MODEL=...             # 例如 BAAI/bge-reranker-v2-m3 或 gte-rerank-v2
RERANK_BINDING_HOST=...      # 例如 vLLM/代理的 /v2/rerank 或阿里云 rerank endpoint
RERANK_BINDING_API_KEY=...   # 密钥不要入库

RERANK_BY_DEFAULT=True       # 默认是否启用（也可按查询参数覆盖）
RERANK_ENABLE_CHUNKING=false # rerank 模型 token 受限时启用
RERANK_MAX_TOKENS_PER_DOC=480
MIN_RERANK_SCORE=0.0         # 可选：低于阈值的候选直接丢弃
```

注意事项：
- 运行时环境变量优先级通常高于 `.env`；若出现“配置看起来对但不生效”，优先排查 OS 环境变量覆盖。

---

## RETRIEVAL-01 设计要点（简版）

目标：同一次查询同时走语义召回与关键词召回，提升“专有名词/型号/编号”命中率，并把候选统一交给后续精排与截断。

落地口径：
- 向量召回：沿用 chunks 向量库 TopK
- 关键词召回：对本地 chunks 文本做 BM25 TopK（中文用分词）
- 融合去重：按 chunk_id 合并，保留 source_type 标识
- 精排衔接：融合后的候选进入统一处理与 rerank（如开启）

---

## STORAGE-01 设计要点（简版）

目标：将向量存储切换到 Milvus，实现更稳定的检索与索引管理能力，同时保持 workspace 级数据隔离。

落地口径：
- 存储实现：MilvusVectorDBStorage（本地 Milvus Lite 作为运行形态）
- 数据隔离：collection 命名带 workspace 前缀
- 核心字段：id/vector/created_at + content/file_path/full_doc_id 等元字段

---

## CHUNK-01 设计要点（简版）

目标：形成稳定、可配置、可复现的切片规则，让索引重建时的 chunk_id 与召回行为一致。

落地口径：
- 默认策略：段落优先（双换行/单换行）聚合成块，token 超限再兜底切分
- 上下文连续：对超限切分使用滑窗 overlap；并在 doc_status 记录 chunking 参数用于回溯
- 可配置：CHUNK_SIZE、CHUNK_OVERLAP_SIZE；CHUNK_METHOD=structure/token 切换策略
