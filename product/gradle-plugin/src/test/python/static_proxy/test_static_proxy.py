from __future__ import absolute_import, division, print_function

import json
import os
from os.path import abspath, dirname, join
import subprocess
from unittest import TestCase


static_proxy_dir = abspath(dirname(__file__))
data_dir = join(static_proxy_dir, "data")
main_python_dir = abspath(join(static_proxy_dir, "../../../main/python"))
os.environ["PYTHONPATH"] = main_python_dir


class TestStaticProxy(TestCase):

    maxDiff = None

    def test_find_module(self):
        self.run_json("nonexistent", "file", False, "nonexistent' does not exist")
        self.run_json("errors/empty.py", "file", False, "errors/empty.py' is not a directory")

        self.run_json(["find_module/path1", "find_module/path2"], ["a", "b", "c"],
                      expected="find_module/12.json")
        self.run_json(["find_module/path2", "find_module/path1"], ["a", "b", "c"],
                      expected="find_module/21.json")

        self.run_json("find_module/path3", "mod1")          # Exists as both module and package
        self.run_json("find_module/path3", "mod1.mod1a")
        self.run_json("find_module/path3", "mod99", False, "Module not found: mod99")
        self.run_json("find_module/path3", "empty", False, "Module not found: empty")
        self.run_json("find_module/path3", "no_init_py.mod", False,
                      "Module not found: no_init_py.mod")

    def test_errors(self):
        for name in ["empty", "no_proxies", "conditional"]:
            self.run_json("errors", name, False, name + ".py: no static_proxy classes found")
        self.run_json("errors", "syntax", False, "syntax.py:3:7: invalid syntax")

    def test_bindings(self):
        self.run_json("bindings", "import_from")
        self.run_json("bindings", "import_module")
        self.run_json("bindings", "import_module_as")
        self.run_json("bindings", "late", False,
                      "late.py:4:22: cannot resolve 'C' (binding not found)")
        self.run_json("bindings", "del", False,
                      "del.py:7:22: cannot resolve 'Class1' (binding not found)")
        self.run_json("bindings", "class", False,
                      "class.py:7:22: cannot resolve 'C' \(bound at .*class.py:4:1\)", re=True)
        self.run_json("bindings", "def", False,
                      "def.py:7:22: cannot resolve 'f' \(bound at .*def.py:4:1\)", re=True)
        self.run_json("bindings", "assign", False,
                      "assign.py:6:22: cannot resolve 'C' \(bound at .*assign.py:4:1\)", re=True)
        self.run_json("bindings", "assign_list", False, "assign_list.py:6:22: cannot resolve 'C' "
                      "\(bound at .*assign_list.py:4:4\)", re=True)
        self.run_json("bindings", "assign_list_recursive", False, "assign_list_recursive.py:6:22: "
                      "cannot resolve 'C' \(bound at .*assign_list_recursive.py:4:8\)", re=True)
        self.run_json("bindings", "assign_aug", False, "assign_aug.py:7:22: cannot resolve 'C' "
                      "\(bound at .*assign_aug.py:5:1\)", re=True)

    def test_header(self):
        self.run_json("header", "bases")
        self.run_json("header", "package")
        self.run_json("header", "modifiers")

    def test_constructor(self):
        self.run_json("constructor", "constructor")
        self.run_json("constructor", "name", False,
                      "name.py:5:6: @constructor can only be used on __init__")
        self.run_json("constructor", "return", False, "return.py:5:6: constructor\(\) takes "
                      "exactly 1 arguments? \(2 given\)", re=True)

    def test_method(self):
        self.run_json("method", "return")
        self.run_json("method", "args")
        self.run_json("method", "throws")
        self.run_json("method", "modifiers")
        self.run_json("method", "overload")
        self.run_json("method", "init_method", False,
                      "init_method.py:5:6: @method cannot be used on __init__")
        self.run_json("method", "init_override", False,
                      "init_override.py:5:6: @Override cannot be used on __init__")
        self.run_json("method", "missing_brackets", False, "missing_brackets.py:5:6: 'arg_types' "
                      "must be (<type 'list'>, <type 'tuple'>)")
        self.run_json("method", "missing_args", False,
                      "missing_args.py:5:6: method() takes at least 2 arguments")

    def run_json(self, path, modules, succeed=True, expected=None, **kwargs):
        if isinstance(path, str):
            path = [path]
        if isinstance(modules, str):
            modules = [modules]
        if succeed and (expected is None):
            assert len(path) == 1 and len(modules) == 1
            expected = join(path[0], modules[0].replace(".", "/")) + ".json"

        process = subprocess.Popen(
            ["python", join(main_python_dir, "chaquopy/static_proxy.py"),
             "--path", os.pathsep.join(join(data_dir, d) for d in path),
             "--json"] + modules,
            stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        stdout, stderr = process.communicate()

        status = process.wait()
        if status == 0:
            if not succeed:
                self.dump_run("run unexpectedly succeeded", stdout, stderr)
            try:
                result = json.loads(stdout)
            except ValueError:
                print("Invalid output\n" + stdout)
                raise
            self.assertEqual(json.load(open(join(data_dir, expected))), result)
        else:
            if succeed:
                self.dump_run("exit status {}".format(status), stdout, stderr)
            self.assertInLong(expected, stderr, **kwargs)

    def dump_run(self, msg, stdout, stderr):
        self.fail(msg + "\n" +
                  "=== STDOUT ===\n" + stdout +
                  "=== STDERR ===\n" + stderr)

    # Prints b as a multi-line string rather than a repr().
    def assertInLong(self, a, b, re=False):
        try:
            if re:
                self.assertRegexpMatches(b, a)
            else:
                self.assertIn(a, b)
        except AssertionError:
            raise AssertionError("{} '{}' not found in:\n{}"
                                 .format(("regexp" if re else "string"), a, b))
