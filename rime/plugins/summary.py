#!/usr/bin/python
# -*- coding: utf-8 -*-

import os
import hashlib
import sys
import socket
import getpass

from itertools import groupby
from enum import Enum

if sys.version_info[0] == 2:
    import commands as builtin_commands  # NOQA
else:
    import subprocess as builtin_commands

from rime.basic import consts  # NOQA
from rime.basic import codes as basic_codes  # NOQA
from rime.basic import test  # NOQA


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


def GetSummaryFileComment(dir, filename):
    filepath = os.path.join(dir, filename)
    if os.path.exists(filepath):
        f = open(filepath)
        r = f.read().strip()
        f.close()
        return r
    else:
        return ''


def GetTestCaseState(result):
    """Generate per testcase result object for summary from TestCaseResult."""
    if result.verdict is test.TestCaseResult.NA:
        return {'status': ItemState.NA, 'detail': str(result.verdict)}
    elif result.verdict is test.TestCaseResult.AC:
        return {'status': ItemState.GOOD, 'detail': '%.2fs' % (result.time)}
    else:
        return {'status': ItemState.BAD, 'detail': str(result.verdict)}


def GenerateSummary(results, ui):
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
    problems = [GenerateSummaryOne(k, g) 
                for k, g in groupby(results, lambda k: k.problem)]

    return {
        'system': system,
        'environments': environments,
        'problems': list(problems),
        'errors': ui.errors.errors if ui.errors.HasError() else [],
        'warnings': ui.errors.warnings if ui.errors.HasWarning() else []
    }

def GenerateSummaryOne(problem, testset_results):
    testset_results = list(sorted(testset_results, key=lambda x: x.solution.name))

    # Get test results from each testset (i.e. per solution)
    solutions = []
    testnames = set()
    for testset in testset_results:
        verdicts = {}
        for (testcase, result) in testset.results.items():
            testname = os.path.splitext(
                os.path.basename(testcase.infile))[0]
            testnames.add(testname)
            verdicts[testname] = GetTestCaseState(result)
        solutions.append({
            'name': testset.solution.name,
            'verdicts': verdicts,
        })

    # Populate missing results with NA.
    empty_verdict = test.TestCaseResult(
        None, None, test.TestCaseResult.NA, None, None)
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
        'comment': GetSummaryFileComment(
            out_dir, testname + '.comment'),
    } for testname in sorted(testnames)]

    # Get summary about the problem.
    assignees = problem.assignees
    if isinstance(assignees, list):
        assignees = ','.join(assignees)

    num_solutions = len(solutions)
    num_tests = len(problem.testset.ListTestCases())
    correct_solution_results = [result for result in testset_results
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
    return {
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
