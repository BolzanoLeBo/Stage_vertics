import csv
from glob import glob
import pandas as pd
import sys
import numpy as np
from drs import drs
import copy
from schedcat.model.tasks import SporadicTask, TaskSystem


def gen_taskset(nb_tasks, util):
    max_tab = [9999 for i in range(10)]
    max_tab2 = [max_tab, max_tab]
    freqs = ['24MHz', '48MHz', '72MHz']
    '''nb_tasks = int(sys.argv[1])
    util = int(sys.argv[2])'''

    #sample the runtimes
    
    size_i = {
        'FFT':1000,
        'RSA_enc':145, 
        'RSA_dec':172, 
        'bubble_sort':1280, 
        'bubble_sort_no_opt':1280,
        'dijkstra':532,
        'kalman':1620,
        'mat_mul':198,
        'pointer_chase':62,
        'sine':228
    }

    size_d = {
        'FFT':4000,
        'RSA_enc':500, 
        'RSA_dec':4000, 
        'bubble_sort':3910, 
        'bubble_sort_no_opt':3910,
        'dijkstra':6250,
        'kalman':4000,
        'mat_mul':4680,
        'pointer_chase':0,
        'sine':0
    }


    size_ro = {
        'FFT':0,
        'RSA_enc':0, 
        'RSA_dec':0, 
        'bubble_sort':0, 
        'bubble_sort_no_opt':0,
        'dijkstra':0,
        'kalman':0,
        'mat_mul':0,
        'pointer_chase':3910,
        'sine':6840
    }
    only_idata_codes = ['FFT','RSA_enc', 'RSA_dec', 'bubble_sort', 'bubble_sort_no_opt','dijkstra','kalman','mat_mul']
    only_ro_codes = ['pointer_chase', 'sine']
    bench_order = []
    bench_init = 0
    benchs = ['FFT',
                'RSA_enc', 
                'RSA_dec', 
                'bubble_sort', 
                'bubble_sort_no_opt',
                'dijkstra',
                'kalman',
                'mat_mul',
                'pointer_chase',
                'sine']
    dico_bench = {'FFT':[9999,9999],
                'RSA_enc':[9999,9999], 
                'RSA_dec':[9999,9999], 
                'bubble_sort':[9999,9999], 
                'bubble_sort_no_opt':[9999,9999],
                'dijkstra':[9999,9999],
                'kalman':[9999,9999],
                'mat_mul':[9999,9999],
                'pointer_chase':[9999,9999],
                'sine':[9999,9999]}
    
    dico_ro = {"no_ro" :copy.deepcopy(dico_bench), "ro_f" :copy.deepcopy(dico_bench),
                "ro_r" : copy.deepcopy(dico_bench), "ro_c" : copy.deepcopy(dico_bench)}
    dico_data = {"no_d" : copy.deepcopy(dico_ro), "dr": copy.deepcopy(dico_ro), 
                 "dc" : copy.deepcopy(dico_ro)}
    dico_instr = {"cf":copy.deepcopy(dico_data), "cc" : copy.deepcopy(dico_data)}

    dico_f = {"24MHz" : copy.deepcopy(dico_instr), "48MHz" : copy.deepcopy(dico_instr),
              "72MHz" : copy.deepcopy(dico_instr)}
    #exemple : 
    # dico_f["48MHz"]["cc"]["dr"]["ro_f"]["FFT"][0] 
    # => runtime of bench FFT at 48 MHz when code is in ccm, no ro and input data in ram
    # => if there is no tests with ro it will be 9999 in the dictionnary and not used

    #append the non read only codes data
    files = glob("./bench/*.csv")
    for file in files : 
        with open(file, 'r') as f : 
            reader = csv.DictReader(f, delimiter = '\t')
            found = 1
            for col in reader :
                for f in freqs : 
                    name = file.removeprefix("./bench\\")
                    #select which data type we use
                    if "runtime" in name : 
                        unit = 0
                    elif "energy" in name : 
                        unit = 1
                    else : 
                        found = 0

                    #select what executions we extract data from
                    if "data_RAM" in name : 
                        data = "dr"
                    elif "data_CCM" in name :
                        data = "dc"
                    else : 
                        data = "no_d"

                    if "code_FLASH" in name : 
                        code = "cf"
                    elif "code_CCM" in name : 
                        code = 'cc'
                    else : 
                        found = 0 

                    if "ro_FLASH" in name : 
                        ro = "ro_f"
                    elif "ro_RAM" in name : 
                        ro = "ro_r"
                    elif "ro_CCM" in name : 
                        ro = "ro_c"
                    else : 
                        ro = "no_ro"
                    
                    
                    
                    #update the corresponding dictionnary at the good place
                    bench_name = col["group"]
                    #it can occurs that ro only are in the other data we don't want to add this
                    if bench_name in only_ro_codes and data != "no_d" : 
                        found = 0
                    if found and bench_name in benchs : 
                        dico_f[f][code][data][ro][bench_name][unit] = float(col[f])
    #print(dico_f["72MHz"]["cf"]["dr"]["no_ro"])
    #----------------------------GENERATE TASK SET--------------------------------------------
    #make random utilization 
    utils = drs(nb_tasks, util)

    taskset = TaskSystem()
    data_size = 0

    for i in range (nb_tasks) : 

        #choose a random benchmark for the task
        task_name = np.random.choice(benchs)
        task_id = benchs.index(task_name)
        print(task_name, task_id)


        #ref runtime is the reference runtime it is how normally the code is executed
        if task_name in only_idata_codes : 
            ref_runtime = dico_f["72MHz"]["cf"]["dr"]["no_ro"][task_name][0]
            ref_energy = dico_f["72MHz"]["cf"]["dr"]["no_ro"][task_name][1]
        elif task_name in only_ro_codes : 
            ref_runtime = dico_f["72MHz"]["cf"]["no_d"]["ro_f"][task_name][0]
            ref_energy = dico_f["72MHz"]["cf"]["no_d"]["ro_f"][task_name][1]
        else : 
            ref_runtime = dico_f["72MHz"]["cf"]["dr"]["ro_f"][task_name][0]
            ref_energy = dico_f["72MHz"]["cf"]["dr"]["ro_f"][task_name][1]
        period = ref_runtime/utils[i]
        #create the task
        task = SporadicTask(ref_runtime, period)
        #task parameters (for the optimization algo)
        task.ref_runtime = ref_runtime
        task.ref_energy = ref_energy
        task.name = task_name
        task.size_i = size_i[task_name]
        task.size_d = size_d[task_name]
        task.size_ro = size_ro[task_name]


        c_index = ["cf", "cc"]
        d_index = ["no_d", "dr", "dc"]
        ro_index = ["no_ro", "ro_f", "ro_r", "ro_c"]
        
        #init all the tasks info
        perf = []
        for f in range (len(freqs)) : 
            perf.append([])
            for c in range (len(c_index)) :
                perf[f].append([]) 
                for d in range (len(d_index)) : 
                    perf[f][c].append([])                    
                    for ro in range (len(ro_index)):
                        perf[f][c][d].append(dico_f[freqs[f]][c_index[c]][d_index[d]][ro_index[ro]][task_name])                
        task.perf = perf
        taskset.append(task)
        data_size += size_d[task.name]
    taskset.assign_ids_by_deadline()
    taskset.sort_by_deadline()
    #set storage size 
    taskset.ram_size = 40000
    taskset.ccm_size = 500
    taskset.flash_size = 256000
    #print the runtime and the period
    print(taskset)
    print(data_size)
    #print(taskset[0].name, taskset[0].perf)
    return(taskset)