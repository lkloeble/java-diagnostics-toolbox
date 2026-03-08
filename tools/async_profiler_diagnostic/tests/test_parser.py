# tests/test_parser.py

from async_profiler_diagnostic.parser import parse_collapsed, validate_collapsed


def test_parse_sample_total_samples(sample_collapsed):
    profile = parse_collapsed(sample_collapsed)
    assert profile.total_samples == 147


def test_parse_sample_num_stacks(sample_collapsed):
    profile = parse_collapsed(sample_collapsed)
    assert len(profile.stacks) == 10


def test_parse_minimal_total_samples(minimal_collapsed):
    profile = parse_collapsed(minimal_collapsed)
    assert profile.total_samples == 4


def test_parse_minimal_num_stacks(minimal_collapsed):
    profile = parse_collapsed(minimal_collapsed)
    assert len(profile.stacks) == 3


def test_parse_leaf_frame(minimal_collapsed):
    profile = parse_collapsed(minimal_collapsed)
    watcher = next(s for s in profile.stacks if s.count == 2)
    assert watcher.frames[-1] == "__psynch_cvwait"
    assert watcher.frames[0] == "thread_start"


def test_parse_single_frame_stack():
    profile = parse_collapsed("gc/harness/MemoryBehaviorApp.main 1\n")
    assert len(profile.stacks) == 1
    assert profile.stacks[0].frames == ["gc/harness/MemoryBehaviorApp.main"]
    assert profile.stacks[0].count == 1


def test_parse_skips_comment_lines():
    content = "# this is a comment\nfoo;bar 5\n"
    profile = parse_collapsed(content)
    assert len(profile.stacks) == 1
    assert profile.total_samples == 5


def test_parse_skips_empty_lines():
    content = "\n\nfoo;bar 3\n\nbaz 2\n"
    profile = parse_collapsed(content)
    assert profile.total_samples == 5


def test_parse_skips_invalid_count():
    content = "foo;bar notanumber\nfoo;baz 5\n"
    profile = parse_collapsed(content)
    assert len(profile.stacks) == 1


def test_parse_empty():
    profile = parse_collapsed("")
    assert profile.total_samples == 0
    assert len(profile.stacks) == 0


def test_parse_frame_order():
    # frames[0] = root, frames[-1] = leaf
    profile = parse_collapsed("root;middle;leaf 3\n")
    assert profile.stacks[0].frames == ["root", "middle", "leaf"]


def test_validate_valid(minimal_collapsed):
    assert validate_collapsed(minimal_collapsed) is True


def test_validate_sample(sample_collapsed):
    assert validate_collapsed(sample_collapsed) is True


def test_validate_empty():
    assert validate_collapsed("") is False


def test_validate_invalid_text():
    assert validate_collapsed("this is not a collapsed stacks file\nsome random text\n") is False


def test_validate_single_valid_line():
    assert validate_collapsed("gc/harness/App.main 1\n") is True
