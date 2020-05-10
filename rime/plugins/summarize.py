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
    def Summarize(self, ui):
        if not ui.options.skip_clean:
            yield self.Clean(ui)

        results = yield self.Test(ui)

        summ = summary.GenerateSummary(results, ui)

        jinja_env = Environment(loader=FileSystemLoader(
            os.path.join(self.base_dir, 'rime', 'plugins'), encoding='utf8'))
        template = jinja_env.get_template('summary.md.ninja')
        template.globals['ItemState'] = summary.ItemState

        content = template.render(**summ)

        codecs.open(os.path.join(self.base_dir, 'summary.md'),
            'w', 'utf8').write(content)

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
        if args:
            ui.console.PrintError(
                'Extra argument passed to summary command!')
            return None

        if isinstance(obj, Project):
            return obj.Summarize(ui)

        ui.console.PrintError(
            'summary plugin is not supported for the specified target.')
        return None


targets.registry.Override('Project', Project)

rime_commands.registry.Add(Summarize)
