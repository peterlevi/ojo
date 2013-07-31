import unittest
from ojo import util

class TestUtil(unittest.TestCase):
    def test_path_url(self):
        path = '/a/b/c d'
        url = util.path2url(path)
        self.assertEquals('file:///a/b/c%20d', url)
        self.assertEquals(path, util.url2path(url))