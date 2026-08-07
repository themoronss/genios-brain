from __future__ import annotations

from genios_engine.platform.migrate import _split_statements

# The migration runner split SQL on a naive sql.split(";"), which broke on a ';' INSIDE a string
# literal (COMMENT ON ... IS '…;…') or a $$ function body — a bug that only surfaced on a real
# Postgres run and blocked every L2 migration. The splitter must honour strings, $$ bodies and
# -- line comments.


def test_splits_on_top_level_semicolons():
    assert _split_statements("create table a(x int); create table b(y int);") == \
        ["create table a(x int)", "create table b(y int)"]


def test_semicolon_inside_a_string_literal_is_not_a_split():
    sql = "comment on table t is 'one; two; three'; create table a(x int);"
    assert _split_statements(sql) == ["comment on table t is 'one; two; three'", "create table a(x int)"]


def test_escaped_quote_inside_string():
    sql = "insert into t values ('it''s; fine'); select 1;"
    assert _split_statements(sql) == ["insert into t values ('it''s; fine')", "select 1"]


def test_dollar_quoted_body_with_semicolons_stays_one_statement():
    sql = ("create function f() returns int as $$ begin; return 1; end; $$ language plpgsql;"
           " select 1;")
    stmts = _split_statements(sql)
    assert len(stmts) == 2 and "return 1; end;" in stmts[0] and stmts[1] == "select 1"


def test_line_comment_with_a_semicolon_is_ignored():
    sql = "select 1; -- a comment; with a semicolon\nselect 2;"
    assert _split_statements(sql) == ["select 1", "select 2"]


def test_trailing_statement_without_semicolon_is_kept():
    assert _split_statements("select 1;\nselect 2") == ["select 1", "select 2"]
