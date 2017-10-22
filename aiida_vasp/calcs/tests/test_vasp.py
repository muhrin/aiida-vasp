# pylint: disable=unused-import,unused-argument,redefined-outer-name
"""Unittests for VaspCalculation"""
import os
import contextlib

import numpy
import pytest
from aiida.common.folders import SandboxFolder

from aiida_vasp.utils.fixtures import aiida_env, fresh_aiida_env, localhost, vasp_params, \
    paws, vasp_structure, vasp_kpoints, vasp_code, ref_incar, localhost_dir, vasp_chgcar, \
    vasp_wavecar, ref_retrieved_nscf


@pytest.fixture()
def vasp_calc_and_ref(vasp_code, vasp_params, paws, vasp_kpoints,
                      vasp_structure, ref_incar):
    """Fixture for non varying setup of a vasp calculation"""
    from aiida_vasp.calcs.vasp import VaspCalculation
    calc = VaspCalculation()
    calc.use_code(vasp_code)
    calc.set_computer(vasp_code.get_computer())
    calc.set_resources({'num_machines': 1, 'num_mpiprocs_per_machine': 1})
    calc.use_parameters(vasp_params)
    calc.use_paw(paws['In'], kind='In')
    calc.use_paw(paws['As'], kind='As')
    calc.use_structure(vasp_structure)
    kpoints, ref_kpoints = vasp_kpoints
    calc.use_kpoints(kpoints)
    return calc, {'kpoints': ref_kpoints, 'incar': ref_incar}


@pytest.fixture()
def vasp_nscf_and_ref(vasp_calc_and_ref, vasp_chgcar, vasp_wavecar):
    """Fixture: vasp calc with chgcar and wavecar given"""
    calc, ref = vasp_calc_and_ref
    chgcar, ref_chgcar = vasp_chgcar
    wavecar, ref_wavecar = vasp_wavecar
    calc.use_charge_density(chgcar)
    calc.use_wavefunctions(wavecar)
    calc.inp.parameters.update_dict({'icharg': 11})
    ref['chgcar'] = ref_chgcar
    ref['wavecar'] = ref_wavecar
    return calc, ref


@pytest.mark.parametrize(
    ['vasp_structure', 'vasp_kpoints'], [('cif', 'mesh'), ('str', 'list')],
    indirect=True)
def test_store(vasp_calc_and_ref):
    vasp_calc, _ = vasp_calc_and_ref
    vasp_calc.store_all()
    assert vasp_calc.pk is not None


@pytest.mark.parametrize(
    ['vasp_structure', 'vasp_kpoints'], [('cif', 'mesh')], indirect=True)
def test_write_incar(fresh_aiida_env, vasp_calc_and_ref):
    vasp_calc, reference = vasp_calc_and_ref
    inp = vasp_calc.get_inputs_dict()
    with managed_temp_file() as temp_file:
        vasp_calc.write_incar(inp, temp_file)
        with open(temp_file, 'r') as result_incar_fo:
            assert result_incar_fo.read() == reference['incar']


@pytest.mark.parametrize(
    ['vasp_structure', 'vasp_kpoints'], [('cif', 'mesh')], indirect=True)
def test_write_poscar(fresh_aiida_env, vasp_calc_and_ref):
    from ase.io.vasp import read_vasp
    vasp_calc, _ = vasp_calc_and_ref
    inp = vasp_calc.get_inputs_dict()
    with managed_temp_file() as temp_file:
        vasp_calc.write_poscar(inp, temp_file)
        with working_directory(temp_file):
            result_ase = read_vasp(temp_file)
            ref_ase = inp['structure'].get_ase()
            assert numpy.allclose(
                result_ase.get_cell(), ref_ase.get_cell(), atol=1e-16, rtol=0)
            assert result_ase.get_chemical_formula(
            ) == ref_ase.get_chemical_formula()


def test_write_kpoints(fresh_aiida_env, vasp_calc_and_ref):
    vasp_calc, reference = vasp_calc_and_ref
    inp = vasp_calc.get_inputs_dict()
    print inp['kpoints'].get_attrs(), reference['kpoints']
    with managed_temp_file() as temp_file:
        vasp_calc.write_kpoints(inp, temp_file)
        with open(temp_file, 'r') as result_kpoints_fo:
            assert result_kpoints_fo.read() == reference['kpoints']


@pytest.mark.parametrize(
    ['vasp_structure', 'vasp_kpoints'], [('cif', 'mesh')], indirect=True)
def test_write_potcar(fresh_aiida_env, vasp_calc_and_ref):
    """Check that POTCAR is written correctly"""
    vasp_calc, _ = vasp_calc_and_ref
    inp = vasp_calc.get_inputs_dict()
    with managed_temp_file() as temp_file:
        vasp_calc.write_potcar(inp, temp_file)
        with open(temp_file, 'r') as potcar_fo:
            result_potcar = potcar_fo.read()
        assert 'In_d' in result_potcar
        assert 'As' in result_potcar
        assert result_potcar.count('End of Dataset') == 2


@pytest.mark.parametrize(
    ['vasp_structure', 'vasp_kpoints'], [('cif', 'mesh')], indirect=True)
def test_write_chgcar(fresh_aiida_env, vasp_calc_and_ref, vasp_chgcar):
    """Test that CHGAR file is written correctly"""
    vasp_calc, _ = vasp_calc_and_ref
    chgcar, ref_chgcar = vasp_chgcar
    vasp_calc.use_charge_density(chgcar)
    inp = vasp_calc.get_inputs_dict()
    with managed_temp_file() as temp_file:
        vasp_calc.write_chgcar(inp, temp_file)
        with open(temp_file, 'r') as result_chgcar_fo:
            assert result_chgcar_fo.read() == ref_chgcar


@pytest.mark.parametrize(
    ['vasp_structure', 'vasp_kpoints'], [('cif', 'mesh')], indirect=True)
def test_write_wavecar(fresh_aiida_env, vasp_calc_and_ref, vasp_wavecar):
    """Test that CHGAR file is written correctly"""
    vasp_calc, _ = vasp_calc_and_ref
    wavecar, ref_wavecar = vasp_wavecar
    vasp_calc.use_wavefunctions(wavecar)
    inp = vasp_calc.get_inputs_dict()
    with managed_temp_file() as temp_file:
        vasp_calc.write_wavecar(inp, temp_file)
        with open(temp_file, 'r') as result_wavecar_fo:
            assert result_wavecar_fo.read() == ref_wavecar


# pylint: disable=protected-access
def test_prepare(vasp_nscf_and_ref):
    """Check that preparing creates all necessary files"""
    vasp_calc, _ = vasp_nscf_and_ref
    inp = vasp_calc.get_inputs_dict()
    with SandboxFolder() as sandbox_f:
        calc_info = vasp_calc._prepare_for_submission(sandbox_f, inp)
        inputs = sandbox_f.get_content_list()
    assert set(inputs) == {
        'INCAR', 'KPOINTS', 'POSCAR', 'POTCAR', 'CHGCAR', 'WAVECAR'
    }
    assert 'EIGENVAL' in calc_info.retrieve_list
    assert 'DOSCAR' in calc_info.retrieve_list
    assert ('wannier90*', '.', 0) in calc_info.retrieve_list

    vasp_calc.inp.parameters.update_dict({'icharg': 2})
    inp = vasp_calc.get_inputs_dict()
    with SandboxFolder() as sandbox_f:
        calc_info = vasp_calc._prepare_for_submission(sandbox_f, inp)
        inputs = sandbox_f.get_content_list()
    assert set(inputs) == {'INCAR', 'KPOINTS', 'POSCAR', 'POTCAR', 'WAVECAR'}


@pytest.mark.parametrize(
    ['vasp_structure', 'vasp_kpoints'], [('cif', 'mesh')], indirect=True)
def test_parse_with_retrieved(vasp_nscf_and_ref, ref_retrieved_nscf):
    """Check that parsing is successful and creates the right output links"""
    vasp_calc, _ = vasp_nscf_and_ref
    parser = vasp_calc.get_parserclass()(vasp_calc)
    success, outputs = parser.parse_with_retrieved({
        'retrieved':
        ref_retrieved_nscf
    })
    outputs = dict(outputs)
    assert success
    assert 'bands' in outputs
    assert 'dos' in outputs
    assert 'results' in outputs


@contextlib.contextmanager
def managed_temp_file():
    import tempfile
    _, temp_file = tempfile.mkstemp()
    try:
        yield temp_file
    finally:
        os.remove(temp_file)


@contextlib.contextmanager
def working_directory(new_work_dir):
    work_dir = os.getcwd()
    try:
        if os.path.isdir(new_work_dir):
            os.chdir(new_work_dir)
        else:
            os.chdir(os.path.dirname(new_work_dir))
        yield
    finally:
        os.chdir(work_dir)