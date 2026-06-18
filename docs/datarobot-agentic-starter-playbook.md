# DataRobot Agentic Starter — Claude Code 開発プレイブック（汎用）

> **このドキュメントの使い方**
> DataRobot の「Agentic Starter」テンプレートでカスタムエージェント／アプリを開発するとき、
> **新規セッションの冒頭で Claude Code に丸ごと渡す**ための前提・手順・禁止事項をまとめた汎用手順書です。
> テーマ（ドメイン）には依存しません。`<...>` は都度置き換えるプレースホルダです。
>
> 使うときは、これに加えて「今回作りたいエージェントの仕様（入力・処理・出力・データ）」を伝えてください。

---

## 0. 最初に Claude Code に伝える1行

> 「DataRobot Agentic Starter テンプレートのカスタムエージェントを開発する。
> このプレイブックの**鉄則**と**DO/DON'T**に従い、`agent/agent/` 配下を中心に実装し、
> テンプレ構成を壊さないこと。」

---

## 1. 前提アーキテクチャ（テンプレの実態）

`datarobot-community/datarobot-agent-application` は **monorepo テンプレート**。主なコンポーネント:

```
<repo>/
├── agent/                 # ★カスタム実装の主戦場
│   ├── workflow.yaml      # NAT(NeMo Agent Toolkit) のオーケストレーション定義
│   ├── agent/
│   │   ├── myagent.py     # MyAgent（= datarobot_agent_class_from_langgraph 生成）+ system_prompt
│   │   ├── tools.py       # ← 自作ツール（任意。LangChain @tool）
│   │   ├── data/          # ← 同梱データ（任意）
│   │   ├── config.py / register.py / __init__.py
│   ├── pyproject.toml     # 依存 & package-data
│   └── tests/
├── fastapi_server/        # アプリのバックエンド
├── frontend_web/          # React/Vite チャットUI（既製。基本そのまま使える）
├── mcp_server/            # MCP ツールサーバ
├── infra/                 # Pulumi（デプロイ）
├── core/ , docs/
├── Taskfile.yml           # ★生成系だが追跡対象（後述の落とし穴）
└── .env                   # ★環境ごと・gitignore
```

**実装の型（重要な事実）**:
- `workflow.yaml`(NAT) が **LangGraph エージェント**をオーケストレーションする。
- **ツールは LangChain の `@tool` 関数**として実装し、`graph_factory` 内で `create_agent` に渡す
  （NAT の function として登録するのではない）。
- LLM は **必ず `get_llm()`** 経由（直接インスタンス化しない）。DataRobot LLM Gateway / デプロイ済みLLM を吸収。
- `MyAgent` クラス名は**変更不可**（DRUM/DRAgent が参照）。
- 確認時点のバージョン目安: agent component `11.10.27` / `datarobot-genai` 0.15.x / Python 3.11–3.13。
  **バージョンで API 名が変わり得る**ので、実装前に `agent/AGENTS.md` と既存 `myagent.py` を必ず読むこと。

---

## 2. 標準ワークフロー（3フェーズ）

```
[1] スキャフォールド   dr start でテンプレを“生成”（1回だけ）→ GitHub へ push
        ↓
[2] カスタム開発       Claude Code で agent/ 配下を実装 → push
        ↓
[3] 起動・デプロイ     Codespace で pull → 環境再生成(.env/Taskfile/.venv) → dr run dev / dr run deploy
```

**最重要の鉄則 = 生成が先、実装は後。**
テンプレ生成前にコードを書くと、生成処理（`copier recopy`）に上書きされて消える。

---

## 3. フェーズ別手順

### フェーズ1: スキャフォールド（標準・1回のみ）

DataRobot Codespace のターミナルが最も確実（ツールが揃っている）。

```sh
# 空ディレクトリで
dr start
#  → ギャラリーで "Agentic Starter" を選択
#  → フレームワーク: langgraph（または NAT/YAML）
#  → LLM: DataRobot LLM Gateway を推奨（最短。USE_DATAROBOT_LLM_GATEWAY=1）
#  → Pulumi スタック / Use Case を設定
dr run dev          # 既定エージェントが :8080 / :5173 で立つことを確認（土台が健全な証拠）

# GitHub へ（★ここで落とし穴回避）
git init                       # dr が初期化済みなら不要
git add -A
git add -f Taskfile.yml        # ★ .gitignore対象だが追跡すべき。明示 force-add
git commit -m "scaffold: Agentic Starter (<framework>, <llm>)"
gh repo create <name> --public --source=. --push
```

### フェーズ2: Claude Code でカスタム開発

開発マシンで `git clone` してから依頼（**`git init` で作り直さない**）。

```sh
git clone https://github.com/<you>/<repo>.git && cd <repo>
# ここで Claude Code に「今回のエージェント仕様」を渡して実装させる
# 実装後:
task agent:lint && task agent:test
git add -A && git commit -m "feat: <agent purpose>" && git push
```

### フェーズ3: DataRobot Codespace で起動・デプロイ

```sh
git clone https://github.com/<you>/<repo>.git && cd <repo>
# 手動cloneならポート公開: 8080 / 5173 / 8842 / 9000（Session Environment → Exposed Ports）

# ★環境ごとに必ず再生成/再構築（git に入らないもの）
dr task compose      # Taskfile.yml を再生成（保険。force-add済みでも実行可）
dr dotenv setup      # .env を再作成（★必須・環境ごと）
pulumi login         # or pulumi login --local
task install         # 依存導入（.venv も環境ごと）

# 起動・デプロイ
dr run dev                                   # UI 確認（:8080 / :5173）
dr run deploy                                # デプロイ → 出力の AGENT_DEPLOYMENT_ID 等を控える
task agent:cli -- execute-deployment \
  --user_prompt "<検証用プロンプト>" --deployment_id <AGENT_DEPLOYMENT_ID>   # デプロイ後検証

# ローカル(=Codespace)単体でのCLI実行
task agent:cli -- execute --user_prompt "<プロンプト>"
task agent:cli -- execute --completion_json "agent/example-completion.json"
```

---

## 4. Claude Code への指示ルール（DO / DON'T・最重要）

| ✅ DO | ❌ DON'T |
|---|---|
| `git clone` で取得し、既存履歴の上で作業する | 新規 `git init` で作り直す（追跡ファイル集合が壊れる） |
| 実装は **`agent/agent/` 配下**を中心に | テンプレを手でコピーして組み立てる（生成は `dr start` の役割） |
| ツールは LangChain **`@tool`** 関数 → `graph_factory` で `create_agent` に渡す | NAT function として登録しようとする |
| LLM は **`get_llm()`** 経由 | LLM を直接インスタンス化する |
| `MyAgent` 名は維持。`custompy_adaptor` の契約も維持 | `MyAgent` をリネーム／契約変更 |
| 同梱データは `agent/agent/data/` + `pyproject.toml` の `[tool.setuptools.package-data]` に登録 | データをパッケージ外に置いて読めなくする |
| 依存追加は `agent/pyproject.toml` → `dr task run agent:install` | 手で site-packages を触る／lock を放置 |
| `system_prompt` で「検索/計算結果に基づくこと・根拠IDの併記」等の制約を明示 | 出典なしに自由生成させる |
| コミット前に `task agent:lint` / `task agent:test` | テスト未更新のまま放置（既定テストは旧実装前提で落ちる） |
| `Taskfile.yml` を **`git add -f`** で確実に追跡 | `git add -A` だけで済ませる（`Taskfile.yml` が漏れる） |
| カスタム後は **`copier recopy` / 初回 `dr start` を再実行しない** | 実装後に recopy を走らせて既定へ戻す |
| 実装前に `agent/AGENTS.md`・既存 `myagent.py`・`workflow.yaml` を読む | バージョン差を確認せず API 名を決め打ち |

---

## 5. 環境ごとに再生成する「3点セット」

git に入らない＝**clone直後に毎回作る**もの。これを習慣化すれば `dr start` 周りの事故はほぼ消える。

| 対象 | 性質 | 再生成コマンド |
|---|---|---|
| **`.env`** | 認証 / LLM / Pulumi 設定。`.gitignore`対象 | `dr dotenv setup`（編集は `dr dotenv edit`） |
| **`Taskfile.yml`** | `.Taskfile.template` から生成 | `dr task compose` |
| **`.venv` / 依存** | マシン固有 | `task install`（agentのみ: `dr task run agent:install`） |

---

## 6. トラブルシュート早見表

| 症状 | 原因 | 対処 |
|---|---|---|
| `dr start`: **No start command or quickstart script found** | clone に `Taskfile.yml` が無い（生成系で `.gitignore`、または push 時に漏れた） | `dr task compose` で再生成 → 再 `dr start`。恒久対策はリポジトリ側で `git add -f Taskfile.yml` |
| `dr start` 後にカスタム実装が**既定に戻った** | `task start` 内の `copier recopy` が template ファイルを上書き | `git restore agent/`。恒久対策は「実装はスキャフォールド後／recopyを再実行しない」 |
| `dr self update`: *Skipping update* | 既に最低バージョン以上 | 正常。更新不要 |
| `versions.yaml [xxx]: 'install' is not defined` の WARN | 自動インストール手順未定義の告知 | 無害。ツールが入っていれば無視可 |
| LLM 呼び出しが失敗 | `.env` 未設定 / LLM 構成不一致 | `dr dotenv setup`。まずは DataRobot LLM Gateway |
| ポートにアクセスできない（Codespace） | ポート未公開 | 8080/5173/8842/9000 を Exposed Ports に追加 |
| 既定テストが落ちる | テンプレ既定テストが旧実装前提 | 自分の実装に合わせて `agent/tests/` を更新 |

> **なぜ `Taskfile.yml` が落とし穴か**: テンプレの `.gitignore` は `/Taskfile.yml` を無視するが、本家リポジトリでは
> （`git add -f` 等で）**追跡されている**。新規 `git init` + `git add -A` でリポジトリ化すると、一度も追跡されて
> いないため `.gitignore` に従って除外され、push から漏れる。これが「`dr start` が動かない」典型原因。

---

## 7. カスタム実装の“型”（コード骨子・汎用）

> 実際の API 名は導入バージョンの既存 `myagent.py` に必ず合わせること。以下は構造の指針。

### `agent/agent/tools.py`（自作ツール）

```python
from langchain_core.tools import tool

@tool
def <tool_name>(query: str) -> str:
    """<ツールの説明（LLMがいつ呼ぶか分かるように）>。

    Args:
        query: <入力の説明>
    Returns:
        <出力（根拠IDなど、LLMが引用しやすい整形テキスト）>
    """
    # ドメインロジック（データ読込・検索・計算など）
    return <整形済みテキスト>
```

### `agent/agent/myagent.py`（単一エージェント構成の例）

```python
from datarobot_genai.core.agents import make_system_prompt
from datarobot_genai.langgraph.agent import datarobot_agent_class_from_langgraph
from langchain.agents import create_agent
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import END, START, MessagesState, StateGraph

from agent.tools import <tool_name>

prompt_template = ChatPromptTemplate.from_messages([
    ("system", "...（{chat_history} を参照可）..."),
    ("user", "{topic}"),
])

SYSTEM_PROMPT = "あなたは<役割>。<行動原則：ツールを使う／結果のみに基づく／根拠IDを併記 など>"

def graph_factory(llm, tools, verbose=False):
    all_tools = [<tool_name>, *tools]
    node = create_agent(llm, tools=all_tools,
                        system_prompt=make_system_prompt(SYSTEM_PROMPT),
                        name="<agent_name>", debug=verbose)
    wf = StateGraph(MessagesState)
    wf.add_node("<agent_name>", node)
    wf.add_edge(START, "<agent_name>")
    wf.add_edge("<agent_name>", END)
    return wf

MyAgent = datarobot_agent_class_from_langgraph(graph_factory, prompt_template)
# custompy_adaptor(...) は既存実装の契約をそのまま維持（get_llm / agent_chat_completion_wrapper）
```

### `agent/workflow.yaml`（要点）
- `general.front_end.a2a.server` の `name` / `description`、`skills` を自分のエージェント用に更新。
- `functions.langgraph_agent.description` を更新。
- 自作 `@tool` は **workflow.yaml に書かない**（`graph_factory` で配線済み）。

### `agent/pyproject.toml`（データ同梱が必要なら）
```toml
[tool.setuptools.package-data]
agent = ["data/*.json"]
```

### `agent/tests/`
- 既定テストは旧実装前提なので、ノード名・ツール名に合わせて更新。
- ツールの純ロジックは LLM 非依存の単体テストにして高速・確実に検証。

---

## 8. チェックリスト

**コミット前**
- [ ] `agent/agent/` 配下のみで完結（テンプレ構成を壊していない）
- [ ] `MyAgent` 名・`custompy_adaptor` 契約を維持
- [ ] ツールは `@tool` で `graph_factory` に配線
- [ ] 依存追加なら `pyproject.toml` 更新 + `dr task run agent:install`
- [ ] データ同梱なら `package-data` 登録
- [ ] `task agent:lint` / `task agent:test` 通過
- [ ] `git add -f Taskfile.yml` 済み（スキャフォールド commit 時）

**Codespace デプロイ前**
- [ ] ポート公開（8080/5173/8842/9000）
- [ ] `dr task compose` / `dr dotenv setup` / `task install` 実行済み（3点セット）
- [ ] `dr run dev` で UI 動作確認
- [ ] `dr run deploy` 後に `execute-deployment` で検証

---

### 付録: 主要コマンド早見
```sh
dr start                         # 生成・初期化（1回）
dr task compose                  # Taskfile.yml 再生成
dr dotenv setup / edit           # .env 作成 / 編集
task install                     # 全依存導入
dr task run agent:install        # agent 依存のみ更新（コード変更後）
task agent:lint / task agent:test
dr run dev  /  dr run agent:dev  # 全サービス / agentのみ起動
dr run deploy  /  task deploy-dev
task agent:cli -- execute --user_prompt "..."                       # ローカル実行
task agent:cli -- execute-deployment --deployment_id <id> --user_prompt "..."  # デプロイ後検証
```
