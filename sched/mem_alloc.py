import time
import gurobipy as gp
from gurobipy import GRB
import numpy as np
from multiprocessing import Pool

from gen_taskset import gen_taskset

def solver(taskset) : 
    n = len(taskset)
    
    model = gp.Model("ilp_ram_allocator")
    model.setParam('OutputFlag', 0)
    model.setParam('TimeLimit', 3600)
    model.setParam('Threads', 1)

    x_f = model.addVars(n,3, vtype = GRB.BINARY)
    x_c = model.addVars(n,2, vtype = GRB.BINARY)
    x_d = model.addVars(n,3, vtype = GRB.BINARY)
    x_ro = model.addVars(n,4, vtype = GRB.BINARY)

    mulfc = []
    for i in range(3) : 
        mulfc.append(model.addVars(n,2,vtype = GRB.BINARY))

    
    muldro = []
    for i in range(3) : 
        muldro.append(model.addVars(n,4,vtype = GRB.BINARY))

    '''
        x_f : 
        100 24
        010 48
        001 72

        x_c : 
        10 cf 
        01 cc

        x_d : 
        100 no_d 
        010 dr
        001 dc

        x_ro : 
        1000 no_ro 
        0100 ro_f
        0010 ro_r
        0001  ro_c

        '''
    
    #var dimension 
    #no multiple allocation
    model.addConstrs(gp.quicksum(x_f[i,j] for j in range(3) )== 1 for i in range(n))
    model.addConstrs(gp.quicksum(x_c[i,j] for j in range(2) )== 1 for i in range(n))
    model.addConstrs(gp.quicksum(x_d[i,j] for j in range(3) )== 1 for i in range(n))
    model.addConstrs(gp.quicksum(x_ro[i,j] for j in range(4) )== 1 for i in range(n))
    #FLASH size constraint
    #we can have instruction or ro data
    model.addConstr(gp.quicksum(taskset[i].size_i * x_c[i,0] + 
                                taskset[i].size_ro * x_c[i,1] 
                                for i in range(n)) <= taskset.flash_size)
    #CCM size constraint
    #we can have instruction, ro data or input data
    model.addConstr(gp.quicksum(taskset[i].size_i * x_c[i,1] + 
                                taskset[i].size_ro * x_ro[i,3] +
                                taskset[i].size_d * x_d[i,2] 
                                for i in range(n)) <= taskset.ccm_size)
    #SRAM size constraint 
    #we can have input data or ro data 
    model.addConstr(gp.quicksum(taskset[i].size_ro * x_ro[i,2] +
                                taskset[i].size_d * x_d[i,1] 
                                for i in range(n)) <= taskset.ram_size)
    
    #we cannot multiply more than 3 elements so we do pre-mutliplication
    model.addConstrs(mulfc[f][i,c] == x_f[i,f]*x_c[i,c] 
                  for i in range (n) 
                  for f in range (3)
                  for c in range (2))
    
    model.addConstrs(muldro[d][i,ro] == x_d[i,d]*x_ro[i,ro] 
                  for i in range (n) 
                  for d in range (3)
                  for ro in range (4))
    
    #utilization less than 1 
    model.addConstr(gp.quicksum((taskset[i].perf[f][c][d][ro][0]/taskset[i].period)
                                 *mulfc[f][i,c]*muldro[d][i,ro]  
                for f in range(3) 
                for c in range(2) 
                for d in range(3) 
                for ro in range(4) 
                for i in range (n)
                ) <= 1 )

    #minimize the energy
    model.setObjective(
    gp.quicksum((taskset[i].perf[f][c][d][ro][1]*mulfc[f][i,c]*muldro[d][i,ro])  
                for f in range(3) 
                for c in range(2) 
                for d in range(3) 
                for ro in range(4) 
                for i in range (n))
    ,
    GRB.MINIMIZE)


    model.optimize()
    x_f_sol = model.getAttr("x", x_f)
    x_c_sol = model.getAttr("x", x_c)
    x_d_sol = model.getAttr("x", x_d)
    x_ro_sol = model.getAttr("x", x_ro)
    
    f_str = ["24", "48", "72"]
    c_str = ["code Flash", "code CCM"]
    d_str = ["no Idata", "data ram", "data ccm"]
    ro_str = ["no ro", "ro FLASH", "ro RAM", "ro CCM"]
    U_tot = 0
    for i in range (n) : 
        x_index = [0,0,0,0]
        for j in range (4) : 
            if j < 3 : 
                if x_f_sol[i,j] > 0 : 
                    x_index[0] = j
                if x_d_sol[i,j] > 0 : 
                    x_index[2] = j
            if j < 2 : 
                if x_c_sol[i,j] > 0 : 
                    x_index[1] = j

            if x_ro_sol[i,j] > 0 : 
                x_index[3] = j      
        f, c, d, ro = x_index      
        print(taskset[i].name, f_str[f],
            c_str[c], d_str[d],ro_str[ro])
        util = taskset[i].perf[f][c][d][ro][0]/taskset[i].period
        print(taskset[i].ref_runtime/taskset[i].period)
        U_tot += util
    print("total utilization :", U_tot)
def main(): 
    solver(gen_taskset(6, 1))

main()