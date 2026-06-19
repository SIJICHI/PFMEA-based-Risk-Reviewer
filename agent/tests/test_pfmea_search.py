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
"""PFMEA 検索ロジックの単体テスト (SPEC 5 / 8 の動作確認シナリオ)。"""

from agent.tools import (
    _risk_focus,
    detect_process_id,
    detect_rpn_intent,
    extract_keywords,
    load_data,
    pfmea_search,
    search,
    search_as_text,
)


class TestDataset:
    def test_dataset_loads_expected_volume(self):
        data = load_data()
        assert len(data["processes"]) == 10
        assert len(data["fmea_records"]) == 50


class TestProcessDetection:
    def test_synonym_maps_to_canonical_process(self):
        # 「計量」は秤量(P01)、「フィルムコート」はコーティング(P07)。
        assert detect_process_id("計量のばらつきが心配") == "P01"
        assert detect_process_id("フィルムコートのムラ") == "P07"
        assert detect_process_id("打錠工程の不良") == "P06"

    def test_no_process_returns_none(self):
        assert detect_process_id("今日の天気は？") is None


class TestKeywordExtraction:
    def test_stopwords_removed(self):
        kws = extract_keywords("打錠工程で注意するべき不良現象は？")
        assert "注意" not in kws
        assert all(len(k) >= 2 for k in kws)

    def test_ngram_for_long_chunks(self):
        # 7文字以上の塊は 2-4 文字の N-gram に分解される。
        kws = extract_keywords("abcdefghij")
        assert "ab" in kws


class TestRpnIntent:
    def test_detects_rpn_intent(self):
        assert detect_rpn_intent("RPNが高い不良モードを教えて") is True
        assert detect_rpn_intent("リスクが高い工程はどこ？") is True

    def test_no_rpn_intent(self):
        assert detect_rpn_intent("コーティングのムラを防ぐには？") is False


class TestSearchScenarios:
    """SPEC 8 の 5 シナリオ。"""

    def test_scenario1_tableting_defects(self):
        result = search("打錠工程で注意するべき不良現象は？")
        assert result["mode"] == "relevance"
        assert result["process_id"] == "P06"
        assert result["process_name"] == "打錠"
        assert len(result["records"]) > 0
        # 打錠工程(P06)のレコードが上位に来る(工程ボーナス +8)。
        assert result["records"][0]["process_id"] == "P06"

    def test_scenario2_foreign_matter_high_risk(self):
        # 「リスクが高い」で RPN 意図が立つが、トピック「異物混入」で絞ってから
        # RPN 降順になること（無関係な高RPNレコードを返さない）。
        result = search("異物混入のリスクが高い工程はどこ？")
        assert result["mode"] == "rpn"
        assert len(result["records"]) > 0
        rpns = [r["rpn"] for r in result["records"]]
        assert rpns == sorted(rpns, reverse=True)
        # 返却レコードはすべて「異物」に関連していること。
        for r in result["records"]:
            text = r["failure_mode"] + " ".join(r.get("keywords", []))
            assert "異物" in text
        # 異物混入は複数工程に跨るため、2工程以上が含まれること。
        assert len({r["process_id"] for r in result["records"]}) >= 2
        # トップは最大RPNの異物レコード F0102。
        assert result["records"][0]["record_id"] == "F0102"

    def test_scenario3_coating_unevenness(self):
        result = search("コーティングのムラを防ぐには？")
        assert result["mode"] == "relevance"
        assert result["process_id"] == "P07"
        record_ids = [r["record_id"] for r in result["records"]]
        # コートムラのレコード F0701 が含まれる。
        assert "F0701" in record_ids

    def test_scenario4_high_rpn(self):
        result = search("RPNが高い不良モードを教えて")
        assert result["mode"] == "rpn"
        assert len(result["records"]) == 5
        rpns = [r["rpn"] for r in result["records"]]
        assert rpns == sorted(rpns, reverse=True)
        # データセット最大 RPN は F0201 の 160。
        assert result["records"][0]["record_id"] == "F0201"

    def test_scenario5_no_match(self):
        result = search("今日の東京の天気を教えて")
        assert result["mode"] == "relevance"
        assert result["records"] == []


class TestRpnTopicFiltering:
    """RPN モードでの『トピック絞り込み vs 全体ランキング』の切り分け。"""

    def test_generic_ranking_stays_global(self):
        # トピック語が無い純粋ランキング → 全体トップ（無関係でも高RPNが入る）。
        result = search("RPNが高い不良モードを教えて")
        ids = [r["record_id"] for r in result["records"]]
        assert ids[0] == "F0201"
        assert "F0101" in ids  # 異物以外の高RPNも含まれる＝全体ランキング

    def test_topic_plus_rpn_filters_by_topic(self):
        # トピック語あり → そのトピックで絞ってから RPN 降順。
        result = search("異物混入のリスクが高い工程はどこ？")
        for r in result["records"]:
            text = r["failure_mode"] + " ".join(r.get("keywords", []))
            assert "異物" in text

    def test_process_plus_rpn_scopes_to_process(self):
        # 工程指定 + RPN 意図 → その工程内で RPN 降順。
        result = search("打錠工程でRPNが高い不良は？")
        assert result["mode"] == "rpn"
        assert all(r["process_id"] == "P06" for r in result["records"])


class TestResultLimit:
    def test_returns_at_most_five(self):
        result = search("異物混入")
        assert len(result["records"]) <= 5


class TestToolFormatting:
    def test_tool_includes_record_ids(self):
        text = pfmea_search.invoke("打錠工程で注意するべき不良現象は？")
        assert "F06" in text  # 打錠工程レコードIDの接頭辞
        assert "RPN" in text

    def test_tool_no_match_offers_rephrasing(self):
        text = pfmea_search.invoke("今日の天気は？")
        assert "見つかりませんでした" in text
        assert "言い換え" in text


class TestRiskReductionSummary:
    def test_summary_present_and_grounded(self):
        text = search_as_text("打錠工程で注意するべき不良現象は？")
        # 専用の『リスク低減のための推奨アクション』セクションが付与される。
        assert "■ リスク低減のための推奨アクション" in text
        assert "着眼:" in text
        # アクションは検索結果のレコードに基づく（record_id 付き）。
        assert "[F06" in text

    def test_summary_is_rpn_prioritized(self):
        # サマリーは RPN 降順。最大 RPN の F0201 が先頭に来る。
        text = search_as_text("RPNが高い不良モードを教えて")
        block = text.split("■ リスク低減のための推奨アクション")[1]
        assert block.lstrip().splitlines()[0].startswith("（") or "F0201" in block
        assert "1. [F0201 / RPN160]" in block

    def test_risk_focus_reflects_sod(self):
        # 厳しさ大・検出度高の組合せが着眼点に反映される。
        f0201 = next(
            r for r in load_data()["fmea_records"] if r["record_id"] == "F0201"
        )
        focus = _risk_focus(f0201)  # S=8, O=4, D=5
        assert "影響度大・重大(S=8)" in focus
        assert "検出性の強化(D=5)" in focus

    def test_risk_focus_occurrence_driven(self):
        # 発生度 > 検出度 のとき発生予防が着眼点。
        focus = _risk_focus({"severity": 3, "occurrence": 5, "detection": 2})
        assert "発生の予防(O=5)" in focus
        assert "影響度大" not in focus  # S<8
