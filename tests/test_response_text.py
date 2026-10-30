"""Parser must ignore thinking blocks (Sonnet 5.5 response shape)."""

import unittest
from types import SimpleNamespace

from sr_processor.config import (
    DEFAULT_MODEL,
    api_create_kwargs,
    resolve_ui_model,
)
from sr_processor.response import extract_response_text


class ThinkingBlock:
    """Mimics the Anthropic SDK: no .text attribute."""

    def __init__(self):
        self.type = "thinking"
        self.thinking = "internal reasoning"
        self.signature = "sig"

    def __getattr__(self, name):
        raise AttributeError(f"'{type(self).__name__}' object has no attribute '{name}'")


class ExtractResponseTextTests(unittest.TestCase):
    def test_skips_leading_thinking_block(self):
        content = [
            ThinkingBlock(),
            SimpleNamespace(type="text", text='{"eligible": false, "reason": "not RCT"}'),
        ]
        self.assertEqual(
            extract_response_text(content),
            '{"eligible": false, "reason": "not RCT"}',
        )

    def test_joins_multiple_text_blocks(self):
        content = [
            ThinkingBlock(),
            SimpleNamespace(type="text", text='{"eligible":'),
            SimpleNamespace(type="text", text=" true}"),
        ]
        self.assertEqual(extract_response_text(content), '{"eligible":\n true}')

    def test_dict_style_blocks(self):
        content = [
            {"type": "thinking", "thinking": "skip me", "signature": "x"},
            {"type": "text", "text": '{"eligible": true}'},
        ]
        self.assertEqual(extract_response_text(content), '{"eligible": true}')

    def test_empty_response_raises(self):
        with self.assertRaisesRegex(ValueError, "empty response"):
            extract_response_text([])

    def test_thinking_only_raises_without_touching_text(self):
        with self.assertRaisesRegex(ValueError, "no text to parse"):
            extract_response_text([ThinkingBlock()])

    def test_legacy_first_block_text_still_works(self):
        content = [SimpleNamespace(type="text", text='{"eligible": true}')]
        self.assertEqual(extract_response_text(content), '{"eligible": true}')


class ModelConfigTests(unittest.TestCase):
    def test_default_model_is_sonnet_55(self):
        self.assertEqual(DEFAULT_MODEL, "claude-sonnet-5-5")

    def test_sonnet_55_opts_out_of_upfront_thinking(self):
        self.assertEqual(
            api_create_kwargs("claude-sonnet-5-5"),
            {"thinking": {"type": "between_tools"}},
        )

    def test_sonnet_46_sends_no_thinking_kwarg(self):
        self.assertEqual(api_create_kwargs("claude-sonnet-4-6"), {})

    def test_resolve_ui_model_rejects_unknown(self):
        with self.assertRaisesRegex(ValueError, "Unsupported model"):
            resolve_ui_model("claude-opus-4")

    def test_resolve_ui_model_default(self):
        self.assertEqual(resolve_ui_model(None), DEFAULT_MODEL)
        self.assertEqual(resolve_ui_model("claude-sonnet-4-6"), "claude-sonnet-4-6")


class FrameworkPromptTests(unittest.TestCase):
    def test_combine_prepends_briefing(self):
        from sr_processor.prompt import combine_framework_and_prompt

        out = combine_framework_and_prompt("Four dimensions of dyadicness.", "Return JSON only.")
        self.assertIn("FRAMEWORK BRIEFING", out)
        self.assertIn("Four dimensions of dyadicness.", out)
        self.assertIn("CODING INSTRUCTIONS", out)
        self.assertIn("Return JSON only.", out)
        self.assertTrue(out.index("FRAMEWORK BRIEFING") < out.index("CODING INSTRUCTIONS"))

    def test_combine_without_briefing_is_protocol_only(self):
        from sr_processor.prompt import combine_framework_and_prompt

        self.assertEqual(combine_framework_and_prompt("  ", "Return JSON only."), "Return JSON only.")


if __name__ == "__main__":
    unittest.main()
