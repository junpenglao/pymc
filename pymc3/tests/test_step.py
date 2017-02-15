import os
import unittest

from .checks import close_to
from .models import simple_categorical, mv_simple, mv_simple_discrete, simple_2model
from pymc3.sampling import assign_step_methods, sample
from pymc3.model import Model
from pymc3.step_methods import (NUTS, BinaryGibbsMetropolis, CategoricalGibbsMetropolis,
                                Metropolis, Slice, CompoundStep, NormalProposal,
                                MultivariateNormalProposal, HamiltonianMC)
from pymc3.distributions import Binomial, Normal, Bernoulli, Categorical

from numpy.testing import assert_array_almost_equal
import numpy as np
import numpy.testing as npt
from tqdm import tqdm


class TestStepMethods(object):  # yield test doesn't work subclassing unittest.TestCase
    master_samples = {
        Slice: np.array([
            -8.13087389e-01, -3.08921856e-01, -6.79377098e-01, 6.50812585e-01, -7.63577596e-01,
            -8.13199793e-01, -1.63823548e+00, -7.03863676e-02, 2.05107771e+00, 1.68598170e+00,
            6.92463695e-01, -7.75120766e-01, -1.62296463e+00, 3.59722423e-01, -2.31421712e-01,
            -7.80686956e-02, -6.05860731e-01, -1.13000202e-01, 1.55675942e-01, -6.78527612e-01,
            6.31052333e-01, 6.09012517e-01, -1.56621643e+00, 5.04330883e-01, 3.14824082e-03,
            -1.31287073e+00, 4.10706927e-01, 8.93815792e-01, 8.19317020e-01, 3.71900919e-01,
            -2.62067312e+00, -3.47616592e+00, 1.50335041e+00, -1.05993351e+00, 2.41571723e-01,
            -1.06258156e+00, 5.87999429e-01, -1.78480091e-01, -3.60278680e-01, 1.90615274e-01,
            -1.24399204e-01, 4.03845589e-01, -1.47797573e-01, 7.90445804e-01, -1.21043819e+00,
            -1.33964776e+00, 1.36366329e+00, -7.50175388e-01, 9.25241839e-01, -4.17493767e-01,
            1.85311339e+00, -2.49715343e+00, -3.18571692e-01, -1.49099668e+00, -2.62079621e-01,
            -5.82376852e-01, -2.53033395e+00, 2.07580503e+00, -9.82615856e-01, 6.00517782e-01,
            -9.83941620e-01, -1.59014118e+00, -1.83931394e-03, -4.71163466e-01, 1.90073737e+00,
            -2.08929125e-01, -6.98388847e-01, 1.64502092e+00, -1.19525944e+00, 1.44424109e+00,
            1.52974876e+00, -5.70140077e-01, 5.08633322e-01, -1.70862492e-02, -1.69887948e-01,
            5.19760297e-01, -4.15149647e-01, 8.63685174e-02, -3.66805233e-01, -9.24988952e-01,
            2.33307122e+00, -2.60391496e-01, -5.86271814e-01, -5.01297170e-01, -1.53866195e+00,
            5.71285373e-01, -1.30571830e+00, 8.59587795e-01, 6.72170694e-01, 9.12433943e-01,
            7.04959179e-01, 8.37863464e-01, -5.24200836e-01, 1.28261340e+00, 9.08774240e-01,
            8.80566763e-01, 7.82911967e-01, 8.01843432e-01, 7.09251098e-01, 5.73803618e-01]),
        HamiltonianMC: np.array([
           -0.74925631, -0.2566773 , -2.12480977,  1.64328926, -1.39315913,
            2.04200003,  0.00706711,  0.34240498,  0.44276674, -0.21368043,
           -0.76398723,  1.19280082, -1.43030242, -0.44896107,  0.0547087 ,
           -1.72170938, -0.20443956,  0.35432546,  1.77695096, -0.31053636,
           -0.26729283,  1.26450201,  0.17049917,  0.27953939, -0.24185153,
            0.95617117, -0.45707061,  0.75837366, -1.73391277,  1.63331612,
           -0.68426038,  0.20499991, -0.43866983,  0.31080195,  0.47104548,
           -0.50331753,  0.7821196 , -1.7544931 ,  1.24106497, -1.0152971 ,
           -0.01949091, -0.33151479,  0.19138253,  0.40349184,  0.31694823,
           -0.01508142, -0.31330951,  0.40874228,  0.40874228,  0.58078882,
            0.68378375,  0.84142914,  0.44756075, -0.87297183,  0.59695222,
            1.96161733, -0.37126652,  0.27552912,  0.74547583, -0.16172925,
            0.79969568, -0.20501522, -0.36181518,  0.13114261, -0.8461323 ,
           -0.07749079, -0.07013026,  0.88022116, -0.5546825 ,  0.25232708,
            0.09483573,  0.84910913,  1.33348018, -1.1971401 ,  0.49203123,
            0.22365435,  1.3801812 ,  0.06885929,  1.07115053, -1.52225141,
            1.50179721, -2.01528399, -1.31610679, -0.32298834, -0.80630885,
           -0.6828592 ,  0.2897919 ,  1.64608125, -0.71793662, -0.5233058 ,
            0.53549836,  0.61119221,  0.24235732, -1.3940593 ,  0.28380114,
           -0.22629978, -0.19318957,  1.12543101, -1.40328285,  0.21054137]),
        Metropolis: np.array([
            1.62434536, 1.01258895, 0.4844172, -0.58855142, 1.15626034, 0.39505344, 1.85716138,
            -0.20297933, -0.20297933, -0.20297933, -0.20297933, -1.08083775, -1.08083775,
            0.06388596, 0.96474191, 0.28101405, 0.01312597, 0.54348144, -0.14369126, -0.98889691,
            -0.98889691, -0.75448121, -0.94631676, -0.94631676, -0.89550901, -0.89550901,
            -0.77535005, -0.15814694, 0.14202338, -0.21022647, -0.4191207, 0.16750249, 0.45308981,
            1.33823098, 1.8511608, 1.55306796, 1.55306796, 1.55306796, 1.55306796, 0.15657163,
            0.3166087, 0.3166087, 0.3166087, 0.3166087, 0.54670343, 0.54670343, 0.32437529,
            0.12361722, 0.32191694, 0.44092559, 0.56274686, 0.56274686, 0.18746191, 0.18746191,
            -0.15639177, -0.11279491, -0.11279491, -0.11279491, -1.20770676, -1.03832432,
            -0.29776787, -1.25146848, -1.25146848, -0.93630908, -0.5857631, -0.5857631,
            -0.62445861, -0.62445861, -0.64907557, -0.64907557, -0.64907557, 0.58708846,
            -0.61217957, 0.25116575, 0.25116575, 0.80170324, 1.59451011, 0.97097938, 1.77284041,
            1.81940771, 1.81940771, 1.81940771, 1.81940771, 1.95710892, 2.18960348, 2.18960348,
            2.18960348, 2.18960348, 2.63096792, 2.53081269, 2.5482221, 1.42620337, 0.90910891,
            -0.08791792, 0.40729341, 0.23259025, 0.23259025, 0.23259025, 2.76091595, 2.51228118]),
        NUTS: np.array([
            1.11832371,  1.11832371,  0.42875164, -1.06337276, -1.17501379,
           -0.27775246, -0.27775246,  0.00328623,  0.23795965,  1.65529636,
            1.7901408 , -0.62390469,  0.60124042,  0.60124042,  0.68440675,
            0.70435289,  0.60237357,  0.03717281,  0.03717281,  0.14498283,
            0.33947697, -0.75641974, -1.01172427, -0.32179423, -0.32179423,
           -0.7156012 , -0.7889553 , -0.70557754, -0.43709657, -1.04139017,
           -1.2598486 ,  1.18699505,  0.99526794,  0.99526794,  1.04015149,
            1.50603934,  0.36014394,  0.36014394, -0.13739556, -1.18151088,
           -0.0710748 , -0.0710748 ,  1.31690189,  0.85260096,  0.45588771,
            1.87500787,  1.89097747,  1.34449724,  1.01606708, -1.13494066,
           -1.13494066, -1.50994621, -1.19005012, -1.19005012, -1.01778929,
            0.51446356, -0.36414457, -1.15037476, -1.66474436, -0.94601342,
            1.69062255,  1.12824874, -0.76403619, -0.34949624, -0.34949624,
            0.59859215,  0.70995689,  0.72342126,  0.72342126,  0.13689042,
           -0.01645001, -0.37776318, -0.37776318,  0.11743312,  0.98420861,
           -1.17871458,  0.39449905,  0.39449905, -0.16173529, -0.18126029,
           -0.42421718,  0.08742792,  0.08742792, -0.8713866 , -1.81156194,
           -0.76789325, -1.05432342, -1.05432342, -0.996596  ,  0.90379001,
            1.48470753,  1.30774264,  0.10227063,  0.82993513,  0.82993513,
            0.86046271,  0.99365177, -0.19947887, -1.63970317, -1.09034566]),
    }

    def test_sample_exact(self):
        for step_method in self.master_samples:
            yield self.check_trace, step_method

    def check_trace(self, step_method):
        """Tests whether the trace for step methods is exactly the same as on master.

        Code changes that effect how random numbers are drawn may change this, and require
        `master_samples` to be updated, but such changes should be noted and justified in the
        commit.

        This method may also be used to benchmark step methods across commits, by running, for
        example

        ```
        BENCHMARK=100000 ./scripts/test.sh -s pymc3/tests/test_step.py:TestStepMethods
        ```

        on multiple commits.
        """
        test_steps = 100
        n_steps = int(os.getenv('BENCHMARK', 100))
        benchmarking = (n_steps != test_steps)
        if benchmarking:
            tqdm.write('Benchmarking {} with {:,d} samples'.format(step_method.__name__, n_steps))
        else:
            tqdm.write('Checking {} has same trace as on master'.format(step_method.__name__))
        with Model() as model:
            Normal('x', mu=0, sd=1)
            trace = sample(n_steps, step=step_method(), random_seed=1)

        if not benchmarking:
            assert_array_almost_equal(trace.get_values('x'), self.master_samples[step_method])

    def check_stat(self, check, trace, name):
        for (var, stat, value, bound) in check:
            s = stat(trace[var][2000:], axis=0)
            close_to(s, value, bound)

    def test_step_continuous(self):
        start, model, (mu, C) = mv_simple()
        unc = np.diag(C) ** .5
        check = (('x', np.mean, mu, unc / 10.),
                 ('x', np.std, unc, unc / 10.))
        with model:
            steps = (
                Slice(),
                HamiltonianMC(scaling=C, is_cov=True, blocked=False),
                NUTS(scaling=C, is_cov=True, blocked=False),
                Metropolis(S=C, proposal_dist=MultivariateNormalProposal, blocked=True),
                Slice(blocked=True),
                HamiltonianMC(scaling=C, is_cov=True),
                NUTS(scaling=C, is_cov=True),
                CompoundStep([
                    HamiltonianMC(scaling=C, is_cov=True),
                    HamiltonianMC(scaling=C, is_cov=True, blocked=False)]),
            )
        for step in steps:
            trace = sample(8000, step=step, start=start, model=model, random_seed=1)
            yield self.check_stat, check, trace, step.__class__.__name__

    def test_step_discrete(self):
        start, model, (mu, C) = mv_simple_discrete()
        unc = np.diag(C) ** .5
        check = (('x', np.mean, mu, unc / 10.),
                 ('x', np.std, unc, unc / 10.))
        with model:
            steps = (
                Metropolis(S=C, proposal_dist=MultivariateNormalProposal),
            )
        for step in steps:
            trace = sample(20000, step=step, start=start, model=model, random_seed=1)
            yield self.check_stat, check, trace, step.__class__.__name__

    def test_step_categorical(self):
        start, model, (mu, C) = simple_categorical()
        unc = C ** .5
        check = (('x', np.mean, mu, unc / 10.),
                 ('x', np.std, unc, unc / 10.))
        with model:
            steps = (
                CategoricalGibbsMetropolis(model.x, proposal='uniform'),
                CategoricalGibbsMetropolis(model.x, proposal='proportional'),
            )
        for step in steps:
            trace = sample(8000, step=step, start=start, model=model, random_seed=1)
            yield self.check_stat, check, trace, step.__class__.__name__


class TestMetropolisProposal(unittest.TestCase):
    def test_proposal_choice(self):
        _, model, _ = mv_simple()
        with model:
            s = np.ones(model.ndim)
            sampler = Metropolis(S=s)
            assert isinstance(sampler.proposal_dist, NormalProposal)
            s = np.diag(s)
            sampler = Metropolis(S=s)
            assert isinstance(sampler.proposal_dist, MultivariateNormalProposal)
            s[0, 0] = -s[0, 0]
            with self.assertRaises(np.linalg.LinAlgError):
                sampler = Metropolis(S=s)

    def test_mv_proposal(self):
        np.random.seed(42)
        cov = np.random.randn(5, 5)
        cov = cov.dot(cov.T)
        prop = MultivariateNormalProposal(cov)
        samples = np.array([prop() for _ in range(10000)])
        npt.assert_allclose(np.cov(samples.T), cov, rtol=0.2)


class TestCompoundStep(unittest.TestCase):
    samplers = (Metropolis, Slice, HamiltonianMC, NUTS)

    def test_non_blocked(self):
        """Test that samplers correctly create non-blocked compound steps."""
        _, model = simple_2model()
        with model:
            for sampler in self.samplers:
                self.assertIsInstance(sampler(blocked=False), CompoundStep)

    def test_blocked(self):
        _, model = simple_2model()
        with model:
            for sampler in self.samplers:
                sampler_instance = sampler(blocked=True)
                self.assertNotIsInstance(sampler_instance, CompoundStep)
                self.assertIsInstance(sampler_instance, sampler)


class TestAssignStepMethods(unittest.TestCase):
    def test_bernoulli(self):
        """Test bernoulli distribution is assigned binary gibbs metropolis method"""
        with Model() as model:
            Bernoulli('x', 0.5)
            steps = assign_step_methods(model, [])
        self.assertIsInstance(steps, BinaryGibbsMetropolis)

    def test_normal(self):
        """Test normal distribution is assigned NUTS method"""
        with Model() as model:
            Normal('x', 0, 1)
            steps = assign_step_methods(model, [])
        self.assertIsInstance(steps, NUTS)

    def test_categorical(self):
        """Test categorical distribution is assigned categorical gibbs metropolis method"""
        with Model() as model:
            Categorical('x', np.array([0.25, 0.75]))
            steps = assign_step_methods(model, [])
        self.assertIsInstance(steps, BinaryGibbsMetropolis)
        with Model() as model:
            Categorical('y', np.array([0.25, 0.70, 0.05]))
            steps = assign_step_methods(model, [])
        self.assertIsInstance(steps, CategoricalGibbsMetropolis)

    def test_binomial(self):
        """Test binomial distribution is assigned metropolis method."""
        with Model() as model:
            Binomial('x', 10, 0.5)
            steps = assign_step_methods(model, [])
        self.assertIsInstance(steps, Metropolis)
