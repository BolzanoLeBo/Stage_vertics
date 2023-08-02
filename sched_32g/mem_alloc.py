import time
import gurobipy as gp
from gurobipy import GRB
import numpy as np
import os
from multiprocessing import Pool


from gen_taskset import *

def solver(taskset) : 
    n = len(taskset)
    
    model = gp.Model("ilp_ram_allocator")
    model.setParam('OutputFlag', 0)
    model.setParam('TimeLimit', 3600)
    model.setParam('Threads', 1)

    x_f = model.addVars(n,12, vtype = GRB.BINARY)
    x_p = model.addVars(n,2, vtype = GRB.BINARY)
    x_pre = model.addVars(n,2, vtype = GRB.BINARY)
    x_c = model.addVars(n,2, vtype = GRB.BINARY)
    x_ro = model.addVars(n,4, vtype = GRB.BINARY)

    x_prec = model.addVars(n,4, vtype = GRB.BINARY)
    mulfp = []
    for i in range(12) : 
        mulfp.append(model.addVars(n,2,vtype = GRB.BINARY))

    
    mulcro = []
    for i in range(4) : 
        mulcro.append(model.addVars(n,4,vtype = GRB.BINARY))

    '''
        x_f : 
        100 000 000 000 16 range 2 
        010 000 000 000 26 range 2 
        001 000 000 000 16
        ...
        001 000 000 001 170 boost

        x_p : 
        10 cf 
        01 cc

        x_pre : 
        10 pre_on
        01 pre_off

        x_c : 
        10 cache_on
        01 cache_off

        x_ro : 
        1000 no_ro 
        0100 ro_f
        0010 ro_r
        0001  ro_c

        '''
    
    #var dimension 
    #no multiple allocation
    model.addConstrs(gp.quicksum(x_f[i,j] for j in range(12) )== 1 for i in range(n))
    model.addConstrs(gp.quicksum(x_p[i,j] for j in range(2) )== 1 for i in range(n))
    '''model.addConstrs(gp.quicksum(x_pre[i,j] for j in range(2) )== 1 for i in range(n))
    model.addConstrs(gp.quicksum(x_c[i,j] for j in range(2) )== 1 for i in range(n))'''
    model.addConstrs(gp.quicksum(x_prec[i,j] for j in range(4) )== 1 for i in range(n))
    model.addConstrs(gp.quicksum(x_ro[i,j] for j in range(4) )== 1 for i in range(n))
    #FLASH size constraint
    #we can have instruction or ro data
    model.addConstr(gp.quicksum((taskset[i].size_i * x_p[i,0] + 
                                taskset[i].size_ro * x_ro[i,1]) 
                                for i in range(n)) <= taskset.flash_size)
    #CCM size constraint
    #we can have instruction or ro data
    model.addConstr(gp.quicksum((taskset[i].size_i * x_p[i,1] + 
                                taskset[i].size_ro * x_ro[i,3])
                                for i in range(n)) <= taskset.ccm_size)
    #SRAM size constraint 
    #we can have input data or ro data 
    model.addConstr(gp.quicksum(taskset[i].size_ro * x_ro[i,2]
                                #+ taskset[i].size_d * x_d[i,1]
                                for i in range(n)) <= taskset.ram_size)
    
    #we cannot multiply more than 3 elements so we do pre-mutliplication
    model.addConstrs(mulfp[f][i,p] == x_f[i,f]*x_p[i,p] 
                  for i in range (n) 
                  for f in range (3)
                  for p in range (2))
    
    #model.addConstrs(x_prec[i,pre + c] == x_c[i,c]*x_pre[i,pre] for i in range(n) for c in range(2) for pre in range(2) )
    '''
    x_prec
    c   pre     10 and 10   10 and 01    01 and 10   01 and 01
    0   0           1           0            0           0
    0   1           0           1            0           0
    1   0           0           0            1           0
    1   1           0           0            0           1
    '''
    #x_prec_i = j  => x_c_i = j>1    x_pre_i = j%2     


    model.addConstrs(mulcro[c][i,ro] == x_prec[i,c]*x_ro[i,ro] 
                  for i in range (n) 
                  for c in range (4)
                  for ro in range (4))
    #mulcro[c,i,ro] = 1 => x_c[i,c>1]=1 x_pre[i,c%2]=1 x_ro[i,ro] = 1
    


    ''''#utilization less than 1 
    model.addConstr(gp.quicksum((taskset[i].perf[f][p][c>1][c%2][ro][0]/taskset[i].period)
                                 *mulfp[f][i,p]*mulcro[c][i,ro]
                for f in range(12) 
                for p in range(2) 
                for c in range(4) 
                for ro in range(4) 
                for i in range (n)
                ) <= 1 )

    #minimize the energy
    model.setObjective(
    gp.quicksum((taskset[i].perf[f][p][c>1][c%2][ro][1]*mulfp[f][i,p]*mulcro[c][i,ro] )  
                for f in range(12) 
                for p in range(2) 
                for c in range(4) 
                for ro in range(4) 
                for i in range (n))


    ,
    GRB.MINIMIZE)
    '''

    model.addConstr(gp.quicksum((taskset[i].perf[f][p][c][ro][0]/taskset[i].period)
                                 *mulfp[f][i,p]*mulcro[c][i,ro]
                for f in range(12) 
                for p in range(2) 
                for c in range(4)
                for ro in range(4)
                for i in range (n)
                ) <= 1 )

    #minimize the energy
    model.setObjective(
    gp.quicksum((taskset[i].perf[f][p][c][ro][1]*mulfp[f][i,p]*mulcro[c][i,ro] )  
                for f in range(12) 
                for p in range(2)  
                for c in range(4)
                for ro in range(4) 
                for i in range (n))


    ,
    GRB.MINIMIZE)

    model.optimize()

    
    if model.Status == GRB.INF_OR_UNBD:
        raise Exception('Model is infeasible or unbounded')
    elif model.Status == GRB.INFEASIBLE:
        raise Exception('Model is infeasible')
    elif model.Status == GRB.UNBOUNDED:
        raise Exception('Model is unbounded')
    x_f_sol = model.getAttr("x", x_f)
    x_p_sol = model.getAttr("x", x_p)
    x_c_sol = model.getAttr("x", x_c)
    x_pre_sol = model.getAttr("x", x_pre)
    x_prec_sol = model.getAttr("x")
    x_ro_sol = model.getAttr("x", x_ro)

dico = gen_dictionnary("./bench")
solver(gen_taskset(2,1, dico, 256000, 40000, 8000))