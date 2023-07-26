import csv
from glob import glob
import pandas as pd
import sys
import numpy as np
from drs import drs
import copy
from schedcat.model.tasks import SporadicTask, TaskSystem


def gen_taskset(nb_tasks, util):
    freqs = ['24MHz', '48MHz', '72MHz']
    '''nb_tasks = int(sys.argv[1])
    util = int(sys.argv[2])'''

    #sample the runtimes
    files = glob("./runtime_bench/*.csv")
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
        'pointer_chase':3910,
        'sine':6840
    }
    ro_codes = ['pointer_chase', 'sine']
    bench_order = []
    bench_init = 0
    no_ro_dico = {'FFT':0,
                'RSA_enc':0, 
                'RSA_dec':0, 
                'bubble_sort':0, 
                'bubble_sort_no_opt':0,
                'dijkstra':0,
                'kalman':0,
                'mat_mul':0}
    ro_dico = {
            'pointer_chase':0,
            'sine':0}
    
    ex_dico = {"cfdr" : copy.deepcopy(no_ro_dico), "cfdc" : copy.deepcopy(no_ro_dico), "ccdr" : copy.deepcopy(no_ro_dico), "ccdc" : copy.deepcopy(no_ro_dico), "cfrof" : copy.deepcopy(no_ro_dico), 
               "cfroc" : copy.deepcopy(ro_dico), "cfror" : copy.deepcopy(ro_dico), "cfrof" : copy.deepcopy(ro_dico),
               "ccrof" : copy.deepcopy(ro_dico), "ccroc" : copy.deepcopy(ro_dico), "ccror" :copy.deepcopy(ro_dico)}

    runtime = {"24MHz" : copy.deepcopy(ex_dico), "48MHz" : copy.deepcopy(ex_dico), "72MHz" : copy.deepcopy(ex_dico)}
    energy = {"24MHz" : copy.deepcopy(ex_dico), "48MHz" : copy.deepcopy(ex_dico), "72MHz" : copy.deepcopy(ex_dico)}
    #exemple : 
    # runtime['48MHz']["ccrof"]['sine']
    # => runtime of sine at 48 MHz when code is in ccm and ro data in flash

    #append the non read only codes data
    for file in files : 
        with open(file, 'r') as f : 
            reader = csv.DictReader(f, delimiter = '\t')
            for col in reader :
                if not bench_init : 
                    bench_order.append(col['group'])
                for f in freqs : 
                    name = file.removeprefix("./runtime_bench\\")
                    #select which data type we use
                    if "runtime" in name : 
                        dico = runtime
                    elif "energy" in name : 
                        dico = energy

                    #select what executions we extract data from
                    if "data_RAM-code_FLASH" in name : 
                        ex = "cfdr"
                    elif "data_CCM-code_FLASH" in name :                        
                        ex = "cfdc"
                    elif "data_RAM-code_CCM" in name : 
                        ex = "ccdr"
                    elif "data_CCM-code_CCM" in name : 
                        ex = "ccdc"
                    
                    #update the corresponding dictionnary at the good place
                    if col["group"] not in ro_codes : 
                        dico[f][ex][col['group']] = float(col[f])
                        
            bench_init = 1
    #append the read only codes data
    files = glob("./runtime_bench/read_only/*.csv")
    for file in files : 
        with open(file, 'r') as f : 
            reader = csv.DictReader(f, delimiter = '\t')
            for col in reader :
                for f in freqs : 
                    name = file.removeprefix("./runtime_bench/read_only\\")
                    code_name = col["group"]
                    if "runtime" in name : 
                        dico = runtime
                    elif "energy" in name : 
                        dico = energy
                    if "ro_RAM-code_FLASH" in name : 
                        ex = "cfror"
                    elif "ro_RAM-code_CCM" in name : 
                        ex = "ccror"
                    elif "ro_CCM-code_FLASH" in name : 
                        ex = "cfroc"
                    elif "ro_CCM-code_CCM" in name : 
                        ex = "ccroc"
                    elif "ro_FLASH-code_FLASH" in name : 
                        ex = "cfrof"
                    elif "ro_FLASH-code_CCM" in name : 
                        ex = "ccrof"
                    dico[f][ex][col['group']] = float(col[f]) 

    #----------------------------GENERATE TASK SET--------------------------------------------
    #make random utilization 
    utils = drs(nb_tasks, util)

    taskset = TaskSystem()
    data_size = 0
    max_tab = [9999 for i in range(10)]
    max_tab2 = [max_tab, max_tab]
    for i in range (nb_tasks) : 

        #choose a random benchmark for the task
        task_name = np.random.choice(bench_order)
        task_id = bench_order.index(task_name)
        print(task_name, task_id)
        #parameters are different if we have a benchmark with read only or not
        if task_name not in ro_codes : 
            #ref runtime is the reference runtime it is how normally the code is executed
            ref_runtime = runtime["72MHz"]["cfdr"][task_name]
            ref_energy = energy["72MHz"]["cfdr"][task_name]
            period = ref_runtime/utils[i]
            #create the task
            task = SporadicTask(ref_runtime, period)
            #task parameters (for the optimization algo)
            task.ref_runtime = ref_runtime
            task.ref_energy = ref_energy
            task.name = task_name
            task.type = 'not_ro'
            task.size_i = size_i[task_name]
            task.size_d = size_d[task_name]
            #gain when we use ccm : 
            #for code 
            task.boost_ccdr = [[runtime[f]["ccdr"][task_name] for f in freqs], 
                               [ref_energy - energy[f]["ccdr"][task_name] for f in freqs]]
            #for data
            task.boost_cfdc = [[runtime[f]["cfdc"][task_name]for f in freqs], 
                               [energy[f]["cfdc"][task_name]for f in freqs]]
            #for both
            task.boost_ccdc = [[runtime[f]["ccdc"][task_name] for f in freqs],
                               [energy[f]["ccdc"][task_name]for f in freqs]]
            #perf when we changes frequency but stay in flash
            task.change_f = [[runtime[f]["cfdr"][task_name] for f in freqs],
                             [energy[f]["cfdr"][task_name] for f in freqs]]
            #set the writting norme used in the ram allocate
            
            task.boost = [ task.change_f, task.boost_ccdr, task.boost_cfdc, task.boost_ccdc, max_tab2, max_tab2]
        else :
            ref_runtime = runtime["72MHz"]["cfrof"][task_name]
            ref_energy = energy["72MHz"]["cfrof"][task_name]
            period = ref_runtime/utils[i]
            task = SporadicTask(ref_runtime, period)
            task.ref_runtime = ref_runtime
            task.ref_energy = ref_energy
            task.type = 'ro'
            task.name = task_name
            task.size_i = size_i[task_name]
            task.size_d = size_d[task_name]
            #gain when we use ccm for code
            task.boost_ccrof = [[(runtime[f]["ccrof"][task_name]) for f in freqs], 
                                [(energy[f]["ccrof"][task_name]) for f in freqs]]
            #gain when we put ro_data in SRAM
            task.boost_cfror = [[(runtime[f]["cfror"][task_name]) for f in freqs],
                                [(energy[f]["cfror"][task_name]) for f in freqs]]
            #gain when we put ro_data in SRAM and code in CCM 
            task.boost_ccror = [[(runtime[f]["ccror"][task_name]) for f in freqs],
                                [(energy[f]["ccror"][task_name]) for f in freqs]]
            #perf when we changes frequency but stay in flash
            task.change_f = [[runtime[f]["cfrof"][task_name] for f in freqs],
                             [energy[f]["cfrof"][task_name] for f in freqs]]
            #set the writting norme
            task.boost = [task.boost_cfror,task.boost_ccror,max_tab2,max_tab2, task.change_f,task.boost_ccrof]

        
        taskset.append(task)
        data_size += size_d[task.name]
    taskset.assign_ids_by_deadline()
    taskset.sort_by_deadline()
    #set storage size 
    taskset.ram_size = 40000
    taskset.ccm_size = 8000
    taskset.flash_size = 256000
    #print the runtime and the period
    print(taskset)
    print(data_size)
    return(taskset)
