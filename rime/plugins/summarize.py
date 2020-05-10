#!/usr/bin/python
# -*- coding: utf-8 -*-

import codecs
import os
import os.path


from jinja2 import Environment
from jinja2 import FileSystemLoader

import rime.basic.targets.project  # NOQA
from rime.basic import test  # NOQA
from rime.core import commands as rime_commands  # NOQA
from rime.core import targets  # NOQA
from rime.core import taskgraph  # NOQA
from rime.plugins import summary


class Project(targets.registry.Project):
    @taskgraph.task_method
    def Summarize(self, ui, filename):
        if not ui.options.skip_clean:
            yield self.Clean(ui)

        results = yield self.Test(ui)

        summ = summary.GenerateSummary(results, ui)

        jinja_env = Environment(loader=FileSystemLoader(
            os.path.join(self.base_dir, 'rime', 'plugins'), encoding='utf8'))
        template = jinja_env.get_template(filename + '.ninja')
        template.globals['ItemState'] = summary.ItemState

        content = template.render(**summ)
        codecs.open(
            os.path.join(self.base_dir, filename),
            'w',
            'utf8').write(content)

        yield None


class Summarize(rime_commands.CommandBase):
    def __init__(self, parent):
        super(Summarize, self).__init__(
            'summarize',
            '[<type>]',
            'Project summary generator plugin',
            '',
            parent)
        self.AddOptionEntry(rime_commands.OptionEntry(
            's', 'skip_clean', 'skip_clean', bool, False, None,
            'Skip cleaning generated files up.'
        ))

    def Run(self, obj, args, ui):
        if not isinstance(obj, Project):
            ui.console.PrintError(
                'summary plugin is not supported for the specified target.')
            return None

        if not args or len(args) != 1:
            ui.console.PrintError(
                'Extra argument passed to summary command!')
            return None

        template = self._OptionToFileName(args[0])
        if template is None:
            ui.console.PrintError(
                'Please specify the correct output type!')

        return obj.Summarize(ui, template)

    def _OptionToFileName(self, opt):
        if opt == 'html':
            return 'summary.html'
        elif opt == 'markdown' or opt == 'md':
            return 'summary.md'
        # elif opt == 'pukiwiki' or opt == 'wiki':
        #     return 'pukiwiki.md'
        # elif opt == 'test':
        #     return 'test.txt'
        else:
            return None


targets.registry.Override('Project', Project)

rime_commands.registry.Add(Summarize)
