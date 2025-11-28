from subprocess import check_output
from textwrap import dedent

from sybil import Sybil
from sybil.parsers.markdown import CodeBlockParser, PythonCodeBlockParser


class BashCodeBlockParser(CodeBlockParser):
    language = "bash"

    def evaluate(self, example):
        command, expected = dedent(example.parsed).strip().split("\n")
        actual = check_output(command[2:].split()).strip().decode("ascii")
        assert actual == expected, repr(actual) + " != " + repr(expected)


pytest_collect_file = Sybil(
    parsers=[
        BashCodeBlockParser(),
        PythonCodeBlockParser(),
    ],
    patterns=["*.md"],
).pytest()
