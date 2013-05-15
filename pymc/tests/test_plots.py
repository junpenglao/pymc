from ..plots import *
from pymc import psample


def test_plots():

    # Test single trace
    from pymc.examples import arbitrary_stochastic

    forestplot(arbitrary_stochastic.trace)

    autocorrplot(arbitrary_stochastic.trace)


def test_multichain_plots():

    from pymc.examples import disaster_model as dm

    with dm.model:
        # Run sampler
        ptrace = psample(1000, [dm.step1, dm.step2], dm.start, threads=2)

    forestplot(ptrace, vars=['early_mean', 'late_mean'])

    autocorrplot(ptrace, vars=['switchpoint'])
