# 製剤工程 PFMEA ナレッジ検索エージェント

固形製剤（錠剤）製造ラインの **PFMEA 情報資産**から、自然言語の質問に対して
関連レコード（故障モード・影響・原因・現在の管理・推奨対策・リスク優先数 RPN）を
**根拠（record_id）付き**で提示するエージェントです。DataRobot のエージェント
アプリケーションテンプレートをベースに、**NAT**（[NeMo Agent Toolkit](https://docs.nvidia.com/nemo/agent-toolkit/index.html)）で
LangGraph エージェントをオーケストレーションしています。

## 構成

| ファイル | 役割 |
| --- | --- |
| [`workflow.yaml`](workflow.yaml) | NAT ワークフロー定義（LLM・エージェント・A2A 設定） |
| [`agent/myagent.py`](agent/myagent.py) | `pfmea_search` ツールを備えた単一エージェント（`MyAgent`）と system_prompt |
| [`agent/tools.py`](agent/tools.py) | PFMEA 検索ロジック（シノニム辞書・キーワード抽出・スコアリング・RPN 意図検出） |
| [`agent/data/pfmea_data.json`](agent/data/pfmea_data.json) | 架空の PFMEA データ（10 工程 / 50 レコード） |
| [`tests/test_pfmea_search.py`](tests/test_pfmea_search.py) | 検索ロジックの単体テスト（SPEC §8 の 5 シナリオ） |

## 検索ロジック（`agent/tools.py`）

1. **工程検出**: シノニム辞書で工程名の揺らぎを吸収（例: 「計量」→ 秤量、「フィルムコート」→ コーティング）し `process_id` を特定。
2. **キーワード抽出**: 句読点・ストップワード除去後、長い塊は簡易 N-gram に分解（形態素解析非依存）。
3. **スコアリング**: 本文部分一致 +2、`keywords` 一致 +3、工程一致ボーナス +8。同点は RPN 降順。
4. **RPN 意図検出**: 「RPN が高い」「リスクが高い」等を検出すると RPN 降順モードに切替。
5. **上位 5 件**を返却。該当なし時は言い換え例を提示。

回答生成では system_prompt（`agent/myagent.py`）で「検索結果に基づくのみ」「record_id を根拠として併記」を指示しています。

## ローカル実行

`.env` に DataRobot 認証情報（`DATAROBOT_API_TOKEN` 等）を設定したうえで:

```shell
# 依存インストール
dr task run agent:install   # または: cd agent && uv sync

# CLI で実行（SPEC §8 のシナリオ）
task agent:cli -- execute --user_prompt "打錠工程で注意するべき不良現象は？"
task agent:cli -- execute --user_prompt "異物混入のリスクが高い工程はどこ？"
task agent:cli -- execute --user_prompt "コーティングのムラを防ぐには？"
task agent:cli -- execute --user_prompt "RPNが高い不良モードを教えて"
task agent:cli -- execute --completion_json "example-completion.json"

# テスト
dr task run agent:test      # または: cd agent && uv run pytest
```

チャット UI はリポジトリ同梱の `frontend_web/`（React/Vite）と `fastapi_server/` を利用します。

> ⚠️ 本データは技術検討用に作成した**架空のサンプル**であり、実在の製造ラインの情報ではありません。
