from aiida.orm import CalculationFactory, DataFactory
from aiida.tools.codespecific.vasp.default_paws import lda

class VaspMaker(object):
    '''
    py:class:VaspMaker:
        simplifies the task of creating a Vasp5Calculation from scratch
        further simplifies creating certain often used types of calculations
    '''
    def __init__(self, *args, **kwargs):
        self._init_defaults(*args, **kwargs)

    def _init_defaults(self, *args, **kwargs):
        calcname = kwargs.get('calc', 'vasp.vasp5')
        self.calc_cls = CalculationFactory(calcname)
        self.label = kwargs.get('label', 'unlabeled')
        self._computer = kwargs.get('computer')
        self._code = kwargs.get('code')
        self._settings = kwargs.get('settings', self.calc_cls.new_settings())
        self._set_default_structure(kwargs.get('structure'))
        self._paws = {}
        self._set_default_lda_paws()
        self._kpoints = kwargs.get('kpoints', self.calc_cls.new_kpoints())
        self.kpoints = self._kpoints
        self._charge_density = kwargs.get('charge_density', None)
        self._wavefunctions = kwargs.get('wavefunctions', None)
        self._recipe = None
        self._queue = None

    def _set_default_structure(self, structure):
        if isinstance(structure, str):
            self._structure = DataFactory('cif').get_or_create(structure)[0]
        elif not structure:
            self._structure = self.calc_cls.new_structure()
        else:
            self._structure = structure

    def new(self):
        calc = self.calc_cls()
        calc.use_code(self._code)
        calc.use_structure(self._structure)
        for k in self.elements:
            calc.use_paw(self._paws[k], kind=k)
        calc.use_settings(self._settings)
        calc.use_kpoints(self._kpoints)
        calc.set_computer(self._computer)
        calc.set_queue_name(self._queue)
        if self._charge_density:
            calc.use_charge_density(self._charge_density)
        if self._wavefunctions:
            calc.use_wavefunctions(self._wavefunctions)
        calc.label = self.label
        return calc

    @property
    def structure(self):
        return self._structure

    @structure.setter
    def structure(self, val):
        self._structure = val
        self._set_default_lda_paws()
        self._kpoints.set_cell(self._structure.get_ase().get_cell())

    @property
    def settings(self):
        return self._settings.get_dict()

    @property
    def kpoints(self):
        return self._kpoints

    @kpoints.setter
    def kpoints(self, kp):
        self._kpoints = kp
        self._kpoints.set_cell(self._structure.get_ase().get_cell())

    @property
    def code(self):
        return self._code

    @code.setter
    def code(self, val):
        self._code = val

    @property
    def computer(self):
        return self._computer

    @computer.setter
    def computer(self, val):
        self._computer = val

    @property
    def queue(self):
        return self._queue

    @queue.setter
    def queue(self, val):
        self._queue = val

    def add_settings(self, **kwargs):
        for k, v in kwargs.iteritems():
            if k not in self.settings:
                self._settings.update_dict({k: v})

    def rewrite_settings(self, **kwargs):
            self._settings.update_dict(kwargs)

    def _set_default_lda_paws(self):
        for k in self.elements:
            if k not in self._paws:
                paw = self.calc_cls.Paw.load_paw(family='LDA', symbol=lda[k])[0]
                self._paws[k] = paw

    @property
    def elements(self):
        return set(self._structure.get_ase().get_chemical_symbols())

    def pkcmp(self, nodeA, nodeB):
        if nodeA.pk < nodeB.pk:
            return -1
        elif nodeA.pk > nodeB.pk:
            return 1
        else:
            return 0

    def verify_incar(self):
        if not self.struct:
            raise ValueError('need structure,')
        magmom = self.incar.get('magmom', [])
        lsorb = self.incar.get('lsorbit', False)
        lnonc = self.incar.get('lnoncollinear', False)
        ok = True
        nmag = len(magmom)
        nsit = len(self.struct.sites)
        if lsorb:
            if lnonc:
                if magmom and not nmag == 3*nsit:
                    ok = False
            else:
                if not nmag == nsit:
                    ok = False
        else:
            if not nmag == nsit:
                ok = False
        return ok

    def check_magmom(self):
        magmom = self.settings.get('magmom', [])
        st_magmom = self._structure.get_ase().get_initial_magnetic_moments()
        lsf = self.noncol and 3 or 1
        nio = self.n_ions
        s_mm = nio * lsf
        mm = len(magmom)
        if magmom and st_magmom:
            return s_mm == mm

    def set_magmom_1(self, val):
        magmom = [val]
        magmom *= self.n_ions
        magmom *= self.noncol and 3 or 1
        self.rewrite_settings(magmom=magmom)

    @property
    def nbands(self):
        return self.n_ions * 3 * self.noncol and 3 or 1

    @property
    def n_ions(self):
        return self.structure.get_ase().get_number_of_atoms()

    @property
    def n_elec(self):
        res = 0
        for k in self._structure.get_ase().get_chemical_symbols():
            res += self._paws[k].valence
        return res

    @property
    def noncol(self):
        lsorb = self.settings.get('lsorbit', False)
        lnonc = self.settings.get('lnoncollinear', False)
        return lsorb or lnonc

    @property
    def icharg(self):
        return self.settings['icharg']

    @icharg.setter
    def icharg(self, value):
        if value not in [0, 1, 2, 4, 10, 11, 12]:
            raise ValueError('invalid ICHARG value for vasp 5.3.5')
        else:
            self.settings['icharg'] = value

    @property
    def recipe(self):
        return self._recipe

    @recipe.setter
    def recipe(self, val):
        if self._recipe and self._recipe != recipe:
            raise ValueError('recipe is already set to something else')
        self._init_recipe(val)
        self._recipe = val

    def _init_recipe(self, recipe):
        if recipe == 'test_sc':
            self._init_recipe_test_sc()
        else:
            raise ValueError('recipe not recognized')

    def _init_recipe_test_sc(self):
        self.add_settings(
            gga = 'PE',
            gga_compat = False,
            ismear = 0,
            lorbit = 11,
            lsorbit = True,
            sigma = 0.05,
        )
