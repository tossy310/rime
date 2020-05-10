#!/usr/bin/python
# -*- coding: utf-8 -*-

from rime.core import commands as rime_commands  # NOQA


class HtmlifyFull(rime_commands.CommandBase):
    def __init__(self, parent):
        self.msg = 'Deprecated. Use `rime summarize html` instead.'
        super(HtmlifyFull, self).__init__(
            'htmlify_full',
            '',
            self.msg,
            '',
            parent)

    def Run(self, obj, args, ui):
        ui.console.PrintError(self.msg)
        return None


class MarkdownifyFull(rime_commands.CommandBase):
    def __init__(self, parent):
        self.msg = 'Deprecated. Use `rime summarize markdown` instead.'
        super(MarkdownifyFull, self).__init__(
            'markdownify_full',
            '',
            self.msg,
            '',
            parent)

    def Run(self, obj, args, ui):
        ui.console.PrintError(self.msg)
        return None


rime_commands.registry.Add(HtmlifyFull)
rime_commands.registry.Add(MarkdownifyFull)
