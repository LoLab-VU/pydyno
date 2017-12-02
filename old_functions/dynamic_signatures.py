import tropical.helper_functions as hf
from pysb.simulator import SimulationResult, ScipyOdeSimulator, CupSodaSimulator
import numpy
import operator
import sympy
import math
import itertools
try:
    from pathos.multiprocessing import ProcessingPool as Pool
except ImportError:
    Pool = None

try:
    import h5py
except ImportError:
    h5py = None


class Tropical(object):
    """
    Obtain the dynamic signatures of species from a PySB model

    Parameters
    ----------
    model : pysb.Model
        Model to analyze.
    """
    mach_eps = 1e-11

    def __init__(self, model):

        self.all_comb = {}
        self.model = model
        self.par_name_idx = {j.name: i for i, j in enumerate(self.model.parameters)}
        self._is_setup = False
        self.passengers = []
        self.eqs_for_tropicalization = {}
        self.diff_par = None
        self.tspan = None

    def setup_tropical(self, tspan, diff_par=1, passengers_by='imp_nodes'):
        """
        Set up parameters necessary to obtain the dynamic signatures of species signal execution

        Parameters
        ----------
        tspan : vector-like, optional
            Time values over which to do the tropical analysis. The first and last values define
            the time range.
        diff_par : float
            Magnitude difference that defines that a reaction is dominant over others.
        passengers_by : str
            It can be 'qssa' or 'imp_nodes'. It defines the method to use for finding passenger species

        Returns
        -------

        """
        self.diff_par = diff_par
        self.tspan = tspan
        self.equations_to_tropicalize(get_passengers_by=passengers_by)
        self.set_combinations_sm()
        self._is_setup = True
        return

    def equations_to_tropicalize(self, get_passengers_by='imp_nodes'):
        """

        Returns
        -------
        Dictionary with dominant species indices as keys and ODEs as values o

        """
        if get_passengers_by == 'imp_nodes':
            self.passengers = hf.find_nonimportant_nodes(self.model)
        else:
            raise ValueError('method to obtain passengers not supported')

        idx = list(set(range(len(self.model.odes))) - set(self.passengers))
        # removing source and sink species
        if self.model.has_synth_deg():
            for i, j in enumerate(self.model.species):
                if str(j) == '__sink()' or str(j) == '__source()' and i in idx:
                    idx.remove(i)

        eqs = {i: self.model.odes[i] for i in idx}
        self.eqs_for_tropicalization = eqs
        return

    @staticmethod
    def _choose_max_pos_neg(array, mon_names, diff_par, mon_comb):
        """
        Get the dominant reaction(s) of a species at a specific time point

        Parameters
        ----------
        array
        mon_names
        diff_par
        mon_comb

        Returns
        -------

        """
        mons_pos_neg = [numpy.where(array > 0)[0], numpy.where(array < 0)[0]]
        signs = [1, -1]
        ascending_order = [False, True]
        mons_types = ['products', 'reactants']

        pos_neg_largest = [0] * 2
        range_0_1 = range(2)
        for ii, mon_type, mons_idx, sign, ascending in zip(range_0_1, mons_types, mons_pos_neg, signs, ascending_order):
            largest_prod = 'NoDoms'
            mon_names_ready = [mon_names.keys()[mon_names.values().index(i)] for i in mons_idx]
            # print (array, mon_names_ready)
            # if mon_type == 'reactants':
            #     print(mon_names_ready, mon_names, mons_pos_neg)
            mon_comb_type = mon_comb[mon_type]

            for comb in sorted(mon_comb_type.keys()):
                # comb is an integer that represents the number of monomials in a combination
                if len(mon_comb_type[comb].keys()) == 1:
                    largest_prod = mon_comb_type[comb].keys()[0]
                    break

                monomials_values = {}
                for idx in mon_comb_type[comb].keys():
                    value = 0
                    for j in mon_comb_type[comb][idx]:
                        if j not in mon_names_ready:
                            value += sign * 1e-100 # value_to_add
                        else:
                            value += array[mon_names[j]]
                    monomials_values[idx] = value
                foo2 = sorted(monomials_values.items(), key=operator.itemgetter(1), reverse=ascending)
                # foo2 = pd.Series(monomials_values).sort_values(ascending=ascending)
                comb_largest = mon_comb_type[comb][foo2[0][0]]
                if mon_type == 'products':
                    print (comb, monomials_values, comb_largest)
                for cm in foo2:
                    # Compares the largest combination of monomials to other combinations whose monomials that are not
                    # present in comb_largest
                    if len(set(comb_largest) - set(mon_comb_type[comb][cm[0]])) == len(comb_largest):
                        value_prod_largest = math.log10(sign * foo2[0][1])
                        if abs(value_prod_largest - math.log10(sign * cm[1])) > diff_par and value_prod_largest > -5:
                            largest_prod = foo2[0][0]
                            break
                if largest_prod != 'NoDoms':
                    break
            pos_neg_largest[ii] = largest_prod
            # print(mon_type, mon_names_ready, mon_comb_type, largest_prod)
        return pos_neg_largest

    def signature(self, y, param_values):
        """
        Dynamic signature of the dominant species

        Parameters
        ----------
        y : np.array
            Species trajectories from the model simulation
        param_values: vector-like
            Parameter values used to obtain species trajectories

        Returns
        -------

        """
        assert self._is_setup, 'you must setup tropical first'

        # Dictionary that will contain the signature of each of the species to study
        all_signatures = {}
        for sp in self.eqs_for_tropicalization:
            # reaction terms for positive and negative monomials
            monomials = []
            for term in self.model.reactions_bidirectional:
                total_rate = 0
                for mon_type, mon_sign in zip(['products', 'reactants'], [1, -1]):
                    if sp in term[mon_type]:
                        count = term[mon_type].count(sp)
                        total_rate = total_rate + (mon_sign * count * term['rate'])
                if total_rate == 0:
                    continue
                monomials.append(total_rate)

            # Dictionary whose keys are the symbolic monomials and the values are the simulation results
            mons_dict = {}
            for mon_p in monomials:
                mon_p_values = mon_p

                if mon_p_values == 0:
                    mons_dict[mon_p] = [0] * len(self.tspan)
                else:
                    var_prod = [atom for atom in mon_p_values.atoms(sympy.Symbol)]  # Variables of monomial
                    arg_prod = [0] * len(var_prod)
                    for idx, va in enumerate(var_prod):
                        if str(va).startswith('__'):
                            arg_prod[idx] = numpy.maximum(self.mach_eps, y[str(va)])
                        else:
                            arg_prod[idx] = param_values[self.par_name_idx[va.name]]
                    # arg_prod = [numpy.maximum(self.mach_eps, y[str(va)]) for va in var_prod]
                    f_prod = sympy.lambdify(var_prod, mon_p_values)
                    prod_values = f_prod(*arg_prod)
                    mons_dict[mon_p] = prod_values
            mons_names = {}
            mons_array = numpy.zeros((len(mons_dict.keys()), len(self.tspan)))
            for idx, name in enumerate(mons_dict.keys()):
                mons_array[idx] = mons_dict[name]
                mons_names[name] = idx

            signature_species = numpy.apply_along_axis(self._choose_max_pos_neg, 0, mons_array,
                                                       *(mons_names, self.diff_par, self.all_comb[sp]))
            all_signatures[sp] = list(signature_species)
        return all_signatures

    def set_combinations_sm(self, max_comb=None):
        """
        Obtain all possible combinations of the reactions in which a species is involved

        Parameters
        ----------
        max_comb: int
            Maximum level of combinations

        Returns
        -------

        """
        assert self.eqs_for_tropicalization, 'you must find passenger species first'

        all_comb = {}
        for sp in self.eqs_for_tropicalization:
            # reaction terms
            pos_neg_combs = {}
            parts_reaction = ['products', 'reactants']
            parts_rev = [1, 0]
            signs = [1, -1]

            # We get the reaction rates from the bidirectional reactions in order to have reversible reactions
            # as one 'monomial'. This is helpful for visualization and other (I should think more about this)
            for mon_type, mon_sign, rev_parts in zip(parts_reaction, signs, parts_rev):
                monomials = []

                for term in self.model.reactions_bidirectional:
                    if sp in term[mon_type]:
                        # Add zero to monomials in cases like autocatalytic reactions where a species
                        # shows up both in reactants and products, and we are looking for the reactions that use a sp
                        # but the reaction produces the species overall
                        if sp in term[parts_reaction[rev_parts]]:
                            count_reac = term['reactants'].count(sp)
                            count_pro = term['products'].count(sp)
                            mon_zero = mon_sign
                            if mon_type == 'reactants':
                                if count_pro > count_reac:
                                    mon_zero = 0
                            else:
                                if count_pro < count_reac:
                                    mon_zero = 0
                            monomials.append(mon_zero * term['rate'])
                        else:
                            monomials.append(mon_sign * term['rate'])

                    if sp in term[parts_reaction[rev_parts]] and term['reversible']:
                        monomials.append(signs[rev_parts] * term['rate'])

                # remove zeros from reactions in which the species shows up both in reactants and products
                monomials = [value for value in monomials if value != 0]

                # This is suppose to reduce the number of combinations to max_comb. But it's not working
                # TODO: Make this work
                # if max_comb:
                #     combs = max_comb
                # else:
                #     combs = len(monomials) + 1
                combs = len(monomials) + 1

                mon_comb = {}
                prod_idx = 0

                for L in range(1, combs):
                    prod_comb_names = {}
                    if L == combs - 1:
                        prod_comb_names['NoDoms'] = 'No_Dominants'
                    else:
                        for subset in itertools.combinations(monomials, L):
                            prod_comb_names['M{0}{1}'.format(L, prod_idx)] = subset
                            prod_idx += 1
                    mon_comb[L] = prod_comb_names
                pos_neg_combs[mon_type] = mon_comb
            all_comb[sp] = pos_neg_combs
        self.all_comb = all_comb
        return


def get_simulations(simulations):
    """
    Obtains trajectories, parameters, tspan from a SimulationResult object
    Parameters
    ----------
    simulations: pysb.SimulationResult
        Simulation result

    Returns
    -------

    """
    if isinstance(simulations, str):
        if h5py is None:
            raise Exception('please install the h5py package for this feature')
        if h5py.is_hdf5(simulations):
            sim = SimulationResult.load(simulations)
            tspan = sim.tout[0]
        else:
            raise TypeError('File format not supported')
    elif isinstance(simulations, SimulationResult):
        sim = simulations
        tspan = sim.tout[0]
    else:
        raise TypeError('format not supported')
    trajectories = sim.all
    parameters = sim.param_values
    nsims = sim.nsims
    tspan = tspan
    return trajectories, parameters, nsims, tspan


def organize_dynsign_multi(signatures):
    species = signatures[0].keys()
    nsims = [0]*len(signatures)
    organized_dynsigns = {sp: {'production': nsims[:], 'consumption': nsims[:]} for sp in species}
    for idx, dyn in enumerate(signatures):
        for sp in species:
            organized_dynsigns[sp]['production'][idx] = dyn[sp][0]
            organized_dynsigns[sp]['consumption'][idx] = dyn[sp][1]

    return organized_dynsigns


def run_tropical(model, simulations=None, passengers_by='imp_nodes', diff_par=1):
    """

    Parameters
    ----------
    model: pysb.model
        model to analyze
    simulations: pysb.SimulationResult, or str
        Simulation result of model
    passengers_by : str
        It can be 'qssa' or 'imp_nodes'. It defines the method to use for finding passenger species
    diff_par : float
        Magnitude difference that defines that a reaction is dominant over others.

    Returns
    -------
    Dynamic signatures of dominant species of the model
    """
    trajectories, parameters, nsims, tspan = get_simulations(simulations)
    tro = Tropical(model)
    tro.setup_tropical(tspan=tspan, diff_par=diff_par, passengers_by=passengers_by)
    signatures = tro.signature(y=trajectories, param_values=parameters[0])
    return signatures


def run_tropical_multi(model, simulations=None, passengers_by='imp_nodes', diff_par=1, cpu_cores=1):
    """

    Parameters
    ----------
    model: pysb.model
        model to analyze
    simulations: pysb.SimulationResult, or str
        Simulation result of model
    passengers_by : str
        It can be 'qssa' or 'imp_nodes'. It defines the method to use for finding passenger species
    diff_par : float
        Magnitude difference that defines that a reaction is dominant over others.
    cpu_cores: int
        Number of cores to use for running the analysis

    Returns
    -------
    Dynamic signatures of dominant species of the model

    """
    if Pool is None:
        raise Exception('Please install the pathos package for this feature')

    trajectories, parameters, nsims, tspan = get_simulations(simulations)
    tro = Tropical(model)

    tro.setup_tropical(tspan=tspan, diff_par=diff_par, passengers_by=passengers_by)
    p = Pool(cpu_cores)
    if nsims == 1:
        trajectories = [trajectories]
    else:
        trajectories = trajectories
    res = p.amap(tro.signature, trajectories, parameters)
    signatures = res.get()
    signatures = organize_dynsign_multi(signatures)
    return signatures