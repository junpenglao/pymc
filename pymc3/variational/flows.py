import numpy as np
import theano
from theano import tensor as tt

from pymc3.theanof import change_flags
from .opvi import node_property, collect_shared_to_list

__all__ = [
    'Formula',
    'PlanarFlow',
    'LocFlow',
    'ScaleFlow'
]


_param_to_flow = dict()
_short_name_to_flow = dict()


def register_flow(cls):
    _param_to_flow[frozenset(cls.__param_spec__)] = cls
    _short_name_to_flow[cls.short_name] = cls
    return cls


def flow_from_params(params):
    return _param_to_flow[frozenset(params)]


def flow_from_short_name(name):
    return _short_name_to_flow[name]


class Formula(object):
    """
    Helpful class to use string like formulas with
    __call__ syntax similar to Flow.__init__

    Parameters
    ----------
    formula : str
        string representing normalizing flow
        e.g. 'planar', 'planar*4', 'planar*4-radial*3', 'planar-radial-planar'
        Yet simple pattern is supported:

            1. dash separated flow identifiers
            2. star for replication after flow identifier

    Methods
    -------
    __call__(z0, dim, jitter) - initializes and links all flows returning the last one
    """

    def __init__(self, formula):
        identifiers = formula.lower().replace(' ', '').split('-')
        self.formula = '-'.join(identifiers)
        identifiers = [idf.split('*') for idf in identifiers]
        self.flows = []

        for tup in identifiers:
            if tup[0] not in _short_name_to_flow:
                raise ValueError('No such flow: %r' % tup[0])
            if len(tup) == 1:
                self.flows.append(flow_from_short_name(tup[0]))
            elif len(tup) == 2:
                self.flows.extend([flow_from_short_name(tup[0])]*int(tup[1]))
            else:
                raise ValueError('Wrong format: %s' % formula)
        if len(self.flows) == 0:
            raise ValueError('No flows in formula')

    def __call__(self, z0=None, dim=None, jitter=.001, params=None):
        if len(self.flows) == 0:
            raise ValueError('No flows in formula')
        if params is None:
            params = dict()
        flow = z0
        for i, flow_cls in enumerate(self.flows):
            flow = flow_cls(dim=dim, jitter=jitter, z0=flow, **params.get(i, {}))
        return flow

    def __reduce__(self):
        return self.__class__, self.formula

    def __latex__(self):
        return r'Formula{\mathcal{N}(0, 1) -> %s}' % self.formula

    __repr__ = _latex_repr_ = __latex__

    def get_param_spec_for(self, **kwargs):
        res = dict()
        for i, cls in enumerate(self.flows):
            res[i] = cls.get_param_spec_for(**kwargs)
        return res


class AbstractFlow(object):
    shared_params = None
    __param_spec__ = dict()
    short_name = ''

    def __init__(self, z0=None, dim=None, jitter=.001):
        self.__jitter = jitter
        if isinstance(z0, AbstractFlow):
            parent = z0
            dim = parent.dim
            z0 = parent.forward
        else:
            parent = None
        if dim is not None:
            self.dim = dim
        else:
            raise ValueError('Cannot infer dimension of flow, '
                             'please provide dim or Flow instance as z0')
        if z0 is None:
            self.z0 = tt.matrix()  # type: tt.TensorVariable
        else:
            self.z0 = z0
        self.parent = parent

    def add_param(self, user=None, name=None, ref=0., dtype='floatX'):
        if dtype == 'floatX':
            dtype = theano.config.floatX
        spec = self.__param_spec__[name]
        shape = tuple(eval(s, {'d': self.dim}) for s in spec)
        if user is None:
            return theano.shared(
                np.asarray(np.random.normal(size=shape) * self.__jitter + ref).astype(dtype),
                name=name
            )
        else:
            if self.is_local:
                shape = (-1, ) + shape
            return user.reshape(shape)

    @property
    def params(self):
        return collect_shared_to_list(self.shared_params)

    @property
    def all_params(self):
        params = self.params  # type: list
        current = self
        while not current.isroot:
            current = current.parent
            params.extend(current.params)
        return params

    @property
    @change_flags(compute_test_value='off')
    def sum_logdets(self):
        dets = [self.logdet]
        current = self
        while not current.isroot:
            current = current.parent
            dets.append(current.logdet)
        return tt.add(*dets)

    @node_property
    def forward(self):
        raise NotImplementedError

    @node_property
    def logdet(self):
        raise NotImplementedError

    @change_flags(compute_test_value='off')
    def forward_pass(self, z0):
        ret = theano.clone(self.forward, {self.root.z0: z0})
        try:
            ret.tag.test_value = np.random.normal(
                size=z0.tag.test_value.shape
            ).astype(self.z0.dtype)
        except AttributeError:
            ret.tag.test_value = self.root.z0.tag.test_value
        return ret

    __call__ = forward_pass

    @property
    def root(self):
        current = self
        while not current.isroot:
            current = current.parent
        return current

    @property
    def formula(self):
        f = self.short_name
        current = self
        while not current.isroot:
            current = current.parent
            f = current.short_name + '-' + f
        return f

    @property
    def isroot(self):
        return self.parent is None

    @property
    def is_local(self):
        return self.z0.ndim == 3

    @classmethod
    def get_param_spec_for(cls, **kwargs):
        res = dict()
        for name, fshape in cls.__param_spec__.items():
            res[name] = tuple(eval(s, kwargs) for s in fshape)
        return res

    def __repr__(self):
        return 'Flow{%s}' % self.short_name

    def __str__(self):
        return self.short_name


class FlowFn(object):
    @staticmethod
    def fn(*args):
        raise NotImplementedError

    @staticmethod
    def inv(*args):
        raise NotImplementedError

    @staticmethod
    def deriv(*args):
        raise NotImplementedError

    def __call__(self, *args):
        return self.fn(*args)


class LinearFlow(AbstractFlow):
    __param_spec__ = dict(u=('d', ), w=('d', ), b=())

    @change_flags(compute_test_value='off')
    def __init__(self, h, z0=None, dim=None, u=None, w=None, b=None, jitter=.001):
        self.h = h
        super(LinearFlow, self).__init__(dim=dim, z0=z0, jitter=jitter)
        u = self.add_param(u, 'u')
        w = self.add_param(w, 'w')
        b = self.add_param(b, 'b')
        self.shared_params = dict(u=u, w=w, b=b)
        self.u_, self.w_ = self.make_uw(self.u, self.w)

    u = property(lambda self: self.shared_params['u'])
    w = property(lambda self: self.shared_params['w'])
    b = property(lambda self: self.shared_params['b'])

    def make_uw(self, u, w):
        raise NotImplementedError('Need to implement valid U, W transform')

    @node_property
    def forward(self):
        z = self.z0  # sxd
        u = self.u_   # d
        w = self.w_   # d
        b = self.b   # .
        h = self.h   # f
        # h(sxd \dot d + .)  = s
        if not self.is_local:
            hwz = h(z.dot(w) + b)  # s
            # sxd + (s \outer d) = sxd
            z1 = z + tt.outer(hwz,  u)  # sxd
            return z1
        else:
            z = z.swapaxes(0, 1)
            # z bxsxd
            # u bxd
            # w bxd
            b = b.dimshuffle(0, 'x')
            # b bx-
            hwz = h(tt.batched_dot(z, w) + b)  # bxs
            # bxsxd + (bxsx- * bx-xd) = bxsxd
            hwz = hwz.dimshuffle(0, 1, 'x')  # bxsx-
            u = u.dimshuffle(0, 'x', 1)  # bx-xd
            z1 = z + hwz * u  # bxsxd
            return z1.swapaxes(0, 1)  # sxbxd

    @node_property
    def logdet(self):
        z = self.z0  # sxd
        u = self.u_  # d
        w = self.w_  # d
        b = self.b  # .
        deriv = self.h.deriv  # f'
        if not self.is_local:
            # f'(sxd \dot d + .) * -xd = sxd
            phi = deriv(z.dot(w) + b) * w.dimshuffle('x', 0)
            # \abs(. + sxd \dot d) = s
            det = tt.abs_(1. + phi.dot(u))
            return tt.log(det)
        else:
            z = z.swapaxes(0, 1)
            # z bxsxd
            # u bxd
            # w bxd
            # b b
            # f'(bxsxd \bdot bxd + bx-) * bx-xd = bxsxd
            phi = deriv(tt.batched_dot(z, w) + b) * w.dimshuffle(0, 'x', 1)
            # \abs(. + bxsxd \bdot bxd) = bxs
            det = tt.abs_(1. + tt.batched_dot(phi, u))
            return tt.log(det).sum(0)  # s


class Tanh(FlowFn):
    fn = tt.tanh
    inv = tt.arctanh

    @staticmethod
    def deriv(*args):
        x, = args
        return 1. - tt.tanh(x) ** 2


@register_flow
class PlanarFlow(LinearFlow):
    short_name = 'planar'

    def __init__(self, **kwargs):
        super(PlanarFlow, self).__init__(h=Tanh(), **kwargs)

    def make_uw(self, u, w):
        if not self.is_local:
            # u_ : d
            # w_ : d
            wu = u.dot(w)  # .
            mwu = -1. + tt.nnet.softplus(wu)  # .
            # d + (. - .) * d / .
            u_h = (
                u+(mwu-wu) *
                w/((w**2).sum()+1e-10)
            )
            return u_h, w
        else:
            # u_ : bxd
            # w_ : bxd
            wu = (u*w).sum(-1, keepdims=True)  # bx-
            mwu = -1. + tt.nnet.softplus(wu)  # bx-
            # bxd + (bx- - bx-) * bxd / bx- = bxd
            u_h = (
                u
                + (mwu - wu)
                * w / ((w ** 2).sum(-1, keepdims=True) + 1e-10)
            )
            return u_h, w


class ReferencePointFlow(AbstractFlow):
    __param_spec__ = dict(a=(), b=(), z_ref=('d', ))

    @change_flags(compute_test_value='off')
    def __init__(self, h, z0=None, dim=None, a=None, b=None, z_ref=None, jitter=.1):
        super(ReferencePointFlow, self).__init__(dim=dim, z0=z0, jitter=jitter)
        a = self.add_param(a, 'a')
        b = self.add_param(b, 'b')
        if z_ref is None:
            if hasattr(self.z0, 'tag') and hasattr(self.z0.tag, 'test_value'):
                z_ref = self.add_param(
                    z_ref, 'z_ref',
                    ref=self.z0.tag.test_value[0],
                    dtype=self.z0.dtype
                )
            else:
                z_ref = self.add_param(
                    z_ref, 'z_ref', dtype=self.z0.dtype
                )
        self.h = h
        self.shared_params = dict(a=a, b=b, z_ref=z_ref)
        self.a_, self.b_ = self.make_ab(self.a, self.b)

    a = property(lambda self: self.shared_params['a'])
    b = property(lambda self: self.shared_params['b'])
    z_ref = property(lambda self: self.shared_params['z_ref'])

    def make_ab(self, a, b):
        raise NotImplementedError('Need to specify how to get a, b')

    @node_property
    def forward(self):
        a = self.a_  # .
        b = self.b_  # .
        z_ref = self.z_ref  # d
        z = self.z0  # sxd
        h = self.h  # h(a, r)
        if self.is_local:
            # a bx-x-
            # b bx-x-
            # z bxsxd
            # z_ref bx-xd
            z = z.swapaxes(0, 1)
            a = a.dimshuffle(0, 'x', 'x')
            b = b.dimshuffle(0, 'x', 'x')
            z_ref = z_ref.dimshuffle(0, 'x', 1)
        r = (z - z_ref).norm(2, axis=-1, keepdims=True)  # sx- (bxsx-)
        # global: sxd + . * h(., sx-) * (sxd - sxd) = sxd
        # local: bxsxd + b * h(b, bxsx-) * (bxsxd - bxsxd) = bxsxd
        z1 = z + b * h(a, r) * (z-z_ref)
        if self.is_local:
            z1 = z1.swapaxes(0, 1)
        return z1

    @node_property
    def logdet(self):
        d = self.dim
        a = self.a_  # .
        b = self.b_  # .
        z_ref = self.z_ref  # d
        z = self.z0  # sxd
        h = self.h  # h(a, r)
        deriv = self.h.deriv  # h'(a, r)
        if self.is_local:
            z = z.swapaxes(0, 1)
        r = (z - z_ref).norm(2, axis=-1, keepdims=True)  # s
        har = h(a, r)
        dar = deriv(a, r)
        logdet = tt.log((1. + b*har)**(d-1) * (1. + b*har + b*dar*r))
        if self.is_local:
            logdet = logdet.sum(0)
        return logdet


class Radial(FlowFn):
    @staticmethod
    def fn(*args):
        a, r = args
        return 1./(a+r)

    @staticmethod
    def inv(*args):
        a, y = args
        return 1./y - a

    @staticmethod
    def deriv(*args):
        a, r = args
        return -1. / (a + r) ** 2


@register_flow
class RadialFlow(ReferencePointFlow):
    short_name = 'radial'

    def __init__(self, **kwargs):
        super(RadialFlow, self).__init__(Radial(), **kwargs)

    def make_ab(self, a, b):
        a = tt.exp(a)
        b = -a + tt.nnet.softplus(b)
        return a, b


@register_flow
class LocFlow(AbstractFlow):
    __param_spec__ = dict(loc=('d', ))
    short_name = 'loc'

    def __init__(self, z0=None, dim=None, loc=None, jitter=0):
        super(LocFlow, self).__init__(dim=dim, z0=z0, jitter=jitter)
        loc = self.add_param(loc, 'loc')
        self.shared_params = dict(loc=loc)

    loc = property(lambda self: self.shared_params['loc'])

    @node_property
    def forward(self):
        loc = self.loc  # (bx)d
        z = self.z0  # sx(bx)d
        return z + loc

    @node_property
    def logdet(self):
        return tt.zeros((self.z0.shape[0],))


@register_flow
class ScaleFlow(AbstractFlow):
    __param_spec__ = dict(log_scale=('d', ))
    short_name = 'scale'

    @change_flags(compute_test_value='off')
    def __init__(self, z0=None, dim=None, log_scale=None, jitter=.1):
        super(ScaleFlow, self).__init__(dim=dim, z0=z0, jitter=jitter)
        log_scale = self.add_param(log_scale, 'log_scale')
        self.scale = tt.exp(log_scale)
        self.shared_params = dict(log_scale=log_scale)

    log_scale = property(lambda self: self.shared_params['log_scale'])

    @node_property
    def forward(self):
        scale = self.scale  # (bx)d
        z = self.z0  # sx(bx)d
        return z * scale

    @node_property
    def logdet(self):
        return tt.repeat(tt.sum(self.log_scale), self.z0.shape[0])


@register_flow
class HouseholderFlow(AbstractFlow):
    __param_spec__ = dict(v=('d', ))
    short_name = 'hh'

    @change_flags(compute_test_value='raise')
    def __init__(self, z0=None, dim=None, v=None, jitter=.1):
        super(HouseholderFlow, self).__init__(dim=dim, z0=z0, jitter=jitter)
        v = self.add_param(v, 'v')
        self.shared_params = dict(v=v)
        if self.is_local:
            vv = v.dimshuffle(0, 1, 'x') * v.dimshuffle(0, 'x', 1)
            I = tt.eye(dim).dimshuffle('x', 0, 1)
            vvn = ((v**2).sum(-1)+1e-10).dimshuffle(0, 'x', 'x')
        else:
            vv = tt.outer(v, v)
            I = tt.eye(dim)
            vvn = ((v**2).sum(-1)+1e-10)
        self.H = I - 2. * vv / vvn

    @node_property
    def forward(self):
        z = self.z0  # sxd
        H = self.H   # dxd
        if self.is_local:
            return tt.batched_dot(z.swapaxes(0, 1), H).swapaxes(0, 1)
        else:
            return z.dot(H)

    @node_property
    def logdet(self):
        return tt.zeros((self.z0.shape[0],))
