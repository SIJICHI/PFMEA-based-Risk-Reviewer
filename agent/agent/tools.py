# Copyright 2026 DataRobot, Inc.
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#   http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.
"""PFMEA ナレッジ検索ツール.

製剤工程の PFMEA 情報資産 (``data/pfmea_data.json``) に対して、自然言語の
質問から関連レコードを検索する。検索ロジックは参考実装 (HTML/JS モック) を
Python に移植したもので、以下の要素から成る:

* 工程名シノニム辞書による ``process_id`` 検出 (SPEC 5.1)
* 助詞・ストップワード除去 + 簡易 N-gram によるキーワード抽出 (SPEC 5.2)
* 部分一致スコアリングとランキング、RPN 意図検出による応答モード切替 (SPEC 5.3)

形態素解析ライブラリには依存しない (SPEC 5.2)。
"""

from __future__ import annotations

import json
import re
from functools import lru_cache
from pathlib import Path
from typing import Any

from langchain_core.tools import tool

# データファイルはこのモジュールと同じ位置の data/ ディレクトリに配置する
# (SPEC 7 / 12: 配置・読み込みのベストプラクティス)。
DATA_PATH = Path(__file__).parent / "data" / "pfmea_data.json"

# 返却件数の上限 (SPEC 5.3: 上位5件程度)。
MAX_RESULTS = 5

# 工程名の別名・揺らぎ吸収用シノニム辞書 (SPEC 5.1)。
# 例: 「計量」→ 秤量、「フィルムコート」→ コーティング。
PROCESS_SYNONYMS: dict[str, list[str]] = {
    "秤量": ["秤量", "計量", "量る"],
    "混合": ["混合", "ミキシング", "撹拌", "攪拌"],
    "造粒": ["造粒", "顆粒形成"],
    "乾燥": ["乾燥"],
    "整粒": ["整粒", "篩過", "篩"],
    "打錠": ["打錠", "錠剤成形", "打錠機"],
    "コーティング": ["コーティング", "フィルムコート", "コート"],
    "外観検査": ["外観検査", "検査", "目視検査"],
    "充填": ["充填", "ブリスター", "PTP"],
    "包装": ["包装", "梱包", "封函"],
}

# 助詞・一般語などの除去対象 (SPEC 5.2)。
STOPWORDS: set[str] = {
    "の",
    "が",
    "を",
    "に",
    "は",
    "で",
    "と",
    "も",
    "や",
    "する",
    "した",
    "こと",
    "もの",
    "ある",
    "どんな",
    "どのような",
    "なに",
    "何",
    "教えて",
    "ください",
    "について",
    "とは",
    "です",
    "ますか",
    "でしょうか",
    "注意",
    "すべき",
    "べき",
    "います",
}

# RPN/ランキング意図や FMEA 一般語。RPN モードで「トピックによる絞り込み」を
# 判定する際、これらは“話題”とみなさず除外する（例:「RPNが高い不良モード」は
# 全体ランキング、「異物混入のリスクが高い工程」は異物混入で絞ってからRPN降順）。
_GENERIC_TERMS = [
    "rpn",
    "リスク優先",
    "優先度",
    "優先",
    "高い",
    "重大",
    "危険",
    "重要",
    "不良現象",
    "不良モード",
    "不良",
    "故障モード",
    "故障",
    "モード",
    "工程",
    "リスク",
    "教えて",
    "どこ",
    "ランキング",
    "上位",
    "一覧",
    # 対策の実施状況・進捗を表す語もトピック扱いしない（状況フィルタ側で処理）。
    "高リスク",
    "対策",
    "対応",
    "アクション",
    "施策",
    "状況",
    "進捗",
    "未着手",
    "計画中",
    "実施中",
    "完了",
    "見送り",
    "未対策",
    "未実施",
    "未完了",
    "対策済",
    "対応済",
    "実施済",
    "残存",
    "残ってい",
    "打たれてい",
    "手つかず",
    "積み残",
]

# スコアリング重み (SPEC 5.3)。
_SCORE_HAYSTACK_HIT = 2  # レコード本文への部分一致
_SCORE_KEYWORD_HIT = 3  # keywords フィールド一致は重み付けを高く
_SCORE_PROCESS_BONUS = 8  # 工程ID一致ボーナス

# RPN 重視モードに切り替える意図を表す正規表現 (SPEC 5.3)。
_RPN_INTENT_RE = re.compile(r"rpn|リスク優先|優先度|高い|重大|危険|重要", re.IGNORECASE)
# 句読点・記号の正規化用。
_PUNCT_RE = re.compile(r"[？?！!。、,，．.\n]")


@lru_cache(maxsize=1)
def load_data() -> dict[str, Any]:
    """PFMEA データセットを読み込む (初回のみ I/O、以降はキャッシュ)。"""
    with DATA_PATH.open(encoding="utf-8") as f:
        return json.load(f)


@lru_cache(maxsize=1)
def _process_index() -> dict[str, dict[str, Any]]:
    """process_id -> プロセス定義 の索引。"""
    return {p["process_id"]: p for p in load_data()["processes"]}


def extract_keywords(text: str) -> list[str]:
    """質問文からキーワード候補を抽出する (SPEC 5.2)。

    句読点を空白化し、空白で粗く分割。長い塊 (7文字以上) は分かち書きの
    代わりに 2〜4 文字の N-gram に分解する。最後にストップワードと
    1文字トークンを除去し、重複を排除する。
    """
    rough = _PUNCT_RE.sub(" ", text.lower()).split()
    tokens: list[str] = []
    for chunk in rough:
        if len(chunk) <= 6:
            tokens.append(chunk)
        else:
            for n in (2, 3, 4):
                for i in range(len(chunk) - n + 1):
                    tokens.append(chunk[i : i + n])

    seen: set[str] = set()
    result: list[str] = []
    for tok in tokens:
        if len(tok) >= 2 and tok not in STOPWORDS and tok not in seen:
            seen.add(tok)
            result.append(tok)
    return result


def _topic_keywords(query: str) -> list[str]:
    """ランキング・FMEA 一般語を除いた“話題”キーワードを抽出する。

    RPN モードで「全体ランキング質問」か「特定トピックの中での高RPN」かを
    見分けるために使う。一般語を先に除去してから N-gram 化することで、
    一般語の断片トークンが残らないようにする。
    """
    reduced = query.lower()
    for g in _GENERIC_TERMS:
        reduced = reduced.replace(g.lower(), " ")
    return extract_keywords(reduced)


def detect_process_id(text: str) -> str | None:
    """シノニム辞書を用いて質問文から process_id を検出する (SPEC 5.1)。"""
    processes = load_data()["processes"]
    for canonical, variants in PROCESS_SYNONYMS.items():
        for variant in variants:
            if variant in text:
                for p in processes:
                    if p["process_name"] == canonical:
                        return str(p["process_id"])
    return None


def detect_rpn_intent(text: str) -> bool:
    """「RPN が高い」等の優先度意図を検出する (SPEC 5.3)。"""
    return bool(_RPN_INTENT_RE.search(text))


# 対策の実施状況フィルタ: 質問の語から対象ステータス集合を判定する。
_STATUS_PATTERNS: list[tuple[tuple[str, ...], str]] = [
    (
        ("未着手", "計画中"),
        r"未着手|未対策|未実施|未完了|打たれてい|手つかず|残存|残ってい|積み残",
    ),
    (("実施中",), r"実施中|対応中|進行中|進捗|途中"),
    (("完了",), r"完了|対応済|実施済|対策済|済んだ"),
    (("見送り",), r"見送り|却下|見合わせ|保留"),
]


def detect_status_filter(query: str) -> set[str] | None:
    """質問から対象の対策実施状況の集合を判定する（無ければ None）。

    例:「未対策の高リスクは？」→ {未着手, 計画中}、「実施中の対策は？」→ {実施中}。
    """
    matched: set[str] = set()
    for statuses, pattern in _STATUS_PATTERNS:
        if re.search(pattern, query):
            matched.update(statuses)
    return matched or None


def score_record(
    record: dict[str, Any], keywords: list[str], process_id: str | None
) -> int:
    """1 レコードの関連度スコアを算出する (SPEC 5.3)。"""
    haystack = " ".join(
        [
            record.get("failure_mode", ""),
            record.get("failure_effect", ""),
            record.get("function", ""),
            *record.get("potential_cause", []),
            *record.get("keywords", []),
            record.get("current_control", ""),
            record.get("recommended_action", ""),
        ]
    ).lower()

    record_keywords = [k.lower() for k in record.get("keywords", [])]

    score = 0
    for kw in keywords:
        if kw in haystack:
            score += _SCORE_HAYSTACK_HIT
        for rk in record_keywords:
            if kw in rk or rk in kw:
                score += _SCORE_KEYWORD_HIT

    if process_id and record.get("process_id") == process_id:
        score += _SCORE_PROCESS_BONUS
    return score


def _narrow_pool(
    pool: list[dict[str, Any]], query: str, process_id: str | None
) -> list[dict[str, Any]]:
    """工程指定があれば工程で、無ければトピック語で母集団を絞る。

    トピック語が無い、または該当が無い場合は素通し（全体を維持）する。
    """
    if process_id:
        return [r for r in pool if r.get("process_id") == process_id]
    topic_kw = _topic_keywords(query)
    if topic_kw:
        topic_pool = [r for r in pool if score_record(r, topic_kw, None) > 0]
        if topic_pool:
            return topic_pool
    return pool


def search(query: str) -> dict[str, Any]:
    """質問文に対して PFMEA レコードを検索する (SPEC 5.3 + 対策実施状況)。

    Returns:
        以下のキーを持つ dict:
        * ``mode``: "status"(実施状況) / "rpn"(RPN降順) / "relevance"(関連度順)
        * ``process_id`` / ``process_name``: 検出された工程 (なければ None)
        * ``status_filter``: 実施状況モード時の対象ステータス (なければ None)
        * ``records``: 上位レコードのリスト (最大 ``MAX_RESULTS`` 件)
    """
    records = load_data()["fmea_records"]
    keywords = extract_keywords(query)
    process_id = detect_process_id(query)
    rpn_intent = detect_rpn_intent(query)
    status_filter = detect_status_filter(query)
    proc_index = _process_index()

    if status_filter:
        # 実施状況モード: 指定ステータスに絞り、工程/トピックで narrow し RPN 降順。
        # 「未対策の高リスク」「実施中の対策」等の進捗・残存リスク管理に対応。
        pool = [r for r in records if r.get("action_status") in status_filter]
        pool = _narrow_pool(pool, query, process_id)
        top = sorted(pool, key=lambda r: r.get("rpn", 0), reverse=True)[:MAX_RESULTS]
        mode = "status"
    elif rpn_intent:
        # RPN 重視モード。工程指定→工程内、無ければトピックで絞ってから RPN 降順。
        pool = _narrow_pool(records, query, process_id)
        top = sorted(pool, key=lambda r: r.get("rpn", 0), reverse=True)[:MAX_RESULTS]
        mode = "rpn"
    else:
        scored = [(r, score_record(r, keywords, process_id)) for r in records]
        scored = [(r, s) for r, s in scored if s > 0]
        # スコア降順、同点は RPN 降順 (SPEC 5.3)。
        scored.sort(key=lambda rs: (rs[1], rs[0].get("rpn", 0)), reverse=True)
        top = [r for r, _ in scored[:MAX_RESULTS]]
        mode = "relevance"

    process = proc_index.get(process_id) if process_id else None
    return {
        "mode": mode,
        "process_id": process_id,
        "process_name": process["process_name"] if process else None,
        "status_filter": sorted(status_filter) if status_filter else None,
        "records": top,
    }


def _action_status_line(record: dict[str, Any]) -> str:
    """実施状況（担当・期限/完了日）の1行表記。データが無ければ空文字。"""
    status = record.get("action_status")
    if not status:
        return ""
    owner = record.get("action_owner", "—")
    done = record.get("action_done_date")
    when = f"完了日: {done}" if done else f"期限: {record.get('action_due') or '—'}"
    return f"\n  実施状況: {status}（担当: {owner} / {when}）"


def _post_rpn_line(record: dict[str, Any]) -> str:
    """対策後の想定RPN（before→after）の1行表記。データが無ければ空文字。"""
    post = record.get("post_rpn")
    if post is None:
        return ""
    return (
        f"\n  対策後の想定: RPN {record.get('rpn')} → {post}"
        f"（S{record.get('post_severity')}/O{record.get('post_occurrence')}"
        f"/D{record.get('post_detection')}）"
    )


def _format_record(record: dict[str, Any]) -> str:
    """1 レコードを LLM が根拠提示しやすい整形テキストに変換する。"""
    proc = _process_index().get(record.get("process_id", ""), {})
    causes = "; ".join(record.get("potential_cause", []))
    return (
        f"[{record['record_id']}] 工程: {proc.get('process_name', '?')}"
        f"（{record.get('process_id')}, No.{proc.get('process_no', '?')}）\n"
        f"  故障モード: {record.get('failure_mode', '')}\n"
        f"  影響: {record.get('failure_effect', '')}\n"
        f"  機能: {record.get('function', '')}\n"
        f"  主な要因: {causes}\n"
        f"  厳しさ(S): {record.get('severity')} / "
        f"発生度(O): {record.get('occurrence')} / "
        f"検出度(D): {record.get('detection')} / RPN: {record.get('rpn')}\n"
        f"  現在の管理: {record.get('current_control', '')}\n"
        f"  推奨対策: {record.get('recommended_action', '')}"
        f"{_action_status_line(record)}"
        f"{_post_rpn_line(record)}"
    )


def _risk_focus(record: dict[str, Any]) -> str:
    """S/O/D から FMEA 上の着眼点（リスク低減の方向性）を決定的に導く。

    厳しさ(S)が高い→影響度が大きく重大。発生度(O)が高い→発生予防が有効。
    検出度(D)が高い→検出しにくく流出しやすいため検出強化が有効。
    データに無い事実は作らず、S/O/D の数値から方向性のみを示す。
    """
    s = record.get("severity", 0) or 0
    o = record.get("occurrence", 0) or 0
    d = record.get("detection", 0) or 0
    parts: list[str] = []
    if s >= 8:
        parts.append(f"影響度大・重大(S={s})")
    # O と D のうち大きい方を主眼に（同値なら検出強化を優先表記）。
    if d >= o:
        parts.append(f"検出性の強化(D={d})")
    else:
        parts.append(f"発生の予防(O={o})")
    return " / ".join(parts)


def _risk_reduction_block(records: list[dict[str, Any]]) -> str:
    """取得レコードの推奨対策を RPN 優先で集約した『リスク低減サマリー』。

    各レコードの ``recommended_action`` を根拠 (record_id) 付きで列挙し、
    S/O/D に基づく着眼点を併記する。内容はすべてレコード由来。
    """
    ranked = sorted(records, key=lambda r: r.get("rpn", 0), reverse=True)
    lines = ["■ リスク低減のための推奨アクション（RPN優先）"]
    for i, r in enumerate(ranked, start=1):
        post = r.get("post_rpn")
        rpn_str = f"RPN{r.get('rpn')}" + (f"→{post}" if post is not None else "")
        status = r.get("action_status")
        status_str = f" 〈{status}〉" if status else ""
        meta: list[str] = []
        if r.get("action_owner"):
            meta.append(f"担当: {r['action_owner']}")
        done = r.get("action_done_date")
        due = done or r.get("action_due")
        if due:
            meta.append(("完了" if done else "期限") + f": {due}")
        meta_str = (" ／ " + "・".join(meta)) if meta else ""
        lines.append(
            f"{i}. [{r['record_id']} / {rpn_str}]{status_str} "
            f"{r.get('failure_mode', '')}\n"
            f"   → {r.get('recommended_action', '')}\n"
            f"   （着眼: {_risk_focus(r)}{meta_str}）"
        )
    return "\n".join(lines)


def search_as_text(query: str) -> str:
    """検索結果を LLM 向けの整形テキストにする (該当なし時は言い換え例を提示)。"""
    result = search(query)
    records = result["records"]

    if not records:
        # 該当なしの場合は言い換え例を提示する (SPEC 5.3)。
        return (
            f"質問「{query}」に一致する PFMEA レコードは見つかりませんでした。\n"
            "工程名（例: 打錠、コーティング、外観検査、混合 など）や、不良現象の"
            "キーワード（例: 異物混入、重量偏差、コートムラ）を含めて言い換えて"
            "ください。\n"
            "言い換え例:\n"
            "  - 「打錠工程で注意するべき不良現象は？」\n"
            "  - 「異物混入のリスクが高い工程はどこ？」\n"
            "  - 「RPNが高い不良モードを教えて」"
        )

    if result["mode"] == "status":
        labels = "・".join(result.get("status_filter") or [])
        scope = f"{result['process_name']}工程の" if result["process_name"] else ""
        header = (
            f"{scope}対策状況『{labels}』の PFMEA レコードを RPN 降順で "
            f"{len(records)} 件抽出しました。"
        )
    elif result["mode"] == "rpn":
        scope = (
            f"{result['process_name']}工程の" if result["process_name"] else "全工程の"
        )
        header = f"{scope}PFMEA レコードを RPN 降順で {len(records)} 件抽出しました。"
    else:
        scope = (
            f"{result['process_name']}工程に関連する"
            if result["process_name"]
            else "関連する"
        )
        header = f"{scope}PFMEA レコードを関連度順に {len(records)} 件抽出しました。"

    body = "\n\n".join(_format_record(r) for r in records)
    risk_block = _risk_reduction_block(records)
    return f"{header}\n\n{body}\n\n{risk_block}"


@tool
def pfmea_search(query: str) -> str:
    """製剤工程の PFMEA 情報資産から、質問に関連する故障モード・影響・原因・
    現在の管理・推奨対策・リスク優先数(RPN)を含むレコードを検索する。

    各レコードには対策の実施状況（未着手/計画中/実施中/完了/見送り・担当・期限）と
    対策後の想定RPNも含まれる。工程の不良現象・リスク・対策・その進捗や残存リスクに
    関する質問にはこのツールを必ず使用すること。
    例:「打錠工程で注意すべき不良現象は？」「異物混入のリスクが高い工程は？」
    「RPNが高い不良モードを教えて」「まだ対策が打たれていない高リスクは？」
    「実施中の対策は？」。

    Args:
        query: 利用者の自然言語の質問文（日本語）。

    Returns:
        関連 PFMEA レコードを record_id・実施状況・対策後想定RPN 付きで整形した
        テキスト。該当が無い場合は言い換え例を含む案内文を返す。
    """
    return search_as_text(query)
