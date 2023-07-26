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

    mode = model.addVars(n, 6, vtype = GRB.BINARY)
    '''
    100000 => cfdr   cfror
    010000 => ccdr   ccror
    001000 => cfdc 
    000100 => ccdc  
    000010 =>        cfrof
    000001 =>        ccrof
    '''
    mode_to_string = ["cfdr/cfror", "ccdr/ccror", "cfdc", "ccdc", "cfrof", "ccrof"]
    #var dimension 
    model.addConstrs(gp.quicksum(mode[i,j] for j in range(6) )== 1 for i in range(n))

    '''#FLASH size constraint
    #instruction in flash when mode divisible by 2 | data in flash when mode >= 4 
    model.addConstr(gp.quicksum(taskset[i].size_i * (mode[i]%2 == 0) + taskset[i].size_d * (mode[i] >= 4) for i in range(n)) <= taskset.flash_size)
    #CCM size constraint
    #instruction in ccm when mode not divisible by 2 | data in ccm when mode = 2 or 3
    model.addConstr(gp.quicksum(taskset[i].size_i * (mode[i]%2) + taskset[i].size_d * ((mode[i]-2) * (mode[i]-3) == 0) for i in range(n)) <= taskset.ccm_size)
    #SRAM size constraint 
    #data in ram when mode is equal to 0 or 1 
    model.addConstr(gp.quicksum(taskset[i].size_i * (mode[i]*(mode[i]-1) ==0) for i in range(n)) <= taskset.ram_size)
    '''
    model.setObjective(
    gp.quicksum(taskset[i].boost[j][0][0]*mode[i,j] for i in range(n) for j in range(6))
    ,
    GRB.MINIMIZE)


    model.optimize()
    mode_sol = model.getAttr("x", mode)
    for i in range (n) : 
        mode_index = 0
        for j in range (6) : 
            if mode_sol[i,j] > 0 : 
                mode_index = j
        print(taskset[i].name, mode_to_string[mode_index] )

def main(): 
    solver(gen_taskset(5, 1))

main()