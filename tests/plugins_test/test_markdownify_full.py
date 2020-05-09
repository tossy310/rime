import unittest

import mock

from rime.plugins import markdownify_full
from rime.util import struct


class TestMarkdownifyProject(unittest.TestCase):
    def test_do_clean(self):
        ui = mock.MagicMock()
        ui.options = struct.Struct({'skip_clean': False})
        # TODO(fixme) specify the dir that contains the jinja template
        project = markdownify_full.Project('project', 'base_dir', None)
        project.problems = []
        project.Clean = mock.MagicMock()

        task_graph = project._GenerateMarkdownFull(ui)
        task_graph.Continue()

        project.Clean.called_once_with(ui)

    def test_skip_clean(self):
        ui = mock.MagicMock()
        ui.options = struct.Struct({'skip_clean': True})
        project = markdownify_full.Project('project', 'base_dir', None)
        project.problems = []
        project.Clean = mock.MagicMock()

        task_graph = project._GenerateMarkdownFull(ui)
        task_graph.Continue()

        project.Clean.assert_not_called()


if __name__ == '__main__':
    unittest.main()
