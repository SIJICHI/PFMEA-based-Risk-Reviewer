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
    detect_process_id,
    detect_rpn_intent,
    extract_keywords,
    load_data,
    pfmea_search,
    search,
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
        # 「リスクが高い」で RPN 意図が立つ。
        result = search("異物混入のリスクが高い工程はどこ？")
        assert result["mode"] == "rpn"
        assert len(result["records"]) > 0
        rpns = [r["rpn"] for r in result["records"]]
        assert rpns == sorted(rpns, reverse=True)

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
