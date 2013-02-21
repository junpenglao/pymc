'''
Created on May 10, 2012

@author: jsalvatier
'''
from pymc import * 
from numpy.random import normal
import numpy as np 
import pylab as pl 
from itertools import product


"""
This model is U shaped because of the non identifiability. I think this is the same as the Rosenbrock function.
As n increases, the walls become steeper but the distribution does not shrink towards the mode. 
As n increases this distribution gets harder and harder for HMC to sample.

Low Flip HMC seems to do a bit better.

This example comes from 
Discussion of Riemann manifold Langevin and
Hamiltonian Monte Carlo methods by M.
Girolami and B. Calderhead

http://arxiv.org/abs/1011.0057
"""
N = 200
model = Model()
Data = model.Data 
Var = model.Var


x = Var('x', Normal(0, 1))
y = Var('y', Normal(0, 1))
N = 200
Data(np.zeros(N), Normal(x + y**2, 1.))


start = model.test_point
hess = np.ones(2)*np.diag(approx_hess(model, start))[0]


#step_method = hmc_lowflip_step(model, model.vars, hess,is_cov = False, step_size = .25, a = .9)
step_method = hmc_step(model, model.vars, hess, trajectory_length = 4., is_cov = False)

history, state, t = sample(3e3, step_method, start)

print "took :", t
pl.figure()
pl.hexbin(history['x'], history['y'])



# lets plot the samples vs. the actual distribution
from theano import function
xn = 1500
yn = 1000

xs = np.linspace(-3, .25, xn)[np.newaxis,:]
ys =  np.linspace(-1.5,1.5, yn)[:,np.newaxis]

like = (xs + ys**2)**2*N
post = np.exp(-.5*(xs**2 + ys**2 + like))
post = post

pl.figure()
extent = np.min(xs), np.max(xs), np.min(ys), np.max(ys)
pl.imshow(post, extent = extent)
