#!/usr/bin/python

import os
import os.path
import shutil
import time
import requests

from rime.basic import consts
from rime.core import targets
from rime.core import taskgraph
from rime.plugins.plus import commands as plus_commands
from rime.util import files


class Project(targets.registry.Project):
    def PreLoad(self, ui):
        super(Project, self).PreLoad(ui)
        self.domjudge_config_defined = False

        def _domjudge_config(url, contest_id, username, password):
            self.domjudge_config_defined = True
            self.domjudge_url = url
            self.domjudge_contest_id = contest_id
            self.domjudge_username = username
            self.domjudge_password = password
        self.exports['domjudge_config'] = _domjudge_config


class Testset(targets.registry.Testset):
    def __init__(self, *args, **kwargs):
        super(Testset, self).__init__(*args, **kwargs)
        self.domjudge_pack_dir = os.path.join(self.problem.out_dir, 'domjudge')


class DOMJudgePacker(plus_commands.PackerBase):
    @taskgraph.task_method
    def Pack(self, ui, testset):
        testcases = testset.ListTestCases()
        try:
            files.RemoveTree(testset.domjudge_pack_dir)
            files.MakeDir(testset.domjudge_pack_dir)
            files.MakeDir(os.path.join(testset.domjudge_pack_dir, 'data'))
            files.MakeDir(os.path.join(testset.domjudge_pack_dir, 'data',
                                       'sample'))
            files.MakeDir(os.path.join(testset.domjudge_pack_dir, 'data',
                                       'secret'))

            # Generate problem.yaml
            yaml_file = os.path.join(testset.domjudge_pack_dir, 'problem.yaml')
            with open(yaml_file, 'w') as f:
                f.write('name: {}\n'.format(testset.problem.name))
        except Exception:
            ui.errors.Exception(testset)
            yield False
        for (i, testcase) in enumerate(testcases):
            basename = os.path.splitext(os.path.basename(testcase.infile))[0]
            difffile = basename + consts.DIFF_EXT
            packed_infile = basename + ".in"
            packed_difffile = basename + ".ans"
            is_sample = 'sample' in packed_infile
            packed_files_dir = os.path.join(
                testset.domjudge_pack_dir, 'data',
                'sample' if is_sample else 'secret')

            try:
                ui.console.PrintAction(
                    'PACK',
                    testset,
                    '%s -> %s' % (os.path.basename(testcase.infile),
                                  packed_infile),
                    progress=True)
                files.CopyFile(os.path.join(testset.out_dir, testcase.infile),
                               os.path.join(packed_files_dir, packed_infile))
                ui.console.PrintAction(
                    'PACK',
                    testset,
                    '%s -> %s' % (os.path.basename(difffile), packed_difffile),
                    progress=True)
                files.CopyFile(
                    os.path.join(testset.out_dir, testcase.difffile),
                    os.path.join(packed_files_dir, packed_difffile))
            except Exception:
                ui.errors.Exception(testset)
                yield False

        # Create a zip file
        # TODO(chiro): Add problem.pdf
        try:
            shutil.make_archive(
                os.path.join(testset.domjudge_pack_dir, testset.problem.id),
                'zip',
                root_dir=testset.domjudge_pack_dir)
        except Exception:
            ui.errors.Exception(testset)
            yield False

        yield True


class DOMJudgeSubmitter(plus_commands.SubmitterBase):
    _LANGUAGE_MAP = {
        'c': 'c',
        'cxx': 'cpp',
        'java': 'java',
        'kotlin': 'kotlin',
        'script': 'python3',  # assuming script = python
    }

    @taskgraph.task_method
    def Submit(self, ui, solution):
        if not solution.project.domjudge_config_defined:
            ui.errors.Error(
                solution, 'domjudge_config() is not defined in PROJECT.')
            yield False

        base_api_url = solution.project.domjudge_url + 'api/v4/'
        auth = requests.auth.HTTPBasicAuth(
            solution.project.domjudge_username,
            solution.project.domjudge_password)
        contest_id = solution.project.domjudge_contest_id

        # Get the problem id from problems list.
        res = requests.get(
            base_api_url + 'contests/%d/problems' % contest_id,
            auth=auth)
        if res.status_code != 200:
            ui.errors.Error(
                solution, 'Getting problems failed: %s' % res.reason)
            yield False

        possible_problems = [
            p for p in res.json() if p['label'] == solution.problem.id]
        if len(possible_problems) != 1:
            ui.errors.Error(solution, 'Problem does not exist.')
            yield False
        problem_id = possible_problems[0]['id']

        lang_name = self._LANGUAGE_MAP[solution.code.PREFIX]

        ui.console.PrintAction(
            'SUBMIT',
            solution,
            str({'problem_id': problem_id, 'language': lang_name}),
            progress=True)

        source_code_file = os.path.join(
            solution.src_dir, solution.code.src_name)
        with open(source_code_file, 'rb') as f:
            res = requests.post(
                base_api_url + 'contests/%d/submissions' % contest_id,
                data={'problem': problem_id, 'language': lang_name},
                files={'code': f},
                auth=auth)
        if res.status_code != 200:
            ui.errors.Error(solution, 'Submission failed: %s' % res.reason)
            yield False

        submission_id = res.json()['id']

        ui.console.PrintAction(
            'SUBMIT', solution, 'submitted: submission_id=%s' % submission_id,
            progress=True)

        # Poll until judge completes.
        while True:
            res = requests.get(
                base_api_url + 'contests/%d/judgements' % contest_id,
                params={'submission_id': submission_id},
                auth=auth)
            if res.status_code != 200:
                ui.errors.Error(
                    solution, 'Getting judgements failed: %s' % res.reason)
                yield False
            verdict = res.json()[0]['judgement_type_id']
            if verdict:
                break
            time.sleep(3.0)

        if solution.IsCorrect():
            expected = ''
        else:
            expected = '(fake solution)'
        ui.console.PrintAction(
            'SUBMIT', solution,
            '{0} {1} (s{2})'.format(verdict, expected, submission_id))

        yield True


targets.registry.Override('Project', Project)
targets.registry.Override('Testset', Testset)

# TODO: Implement Uploader
plus_commands.packer_registry.Add(DOMJudgePacker)
plus_commands.submitter_registry.Add(DOMJudgeSubmitter)
