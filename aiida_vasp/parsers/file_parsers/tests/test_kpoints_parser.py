"""Test the Kpoints io interface"""
# pylint: disable=unused-import,redefined-outer-name,unused-argument,unused-wildcard-import,wildcard-import

import pytest

from aiida_vasp.utils.fixtures import *
from aiida_vasp.utils.fixtures.testdata import data_path
from aiida_vasp.parsers.file_parsers.kpoints import KpParser


#@pytest.mark.parametrize(['vasp_kpoints'], [('list',)], indirect=True)
def test_parse_kpoints(vasp_kpoints):
    """
    Parse a reference KPOINTS file.

    Using the KpParser and compare the result to a reference
    kpoints-node.

    """

    kpoints, _ = vasp_kpoints

    if kpoints.get_attrs().get('mesh'):
        file_path = data_path('kpoints', 'KPOINTS_mesh')
        method = 'get_kpoints_mesh'
        param = 'mesh'
    elif kpoints.get_attrs().get('array|kpoints'):
        file_path = data_path('kpoints', 'KPOINTS_list')
        method = 'get_kpoints'
        param = 'list'

    parser = KpParser(file_path=file_path)
    result = parser.kpoints
    if param == 'list':
        assert getattr(result, method)().all() == getattr(kpoints, method)().all()
    if param == 'mesh':
        assert getattr(result, method)() == getattr(kpoints, method)()


def test_parse_kpoints_write(vasp_kpoints, tmpdir):
    """
    Parse a reference KPOINTS file.

    Using the KpParser and compare the result to a reference
    kpoints-node.

    """

    kpoints, _ = vasp_kpoints
    if kpoints.get_attrs().get('mesh'):
        method = 'get_kpoints_mesh'
        param = 'mesh'
    elif kpoints.get_attrs().get('array|kpoints'):
        method = 'get_kpoints'
        param = 'list'
    parser = KpParser(data=kpoints)
    temp_file = str(tmpdir.join('KPOINTS'))
    parser.write(file_path=temp_file)
    parser_reparse = KpParser(file_path=temp_file)
    result = parser_reparse.kpoints
    if param == 'list':
        assert getattr(result, method)().all() == getattr(kpoints, method)().all()
    if param == 'mesh':
        assert getattr(result, method)() == getattr(kpoints, method)()
