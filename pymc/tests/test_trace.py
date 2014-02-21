from .checks import *
from .models import *
import pymc as pm
import numpy as np


## For all the summary tests, the number of dimensions refer to the
## original variable dimensions, not the MCMC trace dimensions.


def test_summary_0d_variable_model():
    mu = -2.1
    tau = 1.3
    with Model() as model:
        x = Normal('x', mu, tau, testval=.1)
        step = Metropolis(model.vars, np.diag([1.]))
        trace = sample(100, step=step)
    pm.summary(trace)


def test_summary_1d_variable_model():
    mu = -2.1
    tau = 1.3
    with Model() as model:
        x = Normal('x', mu, tau, shape=2, testval=[.1, .1])
        step = Metropolis(model.vars, np.diag([1.]))
        trace = sample(100, step=step)
    pm.summary(trace)


def test_summary_2d_variable_model():
    mu = -2.1
    tau = 1.3
    with Model() as model:
        x = Normal('x', mu, tau, shape=(2, 2),
                   testval=np.tile(.1, (2, 2)))
        step = Metropolis(model.vars, np.diag([1.]))
        trace = sample(100, step=step)
    pm.summary(trace)


def test_summary_format_values():
    roundto = 2
    summ = pm.trace._Summary(roundto)
    d = {'nodec': 1, 'onedec': 1.0, 'twodec': 1.00, 'threedec': 1.000}
    summ._format_values(d)
    for val in d.values():
        assert val == '1.00'


def test_stat_summary_format_hpd_values():
    roundto = 2
    summ = pm.trace._StatSummary(roundto, None, 0.05)
    d = {'nodec': 1, 'hpd': [1, 1]}
    summ._format_values(d)
    for key, val in d.items():
        if key == 'hpd':
            assert val == '[1.00, 1.00]'
        else:
            assert val == '1.00'


def test_calculate_stats_0d_variable():
    sample = np.arange(10)
    result = list(pm.trace._calculate_stats(sample, 5, 0.05))
    assert result[0] == ()
    assert len(result) == 2


def test_calculate_stats_variable_1d_variable():
    sample = np.arange(10).reshape(5, 2)
    result= list(pm.trace._calculate_stats(sample, 5, 0.05))
    assert result[0] == ()
    assert len(result) == 3

def test_calculate_pquantiles_0d_variable():
    sample = np.arange(10)[:, None]
    qlist = (0.25, 25, 50, 75, 0.98)
    result = list(pm.trace._calculate_posterior_quantiles(sample, qlist))
    assert result[0] == ()
    assert len(result) == 2


def test_stats_value_line():
    roundto = 1
    summ = pm.trace._StatSummary(roundto, None, 0.05)
    values = [{'mean': 0, 'sd': 1, 'mce': 2, 'hpd': [4, 4]},
              {'mean': 5, 'sd': 6, 'mce': 7, 'hpd': [8, 8]},]

    expected = ['0.0              1.0              2.0              [4.0, 4.0]',
                '5.0              6.0              7.0              [8.0, 8.0]']
    result = list(summ._create_value_output(values))
    assert result == expected


def test_post_quantile_value_line():
    roundto = 1
    summ = pm.trace._PosteriorQuantileSummary(roundto, 0.05)
    values = [{'lo': 0, 'q25': 1, 'q50': 2, 'q75': 4, 'hi': 5},
              {'lo': 6, 'q25': 7, 'q50': 8, 'q75': 9, 'hi': 10},]

    expected = ['0.0            1.0            2.0            4.0            5.0',
                '6.0            7.0            8.0            9.0            10.0']
    result = list(summ._create_value_output(values))
    assert result == expected


def test_stats_output_lines_0d_variable():
    roundto = 1
    x = np.arange(5)

    summ = pm.trace._StatSummary(roundto, 5, 0.05)

    expected = ['  Mean             SD               MC Error         95% HPD interval',
                '  -------------------------------------------------------------------',
                '  ',
                '  2.0              1.4              0.6              [0.0, 4.0]',]

    result = list(summ._get_lines(x))
    assert result == expected


def test_stats_output_lines_1d_variable():
    roundto = 1
    x = np.arange(10).reshape(5, 2)

    summ = pm.trace._StatSummary(roundto, 5, 0.05)

    expected = ['  Mean             SD               MC Error         95% HPD interval',
                '  -------------------------------------------------------------------',
                '  ',
                '  4.0              2.8              1.3              [0.0, 8.0]',
                '  5.0              2.8              1.3              [1.0, 9.0]',]
    result = list(summ._get_lines(x))
    assert result == expected


def test_stats_output_lines_2d_variable():
    roundto = 1
    x = np.arange(20).reshape(5, 2, 2)

    summ = pm.trace._StatSummary(roundto, 5, 0.05)

    expected = ['  Mean             SD               MC Error         95% HPD interval',
                '  -------------------------------------------------------------------',
                '  ..............................[0, :]...............................',
                '  8.0              5.7              2.5              [0.0, 16.0]',
                '  9.0              5.7              2.5              [1.0, 17.0]',
                '  ..............................[1, :]...............................',
                '  10.0             5.7              2.5              [2.0, 18.0]',
                '  11.0             5.7              2.5              [3.0, 19.0]',]
    result = list(summ._get_lines(x))
    assert result == expected


def test_posterior_quantiles_output_lines_0d_variable():
    roundto = 1
    x = np.arange(5)

    summ = pm.trace._PosteriorQuantileSummary(roundto, 0.05)

    expected = ['  Posterior quantiles:',
                '  2.5            25             50             75             97.5',
                '  |--------------|==============|==============|--------------|',
                '  ',
                '  0.0            1.0            2.0            3.0            4.0',]

    result = list(summ._get_lines(x))
    assert result == expected


def test_posterior_quantiles_output_lines_1d_variable():
    roundto = 1
    x = np.arange(10).reshape(5, 2)

    summ = pm.trace._PosteriorQuantileSummary(roundto, 0.05)

    expected = ['  Posterior quantiles:',
                '  2.5            25             50             75             97.5',
                '  |--------------|==============|==============|--------------|',
                '  ',
                '  0.0            2.0            4.0            6.0            8.0',
                '  1.0            3.0            5.0            7.0            9.0']

    result = list(summ._get_lines(x))
    assert result == expected


def test_posterior_quantiles_output_lines_2d_variable():
    roundto = 1
    x = np.arange(20).reshape(5, 2, 2)

    summ = pm.trace._PosteriorQuantileSummary(roundto, 0.05)

    expected = ['  Posterior quantiles:',
                '  2.5            25             50             75             97.5',
                '  |--------------|==============|==============|--------------|',
                '  .............................[0, :].............................',
                '  0.0            4.0            8.0            12.0           16.0',
                '  1.0            5.0            9.0            13.0           17.0',
                '  .............................[1, :].............................',
                '  2.0            6.0            10.0           14.0           18.0',
                '  3.0            7.0            11.0           15.0           19.0',]

    result = list(summ._get_lines(x))
    assert result == expected


def test_groupby_leading_idxs_0d_variable():
    result = {k: list(v) for k, v in pm.trace._groupby_leading_idxs(())}
    assert list(result.keys()) == [()]
    assert result[()] == [()]


def test_groupby_leading_idxs_1d_variable():
    result = {k: list(v) for k, v in pm.trace._groupby_leading_idxs((2,))}
    assert list(result.keys()) == [()]
    assert result[()] == [(0,), (1,)]


def test_groupby_leading_idxs_2d_variable():
    result = {k: list(v) for k, v in pm.trace._groupby_leading_idxs((2, 3))}

    expected_keys = [(0,), (1,)]
    keys = list(result.keys())
    assert len(keys) == len(expected_keys)
    for key in keys:
        assert result[key] == [key + (0,), key + (1,), key + (2,)]


def test_groupby_leading_idxs_3d_variable():
    result = {k: list(v) for k, v in pm.trace._groupby_leading_idxs((2, 3, 2))}

    expected_keys = [(0, 0), (0, 1), (0, 2),
                     (1, 0), (1, 1), (1, 2)]
    keys = list(result.keys())
    assert len(keys) == len(expected_keys)
    for key in keys:
        assert result[key] == [key + (0,), key + (1,)]
