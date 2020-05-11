#!/usr/bin/python
# -*- coding: utf-8 -*-


import rime.basic.targets.problem
import rime.basic.targets.project  # NOQA
from rime.core import commands as rime_commands


class Wikify(rime_commands.CommandBase):
    def __init__(self, parent):
        super(Wikify, self).__init__(
            'wikify',
            '',
            'Wikify is deprecated. Please use wikify_full.',
            '',
            parent)

    def Run(self, obj, args, ui):
        ui.console.PrintError('Wikify is deprecated. Please use wikify_full.')
        return None


rime_commands.registry.Add(Wikify)
