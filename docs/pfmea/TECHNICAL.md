# 製剤工程 PFMEA ナレッジ検索エージェント — 技術ドキュメント

固形製剤（錠剤）製造ラインの **PFMEA 情報資産**に対し、技術者の自然言語の質問から
関連レコードを検索し、**故障モード・影響・原因・現在の管理・推奨対策・リスク優先数(RPN)**、
さらに**対策の実施状況**と**対策後の想定RPN（before/after）**、**優先度付きのリスク低減
アクション**を提示するエージェント型アプリケーションです。

> ⚠️ 本アプリのデータは技術検討用に作成した**架空のサンプル**であり、実在の製造ライン
> の情報ではありません。実施状況・対策後RPNも検討用の仮値です。

- リポジトリ: https://github.com/SIJICHI/PFMEA-based-Risk-Reviewer
- ベース: DataRobot Agentic Starter（`datarobot-community/datarobot-agent-application`）
- エージェントフレームワーク: **NAT（NVIDIA NeMo Agent Toolkit）× LangGraph**
- 関連文書: [SPEC.md](SPEC.md) ／ [汎用開発プレイブック](datarobot-agentic-starter-playbook.md)

---

## 1. システム構成

DataRobot Agentic Starter の monorepo 構成を踏襲し、本エージェント固有の実装は主に
`agent/` 配下に閉じています。

```
PFMEA-based-Risk-Reviewer/
├── agent/                      # ★エージェント本体（カスタム実装の中心）
│   ├── workflow.yaml           # NAT オーケストレーション定義
│   ├── agent/
│   │   ├── myagent.py          # MyAgent（LangGraph）+ system_prompt
│   │   ├── tools.py            # pfmea_search ツール（検索ロジック一式）
│   │   ├── data/pfmea_data.json# PFMEA データ（10工程 / 50レコード）
│   │   ├── config.py / register.py / __init__.py
│   ├── pyproject.toml          # 依存 & package-data（data/*.json 同梱）
│   └── tests/                  # 単体テスト（56件）
├── frontend_web/               # React/Vite チャットUI（表描画をカスタム）
├── fastapi_server/             # アプリのバックエンド
├── mcp_server/                 # MCP ツールサーバ（本エージェントは不使用）
├── infra/                      # Pulumi（デプロイ）
└── docs/pfmea/                 # 仕様・技術文書（本書）
```

### リクエストの流れ

```
ユーザー（チャットUI / CLI / Playground）
        │  自然言語の質問
        ▼
fastapi_server ──► NAT workflow.yaml ──► MyAgent（LangGraph 単一ノード）
                                              │
                                              ├─ pfmea_search ツールを呼び出し
                                              │     └─ pfmea_data.json を検索（決定的ロジック）
                                              │
                                              └─ LLM（DataRobot LLM Gateway）が
                                                 検索結果のみに基づき表形式で回答生成
        ▲
        │  Markdown（表）応答
ユーザー（frontend_web が表をレンダリング）
```

設計上の要点:
- **検索は決定的**（`tools.py` の Python ロジック）。LLM は検索結果の整形・優先度づけ・
  根拠提示に専念し、**検索結果に無い事実は生成しない**（system_prompt で強制）。
- ツールは LangChain の `@tool` 関数として `graph_factory` 内でエージェントに渡す
  （NAT function としてではない）。
- LLM は必ず `get_llm()` 経由（DataRobot LLM Gateway / デプロイ済みLLM を吸収）。

---

## 2. データモデル（`agent/agent/data/pfmea_data.json`）

トップレベルは `meta` / `processes`（10件）/ `fmea_records`（50件）の3キー。

### 2.1 meta

```json
{
  "title": "製剤工程 PFMEA 情報資産（架空データ）",
  "line": "固形製剤（錠剤）製造ライン A棟2階",
  "version": "Rev.3",
  "last_updated": "2026-04-10",
  "note": "本データは技術検討用に作成した架空のサンプルであり、実在の製造ラインの情報ではありません。 対策の実施状況・対策後想定RPNは検討用の仮値です。"
}
```

### 2.2 processes（工程定義）

| process_id | No. | 工程名 | 主要設備 | レコード数 |
|---|---|---|---|---|
| P01 | 10 | 秤量 | 電子天秤、原料投入ステーション | 5 |
| P02 | 20 | 混合 | 高速攪拌混合機（ハイスピードミキサー） | 5 |
| P03 | 30 | 造粒 | 流動層造粒乾燥機 | 4 |
| P04 | 40 | 乾燥 | 流動層造粒乾燥機（連続工程） | 5 |
| P05 | 50 | 整粒 | 整粒機（パワーミル） | 4 |
| P06 | 60 | 打錠 | ロータリー式打錠機 | 7 |
| P07 | 70 | コーティング | パンコーティング機 | 4 |
| P08 | 80 | 外観検査 | 自動外観検査機（画像検査） | 5 |
| P09 | 90 | 充填 | PTP包装機、瓶充填機 | 4 |
| P10 | 100 | 包装 | カートナー、封函機 | 7 |

工程定義のフィールド: `process_id` / `process_name` / `process_no` / `description` / `equipment`。

### 2.3 fmea_records（FMEA レコード）

各レコードのフィールド:

| フィールド | 型 | 説明 |
|---|---|---|
| `record_id` | str | 一意ID（例 `F0201`）。回答の**根拠**として併記される |
| `process_id` | str | 紐づく工程（`processes` 参照） |
| `function` | str | 工程に期待される機能 |
| `failure_mode` | str | 故障モード（不良現象） |
| `failure_effect` | str | 影響 |
| `severity` (S) | int | 厳しさ 1–10 |
| `potential_cause` | str[] | 主な要因 |
| `occurrence` (O) | int | 発生度 1–10 |
| `current_control` | str | 現在の管理 |
| `detection` (D) | int | 検出度 1–10 |
| `rpn` | int | リスク優先数 = S × O × D |
| `recommended_action` | str | 推奨対策 |
| `keywords` | str[] | 検索用キーワード |
| `action_status` | str | **対策の実施状況**: 未着手 / 計画中 / 実施中 / 完了 / 見送り |
| `action_owner` | str | 担当部署 |
| `action_due` | str\|null | 完了目標日（未完了時） |
| `action_done_date` | str\|null | 完了日（完了時） |
| `post_severity/occurrence/detection` | int | **対策後**の想定 S/O/D |
| `post_rpn` | int | 対策後の想定 RPN（= post_S × post_O × post_D） |

> 実施状況の分布（サンプル）: 完了17 / 計画中10 / 見送り9 / 実施中8 / 未着手6。
> 高RPN ほど未完了寄りに割り当て、「残存リスク」抽出が意味を持つよう設計。

#### サンプルレコード①: F0201（データ中で最大RPN・未着手）

```json
{
  "record_id": "F0201",
  "process_id": "P02",
  "function": "原薬・添加剤を均一に混合する",
  "failure_mode": "混合不均一（含量偏析）",
  "failure_effect": "錠剤間の含量均一性不良、規格外れ品の発生",
  "severity": 8,
  "potential_cause": [
    "混合時間の設定不足",
    "混合機の回転数不足・設定ミス",
    "原薬粒子径と添加剤粒子径の差による偏析",
    "投入順序の誤り"
  ],
  "occurrence": 4,
  "current_control": "混合工程パラメータ（時間・回転数）の自動記録、サンプリングによる含量均一性試験",
  "detection": 5,
  "rpn": 160,
  "recommended_action": "混合終点をNIR（近赤外分光）でリアルタイム監視する仕組みの導入",
  "keywords": ["混合", "偏析", "含量均一性", "ミキサー", "攪拌", "投入順序"],
  "action_status": "未着手",
  "action_owner": "製剤一課",
  "action_due": "2026-11-30",
  "action_done_date": null,
  "post_severity": 8,
  "post_occurrence": 4,
  "post_detection": 3,
  "post_rpn": 96
}
```

#### サンプルレコード②: F0102（異物混入・対策完了済み）

```json
{
  "record_id": "F0102",
  "process_id": "P01",
  "function": "原薬・添加剤を異物混入なく計量する",
  "failure_mode": "異物混入（金属異物・他原料混入）",
  "failure_effect": "製品中への異物混入、品質クレーム、回収リスク",
  "severity": 9,
  "potential_cause": [
    "計量器具の洗浄不足（前バッチの原料残留）",
    "原料保管容器の破損による異物混入",
    "作業エリアの動線管理不備による交差汚染"
  ],
  "occurrence": 2,
  "current_control": "計量前のライン洗浄確認（清掃記録）、原料の開封前外観確認",
  "detection": 5,
  "rpn": 90,
  "recommended_action": "金属探知機の計量工程への追加設置を検討",
  "keywords": ["異物", "異物混入", "金属", "交差汚染", "洗浄", "コンタミ"],
  "action_status": "完了",
  "action_owner": "製剤一課",
  "action_due": "2026-02-18",
  "action_done_date": "2026-02-18",
  "post_severity": 9,
  "post_occurrence": 2,
  "post_detection": 3,
  "post_rpn": 54
}
```

> データの読み込み: `tools.py` が `Path(__file__).parent / "data" / "pfmea_data.json"`
> を `lru_cache` で1回だけ読み込む。`pyproject.toml` の `[tool.setuptools.package-data]`
> で `agent = ["data/*.json"]` を指定し、デプロイ成果物にも同梱される。

---

## 3. 検索エンジン（`agent/agent/tools.py`）

LLM へ渡す前段の**決定的な検索ロジック**。形態素解析ライブラリには依存しない。

### 3.1 工程検出（シノニム辞書）

`PROCESS_SYNONYMS` で工程名の揺らぎを正規化し `process_id` を特定。

```python
PROCESS_SYNONYMS = {
  "秤量": ["秤量", "計量", "量る"],
  "混合": ["混合", "ミキシング", "撹拌", "攪拌"],
  "打錠": ["打錠", "錠剤成形", "打錠機"],
  "コーティング": ["コーティング", "フィルムコート", "コート"],
  # … 全10工程
}
```
例:「計量」→ 秤量(P01)、「フィルムコート」→ コーティング(P07)。

### 3.2 キーワード抽出

句読点を除去 → 空白分割 → 長い塊（7文字以上）は 2〜4 文字の N-gram に分解 →
ストップワード・1文字トークンを除去 → 重複排除。

### 3.3 スコアリング（関連度モード）

| 加点 | 条件 |
|---|---|
| +2 | レコード本文（故障モード/影響/機能/要因/管理/対策/keywords）への部分一致 |
| +3 | `keywords` フィールドとの一致（重み高） |
| +8 | 工程ID一致ボーナス |

スコア降順、同点は RPN 降順。上位5件（`MAX_RESULTS`）を返却。0件時は言い換え例を提示。

### 3.4 応答モードの切り替え

`search()` は質問意図に応じて3モードを切り替える:

| モード | トリガー | 挙動 |
|---|---|---|
| `relevance` | 既定 | キーワードスコア降順 |
| `rpn` | 「RPN/リスクが高い/優先度/重大」等を検出 | RPN 降順。**トピック語**があればそれで絞ってから降順、工程指定があれば工程内 |
| `status` | 「未対策/まだ対策が打たれていない/実施中/完了」等を検出 | `action_status` で絞り RPN 降順（残存リスク・進捗管理） |

**トピック語の判定**: RPN/ランキング・FMEA一般語（`_GENERIC_TERMS`: リスク・高い・工程・
不良・モード・RPN 等）を除いた残りを「話題」とみなす。これにより:
- 「RPNが高い不良モードを教えて」→ 話題なし → **全体ランキング**
- 「異物混入のリスクが高い工程はどこ？」→ 話題=異物混入 → **異物混入で絞ってRPN降順**

`action_status` フィルタ（`detect_status_filter`）の対応:

| 質問例 | 対象ステータス |
|---|---|
| まだ対策が打たれていない / 未対策 / 残存リスク | 未着手・計画中 |
| 実施中の対策 / 対応中 | 実施中 |
| 完了した対策 / 対応済み | 完了 |
| 見送り / 却下 | 見送り |

### 3.5 リスク低減サマリー（付加価値）

取得レコードの `recommended_action` を **RPN 優先で集約**し、S/O/D に基づく**着眼点**を
機械的に付与（`_risk_focus`）。すべてデータ由来で、新たな対策は創作しない。

| 条件 | 着眼点 |
|---|---|
| S ≥ 8 | 影響度大・重大(S=n) |
| D ≥ O | 検出性の強化(D=n)（検出しにくく流出しやすい） |
| O > D | 発生の予防(O=n)（発生頻度が高い） |

`post_rpn` と併せ、`160→96` のような **before/after** で対策効果を可視化する。

---

## 4. エージェント設計（`agent/agent/myagent.py`）

- `MyAgent = datarobot_agent_class_from_langgraph(graph_factory, prompt_template)`（クラス名固定）
- `graph_factory`: `pfmea_search` ツールを持つ**単一ノード**の LangGraph を構築
- `prompt_template`: ユーザー質問を `{topic}`、履歴を `{chat_history}` で受ける
- `PFMEA_SYSTEM_PROMPT`（行動原則の要点）:
  1. 工程の不良・リスク・対策の質問は必ず `pfmea_search` を呼ぶ
  2. 回答は検索結果のみに基づく（創作禁止）
  3. 各レコードに `record_id` を根拠併記
  4. S/O/D・RPN を整理、RPN が高いほど高優先と明示
  5. **出力はレコード一覧表（Markdown 表）**
  6. その後に**リスク低減アクション表**を提示（未着手・計画中の高RPNを最優先、実施中はフォロー、完了は効果確認）
  7. 0件時は言い換え案内、PFMEA 無関係（天気等）は専用である旨を回答
  8. 架空サンプルである点に留意

### NAT ワークフロー（`agent/workflow.yaml`）抜粋

- `functions.langgraph_agent`（`_type: langgraph_agent`、`llm_name: datarobot_llm`）
- `llms.datarobot_llm`（`_type: datarobot-llm-component`）
- `workflow`（`_type: streaming_memory_agent`、`middleware: [datarobot_moderation]`）
- `general.front_end.a2a` で A2A エージェントカード（名称/説明/スキル/例）を広告

---

## 5. 出力フォーマットと UI（`frontend_web`）

回答は2つの Markdown 表で構成:

1. **レコード一覧表**: 順位 / record_id / 工程 / 故障モード / 影響 / S/O/D / RPN(現→対策後) / 実施状況
2. **リスク低減アクション表**: 優先 / record_id / 主な要因 / 現在の管理 / 推奨アクション / RPN(現→対策後) / 実施状況 / 着眼点

チャットUIは `frontend_web/src/components/ui/streaming-markdown.tsx`（`streamdown`）で描画。
表のレンダリングを以下のようにカスタムしている:

- **セル折り返し**: `td` を `whitespace-normal break-words align-top`（旧 `whitespace-nowrap` を解消）
- **列幅最適化**: `table-auto` を基本に、`record_id` 列（2列目）は `whitespace-nowrap` で一行・最小幅
- **厳密な等幅化**: `table` コンポーネントが hast ノードからヘッダを読み取り、
  `主な要因 / 現在の管理 / 推奨アクション` の列を検出した場合のみ `<colgroup>` を注入。
  当該列を `calc((100% - 狭い列合計) / 列数)` で**完全に同一幅**にし、他列は内容量に応じた `ch` 幅。
  （対象見出しが2列未満の表＝レコード一覧表は従来どおり `table-auto`）

---

## 6. テスト（`agent/tests/`）

`task agent:test` で実行（**56件**）。主な観点:

- `test_pfmea_search.py`: データ件数、工程シノニム検出、キーワード抽出、RPN意図、
  3モード（relevance/rpn/status）、トピック×RPN の切り分け、実施状況フィルタ、
  リスク低減サマリー（着眼点・before/after）、出力整形（record_id 併記・言い換え）
- `test_agent.py`: `MyAgent` の LangGraph 構成、`pfmea_search` の配線、`custompy_adaptor`
- テンプレート既定: chat/streaming/MCP/auth/register

検索ロジックは LLM 非依存の純関数なので、単体テストで決定的に検証できる。

---

## 7. ローカル実行・デプロイ

```sh
# ローカル（DataRobot Codespace 推奨）
dr task compose && dr dotenv setup && task install
task agent:test          # 単体テスト
dr run dev               # :8080 / :5173 でチャットUI

# CLI 実行
task agent:cli -- execute --user_prompt "まだ対策が打たれていない高リスクは？"

# デプロイ
dr run deploy            # → AGENT_DEPLOYMENT_ID / アプリURL / Playground URL
task agent:cli -- execute-deployment --deployment_id <ID> --user_prompt "..."
```

詳細・落とし穴（`Taskfile.yml` の追跡、`.env` の環境ごと再生成 等）は
[汎用開発プレイブック](datarobot-agentic-starter-playbook.md) を参照。

---

## 8. 動作例

質問:「まだ対策が打たれていない高リスクは？」（status モード）

| 順位 | record_id | 工程 | 故障モード | 影響 | S/O/D | RPN(現→対策後) | 実施状況 |
|---|---|---|---|---|---|---|---|
| 1 | F0201 | 混合 | 混合不均一（含量偏析） | 含量均一性不良、規格外れ | 8/4/5 | 160→96 | 未着手 / 製剤一課 / 期限2026-11-30 |
| 2 | F0701 | コーティング | コーティング不均一 | 外観不良、色調差クレーム | 5/4/4 | 80→40 | 計画中 / 製剤二課 / 期限2026-07-31 |
| 3 | F0202 | 混合 | 混合機内部からの異物混入 | 金属・樹脂異物混入 | 9/2/4 | 72→36 | 計画中 / 製剤一課 / 期限2026-12-31 |
| … |

→ 続けて「リスク低減のための推奨アクション」表（主な要因・現在の管理・推奨アクション・
着眼点付き）を提示。

---

## 9. 拡張余地と制約

**拡張余地**
- 対策のクラスタリング（工程横断で同一施策が効くものを集約 → 投資対効果）
- `cost` / `priority` フィールドの追加と並べ替え、未着手をすべて実施した場合の総RPN低減量
- ベクトル検索・Embedding 導入、形態素解析の精度向上、DB化・複数ライン対応

**制約**
- 検索は部分一致 + 簡易 N-gram（意味的類似は未対応）
- データは架空サンプル・読み取り専用（追加・編集機能なし）
- MCP サーバは本エージェントでは未使用（`pfmea_search` ローカルツールのみ）
- 厳密な列等幅は対象見出し名（主な要因/現在の管理/推奨アクション）に依存
