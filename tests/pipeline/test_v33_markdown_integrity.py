"""Phase 3.3 — Markdown integrity tests for the deterministic normalization layer.

Covers the structural repair contract (spec §16): headings, paragraph
separation, lists, tables, code, code protection, horizontal rules, mixed
content, Unicode, URLs, idempotency, and the real Kubernetes regression
structure (spec §17). Word/space glue that would require dictionary-based
reconstruction is explicitly NOT repaired and must be left untouched.
"""

import pytest

from app.agent.pipeline.markdown_integrity import normalize_markdown


# ---------------------------------------------------------------------------
# Headings (spec §1)
# ---------------------------------------------------------------------------

class TestHeadings:
    def test_heading_space_inserted(self):
        assert normalize_markdown("###Title") == "### Title"

    def test_heading_space_with_question(self):
        assert normalize_markdown("###Title?text") == "### Title?text"

    def test_valid_heading_untouched(self):
        assert normalize_markdown("### Heading") == "### Heading"

    def test_non_heading_hashes_untouched(self):
        # 7+ hashes is not a heading; single `#` mid-word is not a heading.
        assert normalize_markdown("#######x") == "#######x"
        assert normalize_markdown("a# b") == "a# b"
        assert normalize_markdown("use 2# tags and 100% effort.") == "use 2# tags and 100% effort."

    def test_heading_glued_to_prose_splits(self):
        assert normalize_markdown("text### Heading") == "text\n\n### Heading"

    def test_heading_after_colon_splits(self):
        # Spec example: Core concepts:#### 1. Roles
        expected = "Core concepts:\n\n#### 1. Roles"
        assert normalize_markdown("Core concepts:#### 1. Roles") == expected

    def test_heading_level_preserved(self):
        assert normalize_markdown("intro## Level Two") == "intro\n\n## Level Two"

    def test_heading_already_on_own_line_untouched(self):
        # A heading already separated by a newline is valid Markdown; the
        # normalizer never rewrites existing (non-glued) structure.
        src = "intro\n#### Level Four"
        assert normalize_markdown(src) == src

    def test_heading_inside_url_not_split(self):
        # URL-ish context must never be treated as glued prose (spec §9).
        assert normalize_markdown(
            "See https://kubernetes.io/docs/concepts/services-networking/service## Notes"
        ) == "See https://kubernetes.io/docs/concepts/services-networking/service## Notes"


# ---------------------------------------------------------------------------
# Paragraph boundaries (spec §2)
# ---------------------------------------------------------------------------

class TestParagraphs:
    def test_normal_prose_untouched(self):
        src = "Kubernetes Services provide stable networking.\n\nPods are ephemeral."
        assert normalize_markdown(src) == src

    def test_word_space_glue_not_repaired(self):
        # Dictionary-based word reconstruction is forbidden (spec §2). If the
        # stream already lost the space, we must NOT guess a reconstruction.
        assert normalize_markdown("Labelsand Selectors") == "Labelsand Selectors"
        assert normalize_markdown("changefrequently") == "changefrequently"

    def test_blank_lines_preserved(self):
        src = "para one\n\n\npara two"
        assert normalize_markdown(src) == src


# ---------------------------------------------------------------------------
# Lists (spec §3)
# ---------------------------------------------------------------------------

class TestLists:
    def test_unordered_untouched(self):
        src = "- Item one\n- Item two\n- Item three"
        assert normalize_markdown(src) == src

    def test_ordered_untouched(self):
        src = "1. First\n2. Second\n3. Third"
        assert normalize_markdown(src) == src

    def test_nested_untouched(self):
        src = "- parent\n  - child\n  - child2\n- sibling"
        assert normalize_markdown(src) == src

    def test_list_with_inline_code_and_links_untouched(self):
        src = "- run `kubectl get svc`\n- see [docs](https://kubernetes.io/docs/)"
        assert normalize_markdown(src) == src

    def test_list_after_heading_untouched(self):
        src = "## Features\n\n- one\n- two"
        assert normalize_markdown(src) == src


# ---------------------------------------------------------------------------
# Tables (spec §4)
# ---------------------------------------------------------------------------

class TestTables:
    def test_table_untouched(self):
        src = (
            "| Service Type | Scope | Purpose |\n"
            "|---|---|---|\n"
            "| ClusterIP | Internal | Internal communication |\n"
            "| NodePort | External | Node-level exposure |"
        )
        assert normalize_markdown(src) == src

    def test_table_with_code_and_links_untouched(self):
        src = (
            "| A | B |\n"
            "|---|---|\n"
            "| `kubectl apply` | [link](https://k8s.io/x) |\n"
            "| long cell with lots of text | ok |"
        )
        assert normalize_markdown(src) == src


# ---------------------------------------------------------------------------
# Code blocks (spec §5) and fence integrity (spec §6)
# ---------------------------------------------------------------------------

class TestCode:
    def test_yaml_block_untouched_even_glued_indentation(self):
        src = (
            "```yaml\n"
            "apiVersion: v1\n"
            "kind: Service\n"
            "metadata:\n"
            "  name: web\n"
            "spec:\n"
            "  type: ClusterIP\n"
            "```"
        )
        assert normalize_markdown(src) == src

    def test_python_block_untouched_indentation_exact(self):
        src = "```python\ndef hello():\n    print(\"hello\")\n```"
        assert normalize_markdown(src) == src

    def test_terraform_block_untouched(self):
        src = (
            '```hcl\n'
            'resource "aws_s3_bucket" "example" {\n'
            '  bucket = "example"\n'
            "}\n"
            "```"
        )
        assert normalize_markdown(src) == src

    def test_fence_opener_glued_to_prose_splits(self):
        # Spec §8: Here is the configuration:```yaml
        src = "Here is the configuration:```yaml\napiVersion: v1\n```"
        out = normalize_markdown(src)
        assert "Here is the configuration:" in out
        assert "```yaml" in out
        # The fence opener must be on its own line with a blank line before it.
        assert "configuration:\n\n```yaml" in out
        assert out.endswith("```")

    def test_code_protection_inside_fence(self):
        # Malformed-markdown-looking content inside a fence must be unchanged.
        src = (
            "```markdown\n"
            "### Title\n"
            "x---y\n"
            "text```not-a-closer\n"
            "---\n"
            "```"
        )
        assert normalize_markdown(src) == src

    def test_glued_closer_left_untouched(self):
        # A closing fence glued to the last code line is content (spec §15:
        # never normalize inside fenced code). Left as-is, conservatively.
        src = "```py\nprint('hi')```\nnext paragraph"
        assert normalize_markdown(src) == src

    def test_fence_round_trip_through_normalization(self):
        src = (
            "before\n\n```yaml\napiVersion: v1\nkind: Service\n```\n\nafter"
        )
        assert normalize_markdown(src) == src


# ---------------------------------------------------------------------------
# Horizontal rules (spec §7)
# ---------------------------------------------------------------------------

class TestHorizontalRules:
    def test_public_internet_glued_rule_and_heading(self):
        # Spec §7: necessary.---### Core Concepts
        expected = "necessary.\n\n---\n\n### Core Concepts"
        assert normalize_markdown("necessary.---### Core Concepts") == expected

    def test_standalone_rule_untouched(self):
        src = "paragraph\n\n---\n\n## Heading"
        assert normalize_markdown(src) == src

    def test_glued_rule_at_end_of_line(self):
        assert normalize_markdown("text.---") == "text.\n\n---"

    def test_overly_glued_mid_line_dashes_untouched(self):
        # Not followed by a heading or line end — conservative, leave alone.
        assert normalize_markdown("a---b") == "a---b"


# ---------------------------------------------------------------------------
# Mixed content (spec §16)
# ---------------------------------------------------------------------------

class TestMixed:
    def test_full_response_structure(self):
        src = (
            "# Title\n\n"
            "Paragraph text.\n\n"
            "- one\n- two\n\n"
            "| H | V |\n|---|---|\n| a | b |\n\n"
            "```python\nprint(1)\n```\n\n"
            "See [k8s docs](https://kubernetes.io/docs/).\n\n"
            "---\n\n"
            "## Next Section"
        )
        assert normalize_markdown(src) == src

    def test_character_glued_full_response(self):
        # Simulates the observed defect classes from production testing that
        # this deterministic layer is responsible for: prose→heading glue and
        # the horizontal-rule glue. Word glue and in-fence content are left
        # untouched by design.
        src = (
            "What is a Kubernetes Service? In Kubernetes, a Service is an "
            "abstractionthat defines a logical set of pods.\n\n"
            "```yaml\napiVersion: v1kind: Service\n```\n\n"
            "necessary.---### Core Concepts"
        )
        out = normalize_markdown(src)
        assert "abstractionthat" in out  # word glue is not dictionary-repaired
        assert "apiVersion: v1kind: Service" in out  # in-fence content untouched
        assert "necessary.\n\n---\n\n### Core Concepts" in out


# ---------------------------------------------------------------------------
# Unicode (spec §10)
# ---------------------------------------------------------------------------

class TestUnicode:
    def test_unicode_preserved(self):
        src = "Grid: 🚀 ₹ → ≥ ≤ × ± and multilingual: héllo wörld 中文"
        assert normalize_markdown(src) == src

    def test_unicode_inside_fence_preserved(self):
        src = "```\n🚀 ₹ → ≥ ≤ × ±\n```"
        assert normalize_markdown(src) == src

    def test_unicode_heading_glue_fixed(self):
        assert normalize_markdown("##标题部分") == "## 标题部分"


# ---------------------------------------------------------------------------
# URLs and citations (spec §9)
# ---------------------------------------------------------------------------

class TestUrls:
    def test_urls_byte_equivalent(self):
        src = (
            "[ Kubernetes Documentation ](https://kubernetes.io/docs/concepts/"
            "services-networking/service/) and https://raw.githubusercontent.com/x/y"
        )
        assert normalize_markdown(src) == src

    def test_citation_markers_untouched(self):
        src = "Pods are scheduled automatically. [Chunk 1] [Chunk 2]"
        assert normalize_markdown(src) == src


# ---------------------------------------------------------------------------
# Idempotency (spec §14)
# ---------------------------------------------------------------------------

class TestIdempotency:
    @pytest.mark.parametrize(
        "sample",
        [
            "###Title",
            "text### Heading",
            "Core concepts:#### 1. Roles",
            "necessary.---### Core Concepts",
            "Here is the configuration:```yaml\napiVersion: v1\n```",
            "See https://kubernetes.io/docs/concepts/services-networking/service## Notes",
            "### What is a Kubernetes Service?In Kubernetes, a Service is an abstraction.",
            "```markdown\n### Title\nx---y\n```",
            "🚀 ₹ → ≥ ≤ × ±",
        ],
    )
    def test_idempotent(self, sample):
        once = normalize_markdown(sample)
        assert normalize_markdown(once) == once


# ---------------------------------------------------------------------------
# Real regression structure (spec §17) — structure, not wording
# ---------------------------------------------------------------------------

class TestRealRegression:
    def test_regression_structure_is_valid(self):
        out = normalize_markdown(
            "### What is a Kubernetes Service?\n\nIn Kubernetes, a Service is an "
            "abstraction that exposes a logical set of pods.\n\n"
            "#### Key Mechanics\n"
            "- **Labels & Selectors**\n"
            "- **Endpoints / EndpointSlices**\n"
            "- **Kube-Proxy**\n\n"
            "necessary.---### Types of Kubernetes Services\n\n"
            "| Service Type | Scope | Description |\n|---|---|---|\n"
            "| ClusterIP | Internal | Default |\n\n"
            "```yaml\napiVersion: v1\nkind: Service\nmetadata:\n  name: web-backend-service\n```\n\n"
            "### What is Kubernetes RBAC?\n\n"
            "#### Core Concepts\n\n"
            "- Roles\n- RoleBindings\n"
        )
        lines = out.split("\n")
        assert "### What is a Kubernetes Service?" in lines
        assert "#### Key Mechanics" in lines
        assert "#### Key Mechanics" in out
        assert "- **Labels & Selectors**" in lines
        assert "necessary." in lines
        assert "---" in lines
        assert "### Types of Kubernetes Services" in lines
        assert "| Service Type | Scope | Description |" in lines
        assert out.count("```") == 2  # YAML block opened and closed
        assert "apiVersion: v1" in out
        assert "kind: Service" in out
        assert "metadata:" in out
        assert "  name: web-backend-service" in out
        assert "### What is Kubernetes RBAC?" in lines
        assert "#### Core Concepts" in lines