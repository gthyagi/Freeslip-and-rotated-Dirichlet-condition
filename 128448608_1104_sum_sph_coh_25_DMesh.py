#!/usr/bin/env python
# coding: utf-8

# # 3D Subduction Model of Sunda Margin
# For model details check following
# 1. Model extent (minmax lon, lat)
# 2. Resolution in each direction
# 3. Number of cpus
# 4. Cohesion

# In[1]:


import underworld as uw
import math
from underworld import function as fn
# import glucifer
import numpy as np
import os
os.environ["UW_ENABLE_TIMING"] = "1"
import time
import h5py


# **Scaling of parameters**

# In[2]:


rho_M             = 1.
g_M               = 1.
Height_M          = 1.
viscosity_M       = 1.


# In[3]:


rho_N             = 50.0 # kg/m**3  note delta rho
g_N               = 9.81 # m/s**2
Height_N          = 6371e3 # m
viscosity_N       = 1e19 # Pa.sec or kg/m.sec


# In[4]:


#Non-dimensional (scaling)
rho_scaling 		= rho_N/rho_M
viscosity_scaling 	= viscosity_N/viscosity_M
g_scaling 		= g_N/g_M
Height_scaling 		= Height_N/Height_M
pressure_scaling 	= rho_scaling * g_scaling * Height_scaling
time_scaling 		= viscosity_scaling/pressure_scaling
strainrate_scaling 	= 1./time_scaling
velocity_scaling        = Height_scaling/time_scaling
pressure_scaling_MPa    = rho_scaling * g_scaling * Height_scaling/1e6


# \begin{align}
# {\tau}_N = \frac{{\rho}_{0N}{g}_N{l}_N}{{\rho}_{0M}{g}_M{l}_M} {\tau}_M
# \end{align}
# 
# \begin{align}
# {V}_N = \frac{{\eta}_{0M}}{{\eta}_{0N}}\frac{{\rho}_{0N}{g}_N{{l}_N}^2}{{\rho}_{0M}{g}_M{{l}_M}^2} {V}_M
# \end{align}

# In[ ]:


# max, min values of lon & lat in the region
lon_min 	= 61.0
lon_max 	= 120.0
lat_min 	= -45.0
lat_max 	= 35.0
diff_lon 	= lon_max - lon_min
diff_lat 	= lat_max - lat_min
mid_lon 	= (lon_max + lon_min)/2
mid_lat 	= (lat_max + lat_min)/2
# print (diff_lon, diff_lat)


# In[ ]:


# model resolution
deform_mesh     = True # deforms the mesh
ncpus           = 1104
resX            = 448
resY            = 608
resZ            = 128
dim             = 3
Mdepth          = 2891.
inner_radius    = (6371.-Mdepth)/6371.
outer_radius    = 6371./6371.


# subducting plate crustal layer thickness in the model
crust_depth = 30

# resolution string
if deform_mesh:
    res = str(resZ)+str(resX)+str(resY)+'_'+str(ncpus)+'_'+'DMesh'
else:
    res = str(resZ)+str(resX)+str(resY)+'_'+str(ncpus)

# cohesion value and yield stress form
sum_coh_dim = 25 # value in MPa
him_coh_dim = 10 # value in MPa
cohesion    = np.round(sum_coh_dim/pressure_scaling_MPa, 4)
cohesion_him= np.round(him_coh_dim/pressure_scaling_MPa, 4)
mu          = 0.01
UP_den      = 0.0
SP_den      = 1.0
LM_visc     = 30.0


# In[ ]:


# cohesion value and yield stress form
'''
tao_Y1: const_cohesion (C, constant cohesion in the crust)
tao_Y2: cohesion_mu_rho_g_z (C + mu_rho_g*depth, depth dependent yield stress)
tao_Y3: cohesion_mu_eff_rho_g_z (C + mu_eff*rho_g*depth, velocity weaking mu)
'''
tao_Y_OC = 'const_coh'


# In[ ]:


# solver options
"""
solver: mg, fgmres, mumps(not working), slud (superludist)
"""
solver 			= 'fgmres'
inner_rtol 		= 1e-3   # default = 1e-5
outer_rtol 		= 1e-3
penalty_mg 		= 1.0e2
penalty_mumps 	        = 1.0e6


# In[ ]:


# adding string to output directory
if tao_Y_OC == 'const_coh':
    file_str 	= str(res)+'_'+str(crust_depth)+'_'+str(sum_coh_dim)
if tao_Y_OC == 'coh_mu_rho_g_z':
    file_str 	= str(res)+'_'+str(crust_depth)+'_'+str(sum_coh_dim)+'_'+str(mu)
if tao_Y_OC == 'coh_mu_eff_rho_g_z':
    file_str 	= str(res)+'_'+str(crust_depth)+'_'+str(sum_coh_dim)+'_'+str(mu)


# In[ ]:


# creating plots
create_plot = False


# In[ ]:


# creating output directory
outputPath = os.path.join(os.path.abspath("/scratch/n69/tg7098/"), "sum_sph_"+str(file_str)+"_"+str(tao_Y_OC)+"_UPDen_"+str(UP_den)+"_SPDen_"+str(SP_den)+"_LMVisc_"+str(int(LM_visc))+"/")
if uw.mpi.rank == 0:
    if not os.path.exists(outputPath):
        os.makedirs(outputPath)
uw.mpi.barrier()


# ### Create mesh and finite element variables

# In[ ]:


"""
mesh information
nodes in each direction (8,12,12) = (radial, long, lat)
min number of nodes in lon lat direction such that no particle is eject from the spherical domain
"""
mesh		    = uw.mesh.FeMesh_SRegion(elementRes    =(resZ,resX,resY),
                                             radialLengths =(inner_radius, outer_radius),
                                             latExtent     =diff_lat,
                                             longExtent    =diff_lon)


# In[ ]:


# timing loading process
if uw.mpi.rank == 0:
    print ("---------------------------------Start timer to load mesh data---------------------------------")
uw.timing.start()

if deform_mesh:
    mesh.load('/scratch/n69/tg7098/spherical_swarm/swarm_'+str(res)+'/mesh_'+str(res)+'.h5')

uw.timing.stop()
if uw.mpi.rank == 0:
    print ("---------------------------------End timer to load mesh data---------------------------------")
uw.timing.print_table()


# In[ ]:


velocityField		= mesh.add_variable( nodeDofCount=dim )
pressureField		= mesh.subMesh.add_variable( nodeDofCount=1 )
densityField		= mesh.add_variable( nodeDofCount=1 )

vc			= mesh.add_variable( nodeDofCount=dim ) #julesfix
vc_eqNum 		= uw.systems.sle.EqNumber( vc, False )  
vcVec			= uw.systems.sle.SolutionVector(vc, vc_eqNum)

#thyagi
strainRateInvField	= mesh.add_variable( nodeDofCount=1 )


# In[ ]:


# loading density field
# densityField.load('../tomo_project/lm_densityField_'+str(res)+'.h5')


# In[ ]:


def sphxyz2sphlonlatr(xyz):
    """
    Function to convert (x,y,z) pts in spherical region to (lon, lat, radius) values in spherical region.
    input data format = (x, y, z)
    output data format = (lon, lat, radius)
    """
    ptsnew	= np.zeros((len(xyz[:,0]),3))
    x_tanlon	= xyz[:,0]/xyz[:,2]
    y_tanlat	= xyz[:,1]/xyz[:,2]
    factor	= np.sqrt(x_tanlon**2 + y_tanlat**2 + 1)
    ptsnew[:,2] = xyz[:,2] * factor
    ptsnew[:,1] = np.arctan(y_tanlat) * (180/math.pi)
    ptsnew[:,0] = np.arctan(x_tanlon) * (180/math.pi)
    return ptsnew


# In[ ]:


def sphlonlatr2sphxyz(data):
    """
    Converts (lon, lat, radius) in spherical region to (x, y, z) in spherical region.
    input data format = (lon, lat, radius)
    output data format = (x, y, z)
    """
    newcoords 		= np.zeros((len(data[:,0]),3))
    (x,y) 		= (np.tan(data[:,0]*np.pi/180.0), np.tan(data[:,1]*np.pi/180.0))
    d 			= data[:,2] / np.sqrt( x**2 + y**2 + 1)
    newcoords[:,0] 	= d*x
    newcoords[:,1] 	= d*y
    newcoords[:,2] 	= d
    return newcoords


# In[ ]:


# loading swarm and material variable
swarm_matVar_path = '/scratch/n69/tg7098/spherical_swarm/swarm_'+str(res)+'/'
swarm 	          = uw.swarm.Swarm(mesh, particleEscape=True)
swarm.load(swarm_matVar_path+'swarm_'+str(res)+'.h5')
materialVariable  = swarm.add_variable("int", 1)
materialVariable.load(swarm_matVar_path+'matVar_'+str(res)+'_cor.h5')
pol_con           = uw.swarm.PopulationControl(swarm, aggressive=True, particlesPerCell=20)

# adding trench tracer and build a tracer swarm
sum_trench_coords = np.loadtxt(swarm_matVar_path+'sum_trench_coords_61_120_-45_35.txt', delimiter=',')
sum_trench_tracer = uw.swarm.Swarm(mesh, particleEscape=True)
sum_trench_tracer_coords = sum_trench_tracer.add_particles_with_coordinates(sum_trench_coords)
sum_trench_tracer_vel = sum_trench_tracer.add_variable( "double", 3 )

him_trench_coords = np.loadtxt(swarm_matVar_path+'him_trench_coords_61_120_-45_35.txt', delimiter=',')
him_trench_tracer = uw.swarm.Swarm(mesh, particleEscape=True)
him_trench_tracer_coords = him_trench_tracer.add_particles_with_coordinates(him_trench_coords)
him_trench_tracer_vel = him_trench_tracer.add_variable( "double", 3 )

# In[ ]:


# all boundary nodes
inner = mesh.specialSets["innerWall_VertexSet"]
outer = mesh.specialSets["outerWall_VertexSet"]
W     = mesh.specialSets["westWall_VertexSet"]
E     = mesh.specialSets["eastWall_VertexSet"]
S     = mesh.specialSets["southWall_VertexSet"]
N     = mesh.specialSets["northWall_VertexSet"]

allWalls 	= mesh.specialSets["AllWalls_VertexSet"]
NS0 		= N+S-(E+W)
# build corner edges node indexset
cEdge 		= (N&W)+(N&E)+(S&E)+(S&W)


# In[ ]:


# boundary conditions available "BC_FREESLIP, "BC_NOSLIP, "BC_LIDDRIVEN"
bc_wanted = 'BC_FREESLIP'


# In[ ]:


# boundary conditions

# zero all dofs of velocityField
velocityField.data[...] = 0.

if bc_wanted == "BC_NOSLIP":
    # No-slip on all sides; normal component = 0 and tagential component = 0
    velBC_NS = uw.conditions.RotatedDirichletCondition(variable=velocityField, indexSetsPerDof=(allWalls,allWalls,allWalls))

elif bc_wanted == "BC_FREESLIP":
    # free-slip on all sides; normal component = 0 and tagential component != 0
    velocityField.data[cEdge.data] = (0.,0.,0.)
    velBC_FS = uw.conditions.RotatedDirichletCondition(variable=velocityField, indexSetsPerDof=(inner+outer,E+W+cEdge,NS0+cEdge), basis_vectors=(mesh._e1, mesh._e2, mesh._e3))
elif bc_wanted == "BC_LIDDRIVEN":
    # lid-driven case
        
    # build driving node indexset & apply velocities with zero radial component
    drivers = outer - (N+S+E+W)
    velocityField.data[drivers.data] = (0.,1.,1.)
    
    # build corner edges node indexset and apply velocities with zero non-radial components
    cEdge = (N&W)+(N&E)+(S&E)+(S&W)
    velocityField.data[cEdge.data] = (0.,0.,0.)
    
    # apply altogether.
    NS0 = N+S - (E+W)
    vBC = uw.conditions.RotatedDirichletCondition(variable=velocityField, indexSetsPerDof=(inner+outer,drivers+E+W+cEdge,drivers+NS0+cEdge), basis_vectors = (mesh._e1, mesh._e2, mesh._e3)) # optional, can include cEdge on the 3rd component
                                                  
elif bc_wanted == "BC_SWIO_FREESLIP_NE_NOSLIP":
    velocityField.data[cEdge.data] = (0.,0.,0.)
    velBC_FS_NS_mix = uw.conditions.RotatedDirichletCondition(variable=velocityField, indexSetsPerDof=(N+E+outer+inner,N+E+cEdge+W,N+E+cEdge+S), basis_vectors = (mesh._e1, mesh._e2, mesh._e3))
else:
    raise ValueError("Can't find an option for the 'bc_wanted' = {}".format(bc_wanted))


# In[ ]:


# material indices
SubCrustIndex   = 4
SubMantleIndex  = 3
CCrustIndex     = 2
CMantleIndex    = 1
UMantleIndex    = 0
HIMCrustIndex   = 5
HIMLithoIndex   = 6
LMantleIndex    = 8
WeakPBBoxesIndex = 9

# In[ ]:


# viscosity values
upperMantleViscosity 	=  1.0
lowerMantleViscosity 	=  LM_visc 
slabMantleViscosity     =  1000.0  
slabCrustViscosity      =  1000.0
CCrustViscosity         =  1000.0
CMantleViscosity        =  1000.0
WeakPBBoxesViscosity    =  10.0

# julesfix - use the pure cartesian velocity instead
strainRate_2ndInvariant = fn.tensor.second_invariant(fn.tensor.symmetric(vc.fn_gradient))


# In[ ]:


# rheology1: viscoplastic crust and rest is newtonian
coord = fn.input()

if tao_Y_OC == 'const_coh':
    cohesion_slab 	= cohesion
    tao_Y_slab 		= cohesion_slab
    tao_Y_slab_him      = cohesion_him
if tao_Y_OC == 'coh_mu_rho_g_z':
    cohesion_slab 	= cohesion
    mu_rho_g 		= mu*1.0*1.  # mu = 0.6, rho = 3300, g = 9.81 
    tao_Y_slab = cohesion_slab  + mu_rho_g *(1. - fn.math.sqrt(coord[0]**2. + coord[1]**2. + coord[2]**2.))
if tao_Y_OC == 'coh_mu_eff_rho_g_z':
    cohesion_slab 	= cohesion
    vc_crit 		= (4.4/(velocity_scaling))*(10e-2/(365*24*60*60)) # v_crit = 4.4 cm/yr
    vc_mag 		= fn.math.sqrt(fn.math.dot(vc,vc))
    mu_eff 		= 0.6*(1.-0.7) + 0.6*(0.7/(1.+(vc_mag/vc_crit)))  # mu_s*(1-gamma) + mu_s*(gamma/(1+(v/vc)))
    rho_g 		= 1.0*1.  # mu = 0.6, rho = 3300, g = 9.81 
    tao_Y_slab 		= cohesion_slab  + mu_eff*rho_g *(1. - fn.math.sqrt(coord[0]**2. + coord[1]**2. + coord[2]**2.))
yielding_slab       = 0.5 * tao_Y_slab / (strainRate_2ndInvariant+1.0e-18)
yielding_slab_him   = 0.5 * tao_Y_slab_him / (strainRate_2ndInvariant+1.0e-18)


# In[ ]:


# choosing rheology
viscoplastic 	= True
Non_Newtonian 	= False

# all are Newtonian except viscoplastic oceanic crust
eta_min = upperMantleViscosity
eta_max = slabCrustViscosity
if viscoplastic:
    slabYieldvisc = fn.exception.SafeMaths(fn.misc.max(eta_min, fn.misc.min(slabCrustViscosity, yielding_slab)))
    slabYieldvisc_him = fn.exception.SafeMaths(fn.misc.max(eta_min, fn.misc.min(slabCrustViscosity, yielding_slab_him)))

# Non-Newtonian and viscoplastic crust (~30km) and Newtonian mantle
if Non_Newtonian:
    n 			= 3.
    sr_T 		= 1e-4
    creep_dislocation 	= slabMantleViscosity * fn.math.pow(((strainRate_2ndInvariant+1.0e-18)/sr_T), (1.-n)/n)
    creep 		= fn.exception.SafeMaths(fn.misc.min(creep_dislocation,slabMantleViscosity))
    slabYieldvisc 	= fn.exception.SafeMaths(fn.misc.min(creep, yielding))


# In[ ]:


# Viscosity function for the materials 
viscosityMap 	= { UMantleIndex    : upperMantleViscosity, 
                    LMantleIndex    : lowerMantleViscosity, 
                    SubCrustIndex   : slabYieldvisc,
                    SubMantleIndex  : slabMantleViscosity,
                    CCrustIndex	    : CCrustViscosity,
                    CMantleIndex    : CMantleViscosity,
                    HIMCrustIndex   : slabYieldvisc_him,
                    HIMLithoIndex   : slabMantleViscosity,
                    WeakPBBoxesIndex: WeakPBBoxesViscosity}

viscosityFn 	= fn.branching.map( fn_key = materialVariable, mapping = viscosityMap )


# In[ ]:


# mantleDensity = densityField
mantleDensity 	= 0.0
slabDensity 	= SP_den
CCrustDensity 	= UP_den
HIMDensity      = SP_den
densityMap 	= { UMantleIndex 	: mantleDensity, 
                    LMantleIndex 	: mantleDensity, 
                    SubCrustIndex       : slabDensity,
                    SubMantleIndex      : slabDensity,
                    CCrustIndex		: CCrustDensity,
                    CMantleIndex	: CCrustDensity,
                    HIMCrustIndex       : HIMDensity,
                    HIMLithoIndex       : HIMDensity,
                    WeakPBBoxesIndex    : mantleDensity}

densityFn   	= fn.branching.map( fn_key = materialVariable, mapping = densityMap )


# In[ ]:


buoyancyFn = -1.*densityFn * mesh.fn_unitvec_radial()


# **System Setup**

# In[ ]:


stokesSLE = uw.systems.Stokes(velocityField, 
                              pressureField, 
                              fn_viscosity	= viscosityFn + 0.*velocityField[0], # julesfix - ensures the nonlinearity is pickedup
#                               voronoi_swarm = swarm,
                              fn_bodyforce	= buoyancyFn, 
                              conditions	= velBC_FS, 
                              _removeBCs	= False )                           


# In[ ]:


def postSolve():
    #julesfix realign vc using the rotation matrix on stokes
    uw.libUnderworld.Underworld.AXequalsY(
        stokesSLE._rot._cself,
        stokesSLE._velocitySol._cself,
        vcVec._cself,
        False
        )


# In[ ]:


stokesSolver = uw.systems.Solver(stokesSLE)


# In[ ]:


# inner solver type
if solver == 'fmgres':
    pass
if solver == 'lu':
    stokesSolver.set_inner_method("lu")
if solver == 'mumps':
    stokesSolver.set_penalty(penalty_mumps)
    stokesSolver.set_inner_method("mumps")
if solver == 'mg':
    stokesSolver.set_penalty(penalty_mg)
    stokesSolver.set_inner_method("mg")
#     stokesSolver.options.mg.levels = 6
if solver == 'slud':
    stokesSolver.set_inner_method('superludist')


# In[ ]:


# rtol value
if inner_rtol != 'default':
    stokesSolver.set_inner_rtol(inner_rtol)
    stokesSolver.set_outer_rtol(outer_rtol)


# In[ ]:


advector = uw.systems.SwarmAdvector(swarm=swarm, velocityField=vc, order=2) #julesfix
advector_sum_trench_tracer = uw.systems.SwarmAdvector( swarm=sum_trench_tracer, velocityField=vc, order=2)
advector_him_trench_tracer = uw.systems.SwarmAdvector( swarm=him_trench_tracer, velocityField=vc, order=2)

# **Analysis tools**

# In[ ]:


#The root mean square Velocity
velSquared 	= uw.utils.Integral(fn.math.dot(vc,vc), mesh)
area 		= uw.utils.Integral(1., mesh)
Vrms 		= math.sqrt(velSquared.evaluate()[0]/area.evaluate()[0])


# In[ ]:


if create_plot:
    # plotting indexed particles
    figParticle = glucifer.Figure(title="Particle Index" )
    figParticle.append( glucifer.objects.Points(swarm, materialVariable, pointSize=2, 
                                                colours='white green red purple blue', discrete=True) )

    #Plot of Velocity Magnitude
    figVelocityMag = glucifer.Figure(title="Velocity magnitude"+'_'+str(cohesion) )
    figVelocityMag.append( glucifer.objects.Surface(mesh, fn.math.sqrt(fn.math.dot(vc,vc)), onMesh=True) ) #julesfix

    #Plot of Strain Rate, 2nd Invariant
    figStrainRate = glucifer.Figure(title="Strain rate 2nd invariant"+'_'+str(cohesion), quality=3 )
    figStrainRate.append( glucifer.objects.Surface(mesh, strainRate_2ndInvariant, logScale=True, onMesh=True) )
    figStrainRate.append( glucifer.objects.VectorArrows(mesh, vc, scaling=1, arrowHead=0.2) ) #julesfix

    #Plot of particles viscosity
    figViscosity = glucifer.Figure(title="Viscosity"+'_'+str(cohesion), quality=3 )
    figViscosity.append( glucifer.objects.Points(swarm, viscosityFn, pointSize=2,logScale=True ) )

    #Plot of particles stress invariant
    figStress = glucifer.Figure(title="Stress 2nd invariant"+'_'+str(cohesion), quality=3  )
    figStress.append(glucifer.objects.Points(swarm, 2.0*viscosityFn*strainRate_2ndInvariant, pointSize=2, logScale=True) )


# **Update function**

# In[ ]:


# define an update function
def update():
    # Retrieve the maximum possible timestep for the advection system.
    dt = advector.get_max_dt()
    # Advect using this timestep size.
    advector.integrate(dt)
    advector_sum_trench_tracer.integrate(dt)
    advector_him_trench_tracer.integrate(dt)
    return time+dt, step+1


# **Checkpointing function definition**

# In[ ]:


# variables in checkpoint function
# Creating viscosity Field
viscosityField       = mesh.add_variable(nodeDofCount=1)
viscosityVariable    = swarm.add_variable(dataType="float", count=1)

# creating material variable field
matVarField          = mesh.add_variable(nodeDofCount=1)

# Creating strain rate fn and fields
strainRateFn         = fn.tensor.symmetric(vc.fn_gradient)
strainRateDField     = mesh.add_variable(nodeDofCount=3)
strainRateNDField    = mesh.add_variable(nodeDofCount=3)
strainRateVariable   = swarm.add_variable(dataType="float", count=6) # strain rate variable

# Creating stress fn and fields
stressFn             = 2. * viscosityFn * strainRateFn
stressInvFn          = fn.tensor.second_invariant(stressFn)
stressInvVariable    = swarm.add_variable(dataType="float", count=1) # stress Inv variable
stressVariable       = swarm.add_variable(dataType="float", count=6) # stress variable

stressDField         = mesh.add_variable(nodeDofCount=3) # stress diagonal components
stressNDField        = mesh.add_variable(nodeDofCount=3) # stress non-diagonal components
stressInvField_sMesh = mesh.subMesh.add_variable(nodeDofCount=1) # creating field on submesh
stressField_sMesh    = mesh.subMesh.add_variable(nodeDofCount=6) # stress components

#creating density field
densityVariable      = swarm.add_variable("float", 1)
density_Field        = mesh.add_variable(nodeDofCount=1)


# In[ ]:


meshHnd = mesh.save(outputPath+'mesh.00000.h5')
def checkpoint():

    # save swarm and swarm variables
    swarmHnd            = swarm.save(outputPath+'swarm.'+str(step).zfill(5)+'.h5')
    materialVariableHnd = materialVariable.save(outputPath+'materialVariable.'+ str(step).zfill(5) +'.h5')
    
    # projecting matvar to mesh field
    matVar_projector    = uw.utils.MeshVariable_Projection(matVarField, materialVariable, type=0) 
    matVar_projector.solve()
    matVarFieldHnd      = matVarField.save(outputPath+'matVarField.'+str(step).zfill(5)+'.h5')
    matVarField.xdmf(outputPath+'matVarField.'+str(step).zfill(5)+'.xdmf', matVarFieldHnd, "matVarField", meshHnd, "mesh", modeltime=time)
    
    # saving velocity field in xyz format
    velocityHnd     = vc.save(outputPath+'velocityField.'+str(step).zfill(5)+'.h5', meshHnd) #julesfix
    vc.xdmf(outputPath+'velocityField.'+str(step).zfill(5)+'.xdmf', velocityHnd, "velocity", meshHnd, "mesh", modeltime=time) #julesfix
    
    # saving velocity field in rthetaphi format
    v_rthetaphi_Hnd = velocityField.save(outputPath+'vField_rthetaphi.'+str(step).zfill(5)+'.h5', meshHnd)
    
    # saving pressure field
    pressureHnd     = pressureField.save(outputPath+'pressureField.'+str(step).zfill(5)+'.h5', meshHnd)
    pressureField.xdmf(outputPath+'pressureField.'+str(step).zfill(5)+'.xdmf', pressureHnd, "pressure", meshHnd, "mesh", modeltime=time)
    
    # save visualisation
    if create_plot:
        figParticle.save(    outputPath + "particle."    + str(step).zfill(5))
        figVelocityMag.save( outputPath + "velocityMag." + str(step).zfill(5))
        figStrainRate.save(  outputPath + "strainRate."  + str(step).zfill(5))
        figViscosity.save(   outputPath + "viscosity."   + str(step).zfill(5))
        figStress.save(      outputPath + "stress."      + str(step).zfill(5))
    
    # saving density Field
    densityVariable.data[:]     = densityFn.evaluate(swarm)[:]
    den_projector               = uw.utils.MeshVariable_Projection(densityField, densityVariable, type=0)
    den_projector.solve()
    densityFieldHnd             = densityField.save(outputPath+'densityField.'+ str(step).zfill(5) +'.h5')
    densityField.xdmf(outputPath+'densityField.'+str(step).zfill(5)+'.xdmf', densityFieldHnd,"densityField",meshHnd,"mesh",modeltime=time)
    
    # saving strainrate invariant field
    strainRateInvField.data[:]  = strainRate_2ndInvariant.evaluate(mesh)[:]
    strainRateInvFieldHnd       = strainRateInvField.save(outputPath+'strainRateInvField.'+str(step).zfill(5)+'.h5', meshHnd)
    strainRateInvField.xdmf(outputPath+'strainRateInvField.'+str(step).zfill(5)+'.xdmf', strainRateInvFieldHnd, "strainRateInv", meshHnd, "mesh", modeltime=time)

#     # saving stress Inv on swarm
#     stressInvVariable.data[:]  = stressInvFn.evaluate(swarm)[:]
#     stressInvVariableHnd       = stressInvVariable.save(outputPath+'stressInvVariable.'+ str(step).zfill(5) +'.h5')
#     stressInvVariable.xdmf(outputPath+'stressInvVariable.'+str(step).zfill(5)+'.xdmf', stressInvVariableHnd,"stressInvVariable",swarmHnd,"swarm",modeltime=time)
    
    # saving viscosity variable (swarm) and field (mesh)
    viscosityVariable.data[:]   = viscosityFn.evaluate(swarm)[:]
    viscosityVariableHnd        = viscosityVariable.save(outputPath+'viscosityVariable.'+ str(step).zfill(5) +'.h5')
    visc_projector              = uw.utils.MeshVariable_Projection(viscosityField, viscosityVariable, type=0) # Project to meshfield
    visc_projector.solve()
    viscosityFieldHnd           = viscosityField.save(outputPath+'viscosityField.'+str(step).zfill(5)+'.h5')
    viscosityField.xdmf(outputPath+'viscosityField.'+str(step).zfill(5)+'.xdmf', viscosityFieldHnd, "viscosityField", meshHnd, "mesh", modeltime=time)

    # saving strain rate variable (swarm) and field (mesh)
    strainRateVariable.data[:]  = strainRateFn.evaluate(swarm)[:]
    strainRateVariableHnd       = strainRateVariable.save(outputPath+'strainRateVariable.'+ str(step).zfill(5) +'.h5')
    strainRateDField.data[:]    = strainRateFn.evaluate(mesh)[:,0:3]
    strainRateNDField.data[:]   = strainRateFn.evaluate(mesh)[:,3:6]
    strainRateDFieldHnd         = strainRateDField.save(outputPath+'strainRateDField.'+str(step).zfill(5)+'.h5')
    strainRateDField.xdmf(outputPath+'strainRateDField.'+str(step).zfill(5)+'.xdmf', strainRateDFieldHnd,"strainRateDField",meshHnd,"mesh",modeltime=time)
    strainRateNDFieldHnd        = strainRateNDField.save(outputPath+'strainRateNDField.'+ str(step).zfill(5) +'.h5')
    strainRateNDField.xdmf(outputPath+'strainRateNDField.'+str(step).zfill(5)+'.xdmf', strainRateNDFieldHnd,"strainRateNDField",meshHnd,"mesh",modeltime=time)
    
    # saving stress variable (swarm) and field (submesh)
    stressVariable.data[:]      = stressFn.evaluate(swarm)[:]
    stressVariableHnd           = stressVariable.save(outputPath+'stressVariable.'+ str(step).zfill(5) +'.h5')
    stress_proj                 = uw.utils.MeshVariable_Projection(stressField_sMesh, stressVariable, voronoi_swarm=swarm, type=0)
    stress_proj.solve()
    stressDField.data[:]        = stressField_sMesh.evaluate(mesh)[:,0:3]
    stressNDField.data[:]       = stressField_sMesh.evaluate(mesh)[:,3:6]
    stressDFieldHnd             = stressDField.save(outputPath+'stressDField.'+str(step).zfill(5)+'.h5')
    stressDField.xdmf(outputPath+'stressDField.'+str(step).zfill(5)+'.xdmf', stressDFieldHnd, "stressDField", meshHnd, "mesh", modeltime=time)
    stressNDFieldHnd            = stressNDField.save(outputPath+'stressNDField.'+str(step).zfill(5)+'.h5')
    stressNDField.xdmf(outputPath+'stressNDField.'+str(step).zfill(5)+'.xdmf', stressNDFieldHnd, "stressNDField", meshHnd, "mesh", modeltime=time)

    # saving stress Invariant on submesh
    stressInvVariable.data[:]   = stressInvFn.evaluate(swarm)[:]
    stress_Inv_proj             = uw.utils.MeshVariable_Projection(stressInvField_sMesh, stressInvVariable, voronoi_swarm=swarm, type=0)
    stress_Inv_proj.solve()
    stressInvField_sMeshHnd     = stressInvField_sMesh.save(outputPath+'stressInvField_sMesh.'+str(step).zfill(5)+'.h5')
    stressInvField_sMesh.xdmf(outputPath+'stressInvField_sMesh.'+str(step).zfill(5)+'.xdmf', stressInvField_sMeshHnd, "stressInvField_sMesh", meshHnd, "mesh", modeltime=time)


# Main simulation loop
# =======
# 
# The main time stepping loop begins here. Inside the time loop the velocity field is solved for via the Stokes system solver and then the swarm is advected using the advector integrator. Basic statistics are output to screen each timestep.

# In[ ]:


time 			= 0.  # Initial time
step 			= 0   # Initial timestep
maxSteps 		= 2   # Maximum timesteps
steps_output 	        = 1   # output every 10 timesteps


# In[ ]:


while step < maxSteps:
    # Solve non linear Stokes system
    stokesSolver.solve(nonLinearIterate=True, callback_post_solve=postSolve, print_stats=True, nonLinearMaxIterations=20)
    # output figure to file at intervals = steps_output
    if step % steps_output == 0 or step == maxSteps-1:
        pol_con.repopulate()
        checkpoint()
        Vrms = math.sqrt( velSquared.evaluate()[0]/area.evaluate()[0] )
        if uw.mpi.rank==0:
            print ('step = {0:6d}; time = {1:.3e}; Vrms = {2:.3e}'.format(step,time,Vrms))
    # update
    time,step = update()


# In[ ]:


if uw.mpi.rank == 0:
    print("Inner (velocity) Solve Options:")
    stokesSolver.options.A11.list()
    print('----------------------------------')
    print("Outer Solve Options:")
    stokesSolver.options.scr.list()
    print('----------------------------------')
    print("Multigrid (where enabled) Options:")
    stokesSolver.options.mg.list()
    # print("Penalty for mg:", penalty_mg)


# **Post simulation visualisation**

# In[ ]:


if create_plot:
    figParticle.show()
    figVelocityMag.show()
    figStrainRate.show()
    figViscosity.show()
    figStress.show()


# In[ ]:


# saving sum trench velocities to h5 file
sum_trench_tracer_vel.data[:] = vc.evaluate(sum_trench_tracer.data)[:]
sum_trench_tracer_vel.save(outputPath+'sum_trench_velocities.h5')
sum_trench_tracer.save(outputPath+'sum_trench_coords.h5')

him_trench_tracer_vel.data[:] = vc.evaluate(him_trench_tracer.data)[:]
him_trench_tracer_vel.save(outputPath+'him_trench_velocities.h5')
him_trench_tracer.save(outputPath+'him_trench_coords.h5')

