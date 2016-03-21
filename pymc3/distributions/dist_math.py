'''
Created on Mar 7, 2011

@author: johnsalvatier
'''
from __future__ import division

import numpy as np
import theano.tensor as T

from .special import gammaln, multigammaln


def bound(logp, *conditions):
    """
    Bounds a log probability density with several conditions

    Parameters
    ----------
    logp : float
    *conditions : booleans

    Returns
    -------
    logp if all conditions are true
    -inf if some are false
    """
    return T.switch(alltrue(conditions), logp, -np.inf)


def alltrue(vals):
    ret = 1
    for c in vals:
        ret = ret * (1 * c)
    return ret


def logpow(x, m):
    """
    Calculates log(x**m) since m*log(x) will fail when m, x = 0.
    """
    # return m * log(x)
    return T.switch(T.any(T.eq(x, 0)), -np.inf, m * T.log(x))


def factln(n):
    return gammaln(n + 1)


def binomln(n, k):
    return factln(n) - factln(k) - factln(n - k)


def betaln(x, y):
    return gammaln(x) + gammaln(y) - gammaln(x + y)


def std_cdf(x):
    """
    Calculates the standard normal cumulative distribution function.
    """
    return 0.5 + 0.5*T.erf(x / T.sqrt(2.))
    

def i0(x):
    """
    Calculates the 0 order modified Bessel function of the first kind""
    """
    return T.switch(T.lt(x, 5), 1 + x**2/4 + x**4/64 + x**6/2304 + x**8/147456
     + x**10/14745600 + x**12/2123366400, 
     np.e**x/(2*np.pi*x)**0.5*(1+1/(8*x) + 9/(128*x**2) + 225/(3072*x**3)
      + 11025/(98304*x**4)))


def i1(x):
    """
    Calculates the 1 order modified Bessel function of the first kind""
    """
    return T.switch(T.lt(x, 5), x/2 + x**3/16 + x**5/384 + x**7/18432 + 
    x**9/1474560 + x**11/176947200 +  x**13/29727129600 ,
    np.e**x/(2*np.pi*x)**0.5*(1-3/(8*x) + 15/(128*x**2) + 315/(3072*x**3)
     + 14175/(98304*x**4)))
