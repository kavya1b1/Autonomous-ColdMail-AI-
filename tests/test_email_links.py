from utils.email_links import normalize_email_links


def test_strips_leetcode_and_gfg():
    body = "Hi,\n\nLeetCode: https://leetcode.com/u/x\nGeeksforGeeks: https://geeksforgeeks.org/user/x\n\nBest"
    out = normalize_email_links(body, linkedin="https://linkedin.com/in/x", github=None, portfolio=None)
    assert "leetcode" not in out.lower()
    assert "geeksforgeeks" not in out.lower()
    assert out.count("linkedin.com/in/x") == 1


def test_dedupes_repeated_links():
    body = (
        "Hi,\n\nLinkedIn: https://linkedin.com/in/x\nLinkedIn https://linkedin.com/in/x\n"
        "Portfolio: https://x.dev\nPortfolio https://x.dev\n\nBest"
    )
    out = normalize_email_links(body, linkedin="https://linkedin.com/in/x", github=None, portfolio="https://x.dev")
    assert out.count("linkedin.com/in/x") == 1
    assert out.count("x.dev") == 1


def test_removes_arbitrary_urls_including_inline():
    body = "Hi,\n\nCheck my blog post: https://random-blog.com/post/1 for details.\n\nBest"
    out = normalize_email_links(body, linkedin=None, github=None, portfolio=None)
    assert "random-blog" not in out
    assert "https://" not in out


def test_never_invents_missing_links():
    out = normalize_email_links("Hello there.", linkedin="https://linkedin.com/in/x", github=None, portfolio=None)
    assert "GitHub" not in out
    assert "Portfolio" not in out
    assert out.endswith("LinkedIn: https://linkedin.com/in/x")


def test_footer_labels_and_order():
    out = normalize_email_links(
        "Body text.",
        linkedin="https://linkedin.com/in/x",
        github="https://github.com/x",
        portfolio="https://x.dev",
    )
    lines = [l for l in out.split("\n") if l.strip()]
    assert lines[-3] == "LinkedIn: https://linkedin.com/in/x"
    assert lines[-2] == "GitHub: https://github.com/x"
    assert lines[-1] == "Portfolio: https://x.dev"
