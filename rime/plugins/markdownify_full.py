#!/usr/bin/python
# -*- coding: utf-8 -*-

import codecs
import getpass
import hashlib
import os
import os.path
import socket
import sys

from enum import Enum
from jinja2 import Environment
from jinja2 import FileSystemLoader

if sys.version_info[0] == 2:
    import commands as builtin_commands  # NOQA
else:
    import subprocess as builtin_commands

from rime.basic import codes as basic_codes  # NOQA
from rime.basic import consts  # NOQA
import rime.basic.targets.project  # NOQA
from rime.basic import test  # NOQA
from rime.core import commands as rime_commands  # NOQA
from rime.core import targets  # NOQA
from rime.core import taskgraph  # NOQA


class ItemState(Enum):
    GOOD, NOTBAD, BAD, NA = range(4)


def GetFileSize(dir, filename):
    filepath = os.path.join(dir, filename)
    if os.path.exists(filepath):
        return '%dB' % os.path.getsize(filepath)
    else:
        return '-'


def GetFileHash(dir, filename):
    filepath = os.path.join(dir, filename)
    if os.path.exists(filepath):
        f = open(filepath)
        r = f.read()
        f.close()
        return hashlib.md5(r.encode('utf-8')).hexdigest()
    else:
        return ''


def GetMarkdownifyFileComment(dir, filename):
    filepath = os.path.join(dir, filename)
    if os.path.exists(filepath):
        f = open(filepath)
        r = f.read().strip()
        f.close()
        return r
    else:
        return ''


class Project(targets.registry.Project):
    @taskgraph.task_method
    def MarkdownifyFull(self, ui):
        markdown = yield self._GenerateMarkdownFull(ui)
        codecs.open('summary.md', 'w', 'utf8').write(markdown)
        yield None

    @taskgraph.task_method
    def _GenerateMarkdownFull(self, ui):
        if not ui.options.skip_clean:
            yield self.Clean(ui)

        jinja_env = Environment(loader=FileSystemLoader(
            os.path.join(self.base_dir, 'rime/plugins/'), encoding='utf8'))
        template = jinja_env.get_template('markdownify.md.ninja')
        template.globals['ItemState'] = ItemState

        # Get system information.
        system = {
            'rev': builtin_commands.getoutput(
                'git show -s --oneline').replace('\n', ' ').replace('\r', ' '),
            'username': getpass.getuser(),
            'hostname': socket.gethostname(),
        }

        cc = os.getenv('CC', 'gcc')
        cxx = os.getenv('CXX', 'g++')
        java_home = os.getenv('JAVA_HOME')
        if java_home is not None:
            java = os.path.join(java_home, 'bin/java')
            javac = os.path.join(java_home, 'bin/javac')
        else:
            java = 'java'
            javac = 'javac'

        environments = [
            {
                'type': 'gcc',
                'detail': builtin_commands.getoutput(
                    '{0} --version'.format(cc)).strip(),
            }, {
                'type': 'g++',
                'detail': builtin_commands.getoutput(
                    '{0} --version'.format(cxx)).strip(),
            }, {
                'type': 'javac',
                'detail': builtin_commands.getoutput(
                    '{0} --version'.format(javac)).strip(),
            }, {
                'type': 'java',
                'detail': builtin_commands.getoutput(
                    '{0} --version'.format(java)).strip(),
            }]

        # Generate content.
        problems = yield taskgraph.TaskBranch([
            self._GenerateMarkdownFullOne(problem, ui)
            for problem in self.problems])

        errors = ui.errors.errors if ui.errors.HasError() else []
        warnings = ui.errors.warnings if ui.errors.HasWarning() else []

        content = template.render(
            system=system, environments=environments,
            problems=problems, errors=errors, warnings=warnings)

        yield content

    @taskgraph.task_method
    def _GenerateMarkdownFullOne(self, problem, ui):
        yield problem.Build(ui)

        # Get various information about the problem.
        solutions = []
        testnames = set()
        results = []
        for solution in sorted(problem.solutions, key=lambda x: x.name):
            test_result = (yield problem.testset.TestSolution(solution, ui))[0]
            verdicts = {}
            for (testcase, result) in test_result.results.items():
                testname = os.path.splitext(
                    os.path.basename(testcase.infile))[0]
                testnames.add(testname)
                verdicts[testname] = self._GetMarkdownifyVerdict(
                    result.verdict, result.time)
            results.append(test_result)
            solutions.append({
                'name': solution.name,
                'verdicts': verdicts,
            })

        # Populate missing results with NA.
        empty_verdict = self._GetMarkdownifyVerdict(
            test.TestCaseResult.NA, '')
        for solution in solutions:
            for testname in testnames:
                if testname not in solution['verdicts']:
                    solution['verdicts'][testname] = empty_verdict

        # Test case informations.
        out_dir = problem.testset.out_dir
        testcases = [{
            'name': testname,
            'insize': GetFileSize(out_dir, testname + consts.IN_EXT),
            'outsize': GetFileSize(out_dir, testname + consts.DIFF_EXT),
            'md5': GetFileHash(out_dir, testname + consts.IN_EXT)[:7],
            'comment': GetMarkdownifyFileComment(
                out_dir, testname + '.comment'),
        } for testname in sorted(testnames)]

        # Get summary about the problem.
        assignees = problem.assignees
        if isinstance(assignees, list):
            assignees = ','.join(assignees)

        num_solutions = len(results)
        num_tests = len(problem.testset.ListTestCases())
        correct_solution_results = [result for result in results
                                    if result.solution.IsCorrect()]
        num_corrects = len(correct_solution_results)
        num_incorrects = num_solutions - num_corrects
        num_agreed = len([result for result in correct_solution_results
                          if result.expected])
        need_custom_judge = problem.need_custom_judge

        # Solutions:
        if num_corrects >= 2:
            solutions_state = ItemState.GOOD
        elif num_corrects >= 1:
            solutions_state = ItemState.NOTBAD
        else:
            solutions_state = ItemState.BAD

        # Input:
        if num_tests >= 20:
            inputs_state = ItemState.GOOD
        else:
            inputs_state = ItemState.BAD

        # Output:
        if num_corrects >= 2 and num_agreed == num_corrects:
            outputs_state = ItemState.GOOD
        elif num_agreed >= 2:
            outputs_state = ItemState.NOTBAD
        else:
            outputs_state = ItemState.BAD

        # Validator:
        if problem.testset.validators:
            validator_state = ItemState.GOOD
        else:
            validator_state = ItemState.BAD

        # Judge:
        if need_custom_judge:
            custom_judges = [
                judge for judge in problem.testset.judges
                if judge.__class__ != basic_codes.InternalDiffCode]
            if custom_judges:
                judge_state = ItemState.GOOD
            else:
                judge_state = ItemState.BAD
        else:
            judge_state = ItemState.NA

        # Done.
        yield {
            'title': problem.title or 'No Title',
            'solutions': solutions,
            'testcases': testcases,
            'assignees': assignees,
            'solution_state': {
                'status': solutions_state,
                'detail': '%d+%d' % (num_corrects, num_incorrects),
            },
            'input_state': {
                'status': inputs_state,
                'detail': str(num_tests),
            },
            'output_state': {
                'status': outputs_state,
                'detail': '%d/%d' % (num_agreed, num_corrects),
            },
            'validator': validator_state,
            'judge': judge_state,
        }

    def _GetMarkdownifyVerdict(self, verdict, time):
        if verdict is test.TestCaseResult.NA:
            return {'status': ItemState.NA, 'detail': str(verdict)}
        elif time is None:
            return {'status': ItemState.BAD, 'detail': str(verdict)}
        else:
            return {'status': ItemState.GOOD, 'detail': '%.2fs' % (time)}


class MarkdownifyFull(rime_commands.CommandBase):
    def __init__(self, parent):
        super(MarkdownifyFull, self).__init__(
            'markdownify_full',
            '',
            'Markdownify full plugin',
            '',
            parent)
        self.AddOptionEntry(rime_commands.OptionEntry(
            's', 'skip_clean', 'skip_clean', bool, False, None,
            'Skip cleaning generated files up.'
        ))

    def Run(self, obj, args, ui):
        if args:
            ui.console.PrintError(
                'Extra argument passed to markdownify_full command!')
            return None

        if isinstance(obj, Project):
            return obj.MarkdownifyFull(ui)

        ui.console.PrintError(
            'Markdownify_full is not supported for the specified target.')
        return None


targets.registry.Override('Project', Project)

rime_commands.registry.Add(MarkdownifyFull)
