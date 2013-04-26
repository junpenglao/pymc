'''
Created on Mar 12, 2011

@author: johnsalvatier
'''
import numdifftools as nd
import numpy as np 
from ..core import *

__all__ = ['approx_hess', 'find_hessian', 'trace_cov']

@withmodel
def approx_hess(model, point, vars=None):
    """
    Returns an approximation of the Hessian at the current chain location.
    
    Parameters
    ----------
    model : Model (optional if in `with` context)
    point : dict
    vars : list 
        Variables for which Hessian is to be calculated.
    """
    if vars is None :
        vars = model.cont_vars

    point = Point(model, point)

    bij = DictToArrayBijection(ArrayOrdering(vars), point)
    dlogp = bij.mapf(model.dlogpc(vars))

    
    def grad_logp(point): 
        return np.nan_to_num(dlogp(point))
    
    '''
    Find the jacobian of the gradient function at the current position
    this should be the Hessian; invert it to find the approximate 
    covariance matrix.
    '''
    return -nd.Jacobian(grad_logp)(bij.map(point))

@withmodel
def find_hessian(model, point, vars = None): 
    """
    Returns Hessian of logp at the point passed.
    
    Parameters
    ----------
    model : Model (optional if in `with` context)
    point : dict
    vars : list 
        Variables for which Hessian is to be calculated.
    """
    H = model.d2logpc(vars)
    return H(Point(model, point))

def trace_cov(trace, vars = None):
    """
    Calculate the flattened covariance matrix using a sample trace

    Useful if you want to base your covariance matrix for further sampling on some initial samples.

    Parameters
    ----------
    trace : Trace 
    vars : list 
        variables for which to calculate covariance matrix

    Returns 
    -------
    r : array (n,n)
        covariance matrix
    """

    if vars is None: 
        vars = trace.samples.keys

    def flat_t(var):
        x = trace[str(var)]
        return x.reshape((x.shape[0], np.prod(x.shape[1:])))
    
    return np.cov(np.concatenate(map(flat_t, vars), 1).T)
