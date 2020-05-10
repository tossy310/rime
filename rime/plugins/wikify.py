#!/usr/bin/python
# -*- coding: utf-8 -*-

from rime.core import commands as rime_commands  # NOQA


class Wikify(rime_commands.CommandBase):
    def __init__(self, parent):
        self.msg = 'This command is deprecated. Use `rime summarize pukiwiki` instead.'
        super(Wikify, self).__init__(
            'wikify_full',
            '',
            self.msg,
            '',
            parent)

    def Run(self, obj, args, ui):
        ui.console.PrintError(self.msg)
        return None


rime_commands.registry.Add(Wikify)
