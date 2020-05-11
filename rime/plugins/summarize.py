#!/usr/bin/python
# -*- coding: utf-8 -*-

import codecs
import os
import os.path
import re
import sys


from six.moves import urllib

import rime.basic.targets.project  # NOQA
from rime.basic import test  # NOQA
from rime.core import commands as rime_commands  # NOQA
from rime.core import targets  # NOQA
from rime.core import taskgraph  # NOQA
from rime.plugins import summary


def SafeUnicode(s):
    if sys.version_info.major == 2 and not isinstance(s, unicode):  # NOQA
        s = s.decode('utf-8')
    return s


class Project(targets.registry.Project):
    def PreLoad(self, ui):
        super(Project, self).PreLoad(ui)
        self.wikify_config_defined = False

        def _wikify_config(url, page, encoding="utf-8", auth_realm=None,
                           auth_username=None, auth_password=None):
            self.wikify_config_defined = True
            self.wikify_url = url
            self.wikify_page = page
            self.wikify_encoding = encoding
            self.wikify_auth_realm = auth_realm
            self.wikify_auth_username = auth_username
            self.wikify_auth_password = auth_password
        self.exports['wikify_config'] = _wikify_config

    @taskgraph.task_method
    def Summarize(self, ui, filename):
        if not ui.options.skip_clean:
            yield self.Clean(ui)

        results = yield self.Test(ui)
        template_file = os.path.join(
            self.base_dir, 'rime', 'plugins', filename + '.ninja')
        content = summary.GenerateSummary(results, template_file, ui)
        # TODO(fixme) branch whether to output file or to upload wiki.
        codecs.open(
            os.path.join(self.base_dir, filename),
            'w',
            'utf8').write(content)

        yield None

    def _UploadWiki(self, wiki, ui):
        url = self.wikify_url
        page = SafeUnicode(self.wikify_page)
        encoding = self.wikify_encoding
        auth_realm = SafeUnicode(self.wikify_auth_realm)
        auth_username = self.wikify_auth_username
        auth_password = self.wikify_auth_password
        auth_hostname = urllib.parse.urlparse(url).hostname

        native_page = page.encode(encoding)
        native_wiki = wiki.encode(encoding)

        if self.wikify_auth_realm:
            auth_handler = urllib.request.HTTPBasicAuthHandler()
            auth_handler.add_password(
                auth_realm, auth_hostname, auth_username, auth_password)
            opener = urllib.request.build_opener(auth_handler)
            urllib.request.install_opener(opener)

        ui.console.PrintAction('UPLOAD', None, url)

        edit_params = {
            'cmd': 'edit',
            'page': native_page,
        }
        edit_page_content = urllib.request.urlopen(
            '%s?%s' % (url, urllib.parse.urlencode(edit_params))).read()

        digest = re.search(
            r'value="([0-9a-f]{32})"',
            edit_page_content.decode(encoding)).group(1)

        update_params = {
            'cmd': 'edit',
            'page': native_page,
            'digest': digest,
            'msg': native_wiki,
            'write': u'ページの更新'.encode(encoding),
            'encode_hint': u'ぷ'.encode(encoding),
        }
        urllib.request.urlopen(
            url, urllib.parse.urlencode(update_params).encode(encoding))


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
            return None

        return obj.Summarize(ui, template)

    def _OptionToFileName(self, opt):
        if opt == 'html':
            return 'summary.html'
        elif opt == 'markdown' or opt == 'md':
            return 'summary.md'
        elif opt == 'pukiwiki' or opt == 'wiki':
            return 'summary.pukiwiki'
        # elif opt == 'test':
        #     return 'test.txt'
        else:
            return None


targets.registry.Override('Project', Project)

rime_commands.registry.Add(Summarize)
