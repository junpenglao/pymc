#   Copyright 2020 The PyMC Developers
#
#   Licensed under the Apache License, Version 2.0 (the "License");
#   you may not use this file except in compliance with the License.
#   You may obtain a copy of the License at
#
#       http://www.apache.org/licenses/LICENSE-2.0
#
#   Unless required by applicable law or agreed to in writing, software
#   distributed under the License is distributed on an "AS IS" BASIS,
#   WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
#   See the License for the specific language governing permissions and
#   limitations under the License.

import pickle
import unittest

import aesara
import aesara.tensor as at
import numpy as np
import numpy.testing as npt
import pandas as pd
import pytest

from aesara.tensor.subtensor import AdvancedIncSubtensor

import pymc3 as pm

from pymc3 import Deterministic, Potential
from pymc3.blocking import RaveledVars
from pymc3.distributions import Normal, logpt_sum, transforms
from pymc3.model import ValueGradFunction


class NewModel(pm.Model):
    def __init__(self, name="", model=None):
        super().__init__(name, model)
        assert pm.modelcontext(None) is self
        # 1) init variables with Var method
        self.register_rv(pm.Normal.dist(), "v1")
        self.v2 = pm.Normal("v2", mu=0, sigma=1)
        # 2) Potentials and Deterministic variables with method too
        # be sure that names will not overlap with other same models
        pm.Deterministic("d", at.constant(1))
        pm.Potential("p", at.constant(1))


class DocstringModel(pm.Model):
    def __init__(self, mean=0, sigma=1, name="", model=None):
        super().__init__(name, model)
        self.register_rv(Normal.dist(mu=mean, sigma=sigma), "v1")
        Normal("v2", mu=mean, sigma=sigma)
        Normal("v3", mu=mean, sigma=Normal("sd", mu=10, sigma=1, testval=1.0))
        Deterministic("v3_sq", self.v3 ** 2)
        Potential("p1", at.constant(1))


class TestBaseModel:
    def test_setattr_properly_works(self):
        with pm.Model() as model:
            pm.Normal("v1")
            assert len(model.vars) == 1
            with pm.Model("sub") as submodel:
                submodel.register_rv(pm.Normal.dist(), "v1")
                assert hasattr(submodel, "v1")
                assert len(submodel.vars) == 1
            assert len(model.vars) == 2
            with submodel:
                submodel.register_rv(pm.Normal.dist(), "v2")
                assert hasattr(submodel, "v2")
                assert len(submodel.vars) == 2
            assert len(model.vars) == 3

    def test_context_passes_vars_to_parent_model(self):
        with pm.Model() as model:
            assert pm.model.modelcontext(None) == model
            assert pm.Model.get_context() == model
            # a set of variables is created
            nm = NewModel()
            assert pm.Model.get_context() == model
            # another set of variables are created but with prefix 'another'
            usermodel2 = NewModel(name="another")
            assert pm.Model.get_context() == model
            assert usermodel2._parent == model
            # you can enter in a context with submodel
            with usermodel2:
                usermodel2.register_rv(pm.Normal.dist(), "v3")
                pm.Normal("v4")
                # this variable is created in parent model too
        assert "another_v2" in model.named_vars
        assert "another_v3" in model.named_vars
        assert "another_v3" in usermodel2.named_vars
        assert "another_v4" in model.named_vars
        assert "another_v4" in usermodel2.named_vars
        assert hasattr(usermodel2, "v3")
        assert hasattr(usermodel2, "v2")
        assert hasattr(usermodel2, "v4")
        # When you create a class based model you should follow some rules
        with model:
            m = NewModel("one_more")
        assert m.d is model["one_more_d"]
        assert m["d"] is model["one_more_d"]
        assert m["one_more_d"] is model["one_more_d"]


class TestNested:
    def test_nest_context_works(self):
        with pm.Model() as m:
            new = NewModel()
            with new:
                assert pm.modelcontext(None) is new
            assert pm.modelcontext(None) is m
        assert "v1" in m.named_vars
        assert "v2" in m.named_vars

    def test_named_context(self):
        with pm.Model() as m:
            NewModel(name="new")
        assert "new_v1" in m.named_vars
        assert "new_v2" in m.named_vars

    def test_docstring_example1(self):
        usage1 = DocstringModel()
        assert "v1" in usage1.named_vars
        assert "v2" in usage1.named_vars
        assert "v3" in usage1.named_vars
        assert "v3_sq" in usage1.named_vars
        assert len(usage1.potentials), 1

    def test_docstring_example2(self):
        with pm.Model() as model:
            DocstringModel(name="prefix")
        assert "prefix_v1" in model.named_vars
        assert "prefix_v2" in model.named_vars
        assert "prefix_v3" in model.named_vars
        assert "prefix_v3_sq" in model.named_vars
        assert len(model.potentials), 1

    def test_duplicates_detection(self):
        with pm.Model():
            DocstringModel(name="prefix")
            with pytest.raises(ValueError):
                DocstringModel(name="prefix")

    def test_model_root(self):
        with pm.Model() as model:
            assert model is model.root
            with pm.Model() as sub:
                assert model is sub.root


class TestObserved:
    def test_observed_rv_fail(self):
        with pytest.raises(TypeError):
            with pm.Model():
                x = Normal("x")
                Normal("n", observed=x)

    def test_observed_type(self):
        X_ = pm.floatX(np.random.randn(100, 5))
        X = pm.floatX(aesara.shared(X_))
        with pm.Model():
            x1 = pm.Normal("x1", observed=X_)
            x2 = pm.Normal("x2", observed=X)

        assert x1.type == X.type
        assert x2.type == X.type


def test_duplicate_vars():
    with pytest.raises(ValueError) as err:
        with pm.Model():
            pm.Normal("a")
            pm.Normal("a")
    err.match("already exists")

    with pytest.raises(ValueError) as err:
        with pm.Model():
            pm.Normal("a")
            pm.Normal("a", transform=transforms.log)
    err.match("already exists")

    with pytest.raises(ValueError) as err:
        with pm.Model():
            a = pm.Normal("a")
            pm.Potential("a", a ** 2)
    err.match("already exists")

    with pytest.raises(ValueError) as err:
        with pm.Model():
            pm.Binomial("a", 10, 0.5)
            pm.Normal("a", transform=transforms.log)
    err.match("already exists")


def test_empty_observed():
    data = pd.DataFrame(np.ones((2, 3)) / 3)
    data.values[:] = np.nan
    with pm.Model(aesara_config={"compute_test_value": "raise"}):
        a = pm.Normal("a", observed=data)

        assert isinstance(a.tag.observations.owner.op, AdvancedIncSubtensor)
        # The masked observations are replaced by elements of the RV `a`,
        # which means that they should all have the same sample test values
        a_data = a.tag.observations.owner.inputs[1]
        npt.assert_allclose(a.tag.test_value.flatten(), a_data.tag.test_value)

        # Let's try this again with another distribution
        b = pm.Gamma("b", alpha=1, beta=1, observed=data)
        assert isinstance(b.tag.observations.owner.op, AdvancedIncSubtensor)
        b_data = b.tag.observations.owner.inputs[1]
        npt.assert_allclose(b.tag.test_value.flatten(), b_data.tag.test_value)


class TestValueGradFunction(unittest.TestCase):
    def test_no_extra(self):
        a = at.vector("a")
        a.tag.test_value = np.zeros(3, dtype=a.dtype)
        f_grad = ValueGradFunction([a.sum()], [a], {}, mode="FAST_COMPILE")
        assert f_grad._extra_vars == []

    def test_invalid_type(self):
        a = at.ivector("a")
        a.tag.test_value = np.zeros(3, dtype=a.dtype)
        a.dshape = (3,)
        a.dsize = 3
        with pytest.raises(TypeError) as err:
            ValueGradFunction([a.sum()], [a], {}, mode="FAST_COMPILE")
        err.match("Invalid dtype")

    def setUp(self):
        extra1 = at.iscalar("extra1")
        extra1_ = np.array(0, dtype=extra1.dtype)
        extra1.dshape = tuple()
        extra1.dsize = 1

        val1 = at.vector("val1")
        val1_ = np.zeros(3, dtype=val1.dtype)
        val1.dshape = (3,)
        val1.dsize = 3

        val2 = at.matrix("val2")
        val2_ = np.zeros((2, 3), dtype=val2.dtype)
        val2.dshape = (2, 3)
        val2.dsize = 6

        self.val1, self.val1_ = val1, val1_
        self.val2, self.val2_ = val2, val2_
        self.extra1, self.extra1_ = extra1, extra1_

        self.cost = extra1 * val1.sum() + val2.sum()

        self.f_grad = ValueGradFunction(
            [self.cost], [val1, val2], {extra1: extra1_}, mode="FAST_COMPILE"
        )

    def test_extra_not_set(self):
        with pytest.raises(ValueError) as err:
            self.f_grad.get_extra_values()
        err.match("Extra values are not set")

        with pytest.raises(ValueError) as err:
            size = self.val1_.size + self.val2_.size
            self.f_grad(np.zeros(size, dtype=self.f_grad.dtype))
        err.match("Extra values are not set")

    def test_grad(self):
        self.f_grad.set_extra_values({"extra1": 5})
        size = self.val1_.size + self.val2_.size
        array = RaveledVars(
            np.ones(size, dtype=self.f_grad.dtype),
            (
                ("val1", self.val1_.shape, self.val1_.dtype),
                ("val2", self.val2_.shape, self.val2_.dtype),
            ),
        )
        val, grad = self.f_grad(array)
        assert val == 21
        npt.assert_allclose(grad, [5, 5, 5, 1, 1, 1, 1, 1, 1])

    @pytest.mark.xfail(reason="Lognormal not refactored for v4")
    def test_edge_case(self):
        # Edge case discovered in #2948
        ndim = 3
        with pm.Model() as m:
            pm.Lognormal(
                "sigma", mu=np.zeros(ndim), tau=np.ones(ndim), shape=ndim
            )  # variance for the correlation matrix
            pm.HalfCauchy("nu", beta=10)
            step = pm.NUTS()

        func = step._logp_dlogp_func
        func.set_extra_values(m.test_point)
        q = func.dict_to_array(m.test_point)
        logp, dlogp = func(q)
        assert logp.size == 1
        assert dlogp.size == 4
        npt.assert_allclose(dlogp, 0.0, atol=1e-5)

    @pytest.mark.xfail(reason="Missing values not refactored for v4")
    def test_tensor_type_conversion(self):
        # case described in #3122
        X = np.random.binomial(1, 0.5, 10)
        X[0] = -1  # masked a single value
        X = np.ma.masked_values(X, value=-1)
        with pm.Model() as m:
            x1 = pm.Uniform("x1", 0.0, 1.0)
            x2 = pm.Bernoulli("x2", x1, observed=X)

        gf = m.logp_dlogp_function()

        assert m["x2_missing"].type == gf._extra_vars_shared["x2_missing"].type

    def test_aesara_switch_broadcast_edge_cases_1(self):
        # Tests against two subtle issues related to a previous bug in Theano
        # where `tt.switch` would not always broadcast tensors with single
        # values https://github.com/pymc-devs/aesara/issues/270

        # Known issue 1: https://github.com/pymc-devs/pymc3/issues/4389
        data = pm.floatX(np.zeros(10))
        with pm.Model() as m:
            p = pm.Beta("p", 1, 1)
            obs = pm.Bernoulli("obs", p=p, observed=data)

        npt.assert_allclose(
            logpt_sum(obs).eval({p.tag.value_var: pm.floatX(np.array(0.0))}),
            np.log(0.5) * 10,
        )

    @pytest.mark.xfail(reason="TruncatedNormal not refactored for v4")
    def test_aesara_switch_broadcast_edge_cases_2(self):
        # Known issue 2: https://github.com/pymc-devs/pymc3/issues/4417
        # fmt: off
        data = np.array([
            1.35202174, -0.83690274, 1.11175166, 1.29000367, 0.21282749,
            0.84430966, 0.24841369, 0.81803141, 0.20550244, -0.45016253,
        ])
        # fmt: on
        with pm.Model() as m:
            mu = pm.Normal("mu", 0, 5)
            obs = pm.TruncatedNormal("obs", mu=mu, sigma=1, lower=-1, upper=2, observed=data)

        npt.assert_allclose(m.dlogp([mu])({"mu": 0}), 2.499424682024436, rtol=1e-5)


@pytest.mark.xfail(reason="DensityDist not refactored for v4")
def test_multiple_observed_rv():
    "Test previously buggy multi-observed RV comparison code."
    y1_data = np.random.randn(10)
    y2_data = np.random.randn(100)
    with pm.Model() as model:
        mu = pm.Normal("mu")
        x = pm.DensityDist(  # pylint: disable=unused-variable
            "x", pm.Normal.dist(mu, 1.0).logp, observed={"value": 0.1}
        )
    assert not model["x"] == model["mu"]
    assert model["x"] == model["x"]
    assert model["x"] in model.observed_RVs
    assert not model["x"] in model.vars


def test_tempered_logp_dlogp():
    with pm.Model() as model:
        pm.Normal("x")
        pm.Normal("y", observed=1)

    func = model.logp_dlogp_function()
    func.set_extra_values({})

    func_temp = model.logp_dlogp_function(tempered=True)
    func_temp.set_extra_values({})

    func_nograd = model.logp_dlogp_function(compute_grads=False)
    func_nograd.set_extra_values({})

    func_temp_nograd = model.logp_dlogp_function(tempered=True, compute_grads=False)
    func_temp_nograd.set_extra_values({})

    x = np.ones(1, dtype=func.dtype)
    assert func(x) == func_temp(x)
    assert func_nograd(x) == func(x)[0]
    assert func_temp_nograd(x) == func(x)[0]

    func_temp.set_weights(np.array([0.0], dtype=func.dtype))
    func_temp_nograd.set_weights(np.array([0.0], dtype=func.dtype))
    npt.assert_allclose(func(x)[0], 2 * func_temp(x)[0])
    npt.assert_allclose(func(x)[1], func_temp(x)[1])

    npt.assert_allclose(func_nograd(x), func(x)[0])
    npt.assert_allclose(func_temp_nograd(x), func_temp(x)[0])

    func_temp.set_weights(np.array([0.5], dtype=func.dtype))
    func_temp_nograd.set_weights(np.array([0.5], dtype=func.dtype))
    npt.assert_allclose(func(x)[0], 4 / 3 * func_temp(x)[0])
    npt.assert_allclose(func(x)[1], func_temp(x)[1])

    npt.assert_allclose(func_nograd(x), func(x)[0])
    npt.assert_allclose(func_temp_nograd(x), func_temp(x)[0])


def test_model_pickle(tmpdir):
    """Tests that PyMC3 models are pickleable"""
    with pm.Model() as model:
        x = pm.Normal("x")
        pm.Normal("y", observed=1)

    file_path = tmpdir.join("model.p")
    with open(file_path, "wb") as buff:
        pickle.dump(model, buff)


def test_model_pickle_deterministic(tmpdir):
    """Tests that PyMC3 models are pickleable"""
    with pm.Model() as model:
        x = pm.Normal("x")
        z = pm.Normal("z")
        pm.Deterministic("w", x / z)
        pm.Normal("y", observed=1)

    file_path = tmpdir.join("model.p")
    with open(file_path, "wb") as buff:
        pickle.dump(model, buff)
