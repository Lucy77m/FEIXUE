# Agent 纯函数：JSON 抠取（result_schema 校验用）与历史转写（压缩前的预处理）。
# 只测无副作用的模块级函数，不实例化 Agent（那会建 shell/python 会话）。
from desktop_pet.agent.loop import _parse_json_value, _render_transcript


class TestParseJsonValue:
    def test_plain_object(self):
        assert _parse_json_value('{"a": 1}') == {"a": 1}

    def test_object_with_prose_around(self):
        assert _parse_json_value('好的，结果是 {"title": "x", "score": 3}，供参考') == {
            "title": "x", "score": 3,
        }

    def test_object_in_code_fence(self):
        assert _parse_json_value('```json\n{"ok": true}\n```') == {"ok": True}

    def test_plain_array(self):
        assert _parse_json_value("[1, 2, 3]") == [1, 2, 3]

    def test_array_after_emotion_tag(self):
        assert _parse_json_value('[happy]\n[{"t": "x"}]') == [{"t": "x"}]

    def test_no_json_returns_none(self):
        assert _parse_json_value("这里没有任何结构化内容。") is None

    def test_scalar_not_accepted(self):
        assert _parse_json_value("42") is None


class TestRenderTranscript:
    def test_roles_and_tool_calls(self):
        out = _render_transcript([
            {"role": "user", "content": "帮我查天气"},
            {"role": "assistant", "content": "", "tool_calls": [
                {"function": {"name": "web_search", "arguments": '{"query": "天气"}'}},
            ]},
            {"role": "tool", "content": "晴，25 度"},
            {"role": "assistant", "content": "今天晴。"},
        ])
        assert "user: 帮我查天气" in out
        assert "web_search" in out
        assert "[工具结果] 晴，25 度" in out
        assert "今天晴。" in out

    def test_image_parts_become_placeholder(self):
        out = _render_transcript([
            {"role": "user", "content": [{"type": "image_url", "image_url": {"url": "data:..."}}]},
        ])
        assert "[图片]" in out
        assert "data:" not in out

    def test_long_transcript_middle_truncated(self):
        msgs = [{"role": "user", "content": f"第{i}句 " + "x" * 400} for i in range(60)]
        out = _render_transcript(msgs)
        assert "…(中间略)…" in out
        assert len(out) < 13_000
        assert "第0句" in out and "第59句" in out

    def test_empty_messages(self):
        assert _render_transcript([]) == ""
