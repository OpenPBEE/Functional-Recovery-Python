def plt_heatmap_breakdowns(recovery, plot_dir):
    '''Plot the time and percent of realizations that each system and/or 
    component is impeding function as a heatmap and as lineplots
    
    Parameters
    ----------
    recovery: dictionary
     dictionary containing recovery breakdown data from the functional
     recovery assessment
     
    plot_dir: str
     Save directory for plots. Plots will save directly to this location as
     png files.
    
    Returns
    -------'''
    
    import seaborn as sb
    import matplotlib.pyplot as plt
    import os
    import numpy as np
    
    
    ## Initial Setup
    if os.path.exists(plot_dir) == False:
        os.mkdir(plot_dir)
    plot_dir=plot_dir +'/'
    
    perform_targ_days = recovery['reoccupancy']['breakdowns']['perform_targ_days']
    perform_targ_labs = ['Immediately', '>3 Days', '>7 Days', '>2 Weeks', '>1 Month', '>2 Months', '>3 Months', '>4 Months', '>6 Months', '>9 Months', '>1 Year', ]
    
    #FZ# Maximum day for recovery amongs all tenant units and all realizations
    recovery_day_max = perform_targ_days[-1]
   
    if recovery_day_max <= 365:
        perform_targ_labs = perform_targ_labs # Number of days for each performance target stripe
    if recovery_day_max > 365:
        num_years = (int(np.floor((recovery_day_max)/365)))
        
        # If number of complete years is more than 2
        for yr in range(num_years-1):
            quarters =[1,2,3]
            for qtr in quarters:
                if yr == 0:
                    perform_targ_labs.append('>' + str(yr+1) +' Year & ' + str(qtr*3)+ ' months')
                if yr > 0:
                    perform_targ_labs.append('>' + str(yr+1) +' Years & ' + str(qtr*3)+ ' months')    
            perform_targ_labs.append('>' + str(yr+2) +' Years')
        
        # For final incomplete year
        num_quarters = int(np.floor((recovery_day_max - num_years*365)/90))
        compl_yr = perform_targ_labs[-1]
        for qtr in range(num_quarters):
            perform_targ_labs.append(compl_yr + ' & '+str((qtr+1)*3) + ' Months')

        perform_targ_labs.append(perform_targ_labs[-1] + ' & ' + str(int(perform_targ_days[-1] - perform_targ_days[-2])) + ' Days')    

    
    var = ['component_breakdowns', 'system_breakdowns']
    labs = ['comp_names', 'system_names']
    plt_ht = [10, 8]
    
    ## Plot Heatmaps
    fnc_states = list(recovery.keys())
    for fs in range(len(fnc_states)):
        
        perform_targ_days = recovery[fnc_states[fs]]['breakdowns']['perform_targ_days']
        perform_targ_labs = ['Immediately', '>3 Days', '>7 Days', '>2 Weeks', '>1 Month', '>2 Months', '>3 Months', '>4 Months', '>6 Months', '>9 Months', '>1 Year', ]
        
        #FZ# Maximum day for recovery amongs all tenant units and all realizations
        recovery_day_max = perform_targ_days[-1]
       
        if recovery_day_max <= 365:
            perform_targ_labs = perform_targ_labs # Number of days for each performance target stripe
        if recovery_day_max > 365:
            num_years = (int(np.floor((recovery_day_max)/365)))
            
            # If number of complete years is more than 2
            for yr in range(num_years-1):
                quarters =[1,2,3]
                for qtr in quarters:
                    if yr == 0:
                        perform_targ_labs.append('>' + str(yr+1) +' Year & ' + str(qtr*3)+ ' months')
                    if yr > 0:
                        perform_targ_labs.append('>' + str(yr+1) +' Years & ' + str(qtr*3)+ ' months')    
                perform_targ_labs.append('>' + str(yr+2) +' Years')
            
            # For final incomplete year
            num_quarters = int(np.floor((recovery_day_max - num_years*365)/90))
            compl_yr = perform_targ_labs[-1]
            for qtr in range(num_quarters):
                perform_targ_labs.append(compl_yr + ' & '+str((qtr+1)*3) + ' Months')
    
            perform_targ_labs.append(perform_targ_labs[-1] + ' & ' + str(int(perform_targ_days[-1] - perform_targ_days[-2])) + ' Days')        
        
        # system breakdown for line plots
        sys_bkdn = np.array(recovery[fnc_states[fs]]['breakdowns'][var[1]])
        systs = recovery[fnc_states[fs]]['breakdowns'][labs[1]]
        # no. of systems in one plot (total 3 plots)
        num_systems = int(np.floor(len(systs)/3))
        
        # Plot 1
        plt.figure(figsize=([6,6]))
        for syst in range(num_systems):
            plt.plot(perform_targ_days, sys_bkdn[syst], marker ='o', label=systs[syst])
        plt.ylim([0,1])
        plt.xlabel('Recovery Time After Earthquake (Days')
        plt.ylabel('Fraction of Realizations Affecting Building')
        plt.title(var[1] +' '+fnc_states[fs] + ' lineplot 1')
        plt.legend()
        plt.grid()
        plt.savefig(plot_dir + var[1] +' '+fnc_states[fs] + ' lineplot 1.png', dpi=300)
        
        # Plot 2
        plt.figure(figsize=([6,6]))
        for syst in range(num_systems):
            plt.plot(perform_targ_days, sys_bkdn[num_systems + syst], marker ='o', label=systs[num_systems + syst])
        plt.ylim([0,1])
        plt.xlabel('Recovery Time After Earthquake (Days')
        plt.ylabel('Fraction of Realizations Affecting Building')
        plt.title(var[1] +' '+fnc_states[fs] + ' lineplot 2')
        plt.legend()
        plt.grid()
        plt.savefig(plot_dir + var[1] +' '+fnc_states[fs] + ' lineplot 2.png', dpi=300)        
        
        # Plot 3
        plt.figure(figsize=([6,6]))
        for syst in range(len(systs) - num_systems*2):
            plt.plot(perform_targ_days, sys_bkdn[2*num_systems + syst], marker ='o', label=systs[2*num_systems + syst])
        plt.ylim([0,1])
        plt.xlabel('Recovery Time After Earthquake (Days')
        plt.ylabel('Fraction of Realizations Affecting Building')
        plt.title(var[1] +' '+fnc_states[fs] + ' lineplot 3')
        plt.legend()
        plt.grid()
        plt.savefig(plot_dir + var[1] +' '+fnc_states[fs] + ' lineplot 3.png', dpi=300)
        
        
        # Heat maps
        for v in range(len(var)):
            y_labs = recovery[fnc_states[fs]]['breakdowns'][labs[v]]
            data = np.array(recovery[fnc_states[fs]]['breakdowns'][var[v]])
            
            plt.rcParams["font.family"] = "Times New Roman"
            plt.figure(figsize=(plt_ht))
            h = sb.heatmap(data, cmap='Blues', linewidths = 0.5, linecolor = 'black', annot = np.round(data,2), xticklabels = perform_targ_labs, yticklabels = y_labs, clip_on = False)
            fnc_lab = fnc_states[fs][0].upper() + fnc_states[fs][1:len(fnc_states[fs])]+' Recovery'
            title = 'Fraction of Realizations Affecting Building ' + fnc_lab
            h.set(xlabel  = 'Recovery Time After Earthquake')
            # h.set(ylabel = labs[v])
            h.set_title(title, x=0.5, y=1.05)
            plt.xticks(rotation=90)
            plt.subplots_adjust(bottom=0.15)
            
            plt.savefig(plot_dir + var[v] +' '+fnc_states[fs] + '.png', dpi=300)

    return


def plt_histograms( recovery, plot_dir ):
    
    '''Plot all realizations of building level recovery as a histogram
    
    Parameters
    ----------
    recovery: dictionary
      dictionary containing building-level recovery data from the 
      functional recovery assessment
     
    plot_dir: str
      Save directory for plots. Plots will save directly to this location as
      png files.
    
    Returns
    -------'''
    
    import seaborn as sb
    import matplotlib.pyplot as plt
    import os
    
    ## Initial Setup
    if os.path.exists(plot_dir) == False:
        os.mkdir(plot_dir)
    plot_dir=plot_dir +'/'
    
    ## Plot Histograms
    fnc_states = list(recovery.keys())
    for fs in range(len(fnc_states)):
        plt.rcParams["font.family"] = "Times New Roman"
        plt.figure(figsize=(6,4))
        sb.histplot(data = recovery[fnc_states[fs]]['building_level']['recovery_day'])
        fnc_lab = fnc_states[fs][0].upper() + fnc_states[fs][1:len(fnc_states[fs])]+' Recovery'        
        plt.xlabel(fnc_lab + ' Time (days)')
        plt.ylabel('Number of Realizatons')
        plt.savefig(plot_dir + fnc_states[fs] + '.png', dpi=300)
        
    return


def plt_recovery_trajectory( recovery, full_repair_time, plot_dir):
    '''Plot mean recovery trajectories
    
    Parameters
    ----------
    recovery: dictionary
      dictionary containing recovery trajectory data from the functional
      recovery assessment
     
    full_repair_time: array [num reals x 1] 
      simulated realization of full repair time 
    
    plot_dir: str
      Save directory for plots. Plots will save directly to this location as
      png files.
    
    Returns
    -------'''
     
    
    import matplotlib.pyplot as plt
    import os
    import numpy as np
    
    ## Initial Setup
    if os.path.exists(plot_dir) == False:
        os.mkdir(plot_dir)
    plot_dir=plot_dir +'/'
    
    

    # Calculate mean recovery times
    reoc = np.mean(np.array(recovery['reoccupancy']['recovery_trajectory']['recovery_day']), axis=0)
    func = np.mean(np.array(recovery['functional']['recovery_trajectory']['recovery_day']), axis=0)
    med = np.median(np.array(recovery['functional']['recovery_trajectory']['recovery_day']), axis=0)
    per_10 = np.percentile(np.array(recovery['functional']['recovery_trajectory']['recovery_day']), 10, axis=0)
    per_90 = np.percentile(np.array(recovery['functional']['recovery_trajectory']['recovery_day']), 90, axis=0)
    full = np.mean(full_repair_time)
    level_of_repair = recovery['functional']['recovery_trajectory']['percent_recovered']
    
    # Plot Recovery Trajectory
    plt.rcParams["font.family"] = "Times New Roman"
    plt.figure(figsize=(6,4)) 
    plt.plot(reoc, level_of_repair,'r-', linewidth = 1.5, label = 'Re-Occupancy') 
    plt.plot(func, level_of_repair,'b-', linewidth = 1.5, label= 'Functional') 
    plt.plot([full, full], [0, 1],'k-', linewidth = 1.5, label= 'Fully Repaired') 
    plt.xlim([0,np.ceil((full+1)/10)*10])
    plt.xlabel('Days After Earthquake')
    plt.ylabel('Fraction of Floor Area')
    plt.legend(loc='upper left')
    plt.grid()
    plt.show()
    
    plt.savefig(plot_dir + 'recovery_trajectory.png', dpi=300)
    
    plt.figure(figsize=(6,4))
    for i in range(len(recovery['functional']['recovery_trajectory']['recovery_day'])):
        plt.plot(recovery['functional']['recovery_trajectory']['recovery_day'][i] , level_of_repair, color = 'lightgrey', linewidth = 0.5)
    plt.plot(med, level_of_repair,'r-', linewidth = 1.5, label= 'Median')
    plt.plot(per_10, level_of_repair,'b--', linewidth = 1.0, label= '10th percentile')
    plt.plot(per_90, level_of_repair,'b--', linewidth = 1.0, label= '90th percentile')
    plt.xlim([0,np.ceil((max(max(recovery['functional']['recovery_trajectory']['recovery_day'])))/10)*10])
    plt.title('Functional Recovery Trajectories')
    plt.xlabel('Days After Earthquake')
    plt.ylabel('Fraction of Floor Area')
    plt.legend(loc='upper left')
    plt.grid()    

    plt.savefig(plot_dir + 'functional_recovery_trajectories.png', dpi=300)
    
    return


def plt_gantt_chart(p_idx, recovery, full_repair_time, workers, schedule, impede, plot_dir, plot_name, systems):
    '''Plot gantt chart for a single realization of the functional recovery
    assessment
    
    Parameters
    ----------
    p_idx: int
      realization index of interest
     
    recovery: dictionary
      dictionary containing recovery trajectory data from the functional
      recovery assessment
    
    full_repair_time: array [num reals x 1] 
      simulated realization of full repair time 
    
    workers: dictionary
      data structure containing work allocation data from the functional
      recovery assessment
    
    schedule: dictionary
      dictionary containing repair schedule data from the functional
      recovery assessment
    
    impede: dictionary
      data structure containing impedance time data from the functional
      recovery assessment
    
    plot_dir: str
      Save directory for plots. Plots will save directly to this location as
      png files.
     
    plot_name: str
      name of file to save plot as (does not include the file type extension)
    
    Returns
      -------'''

    import matplotlib.pyplot as plt
    import os
    import numpy as np
    
    ## Initial Setup
    if os.path.exists(plot_dir) == False:
        os.mkdir(plot_dir)
    plot_dir=plot_dir +'/'
    
    imps = list(impede.keys())
    sys = list(systems)
    
    ## Format Gantt Chart Data
    recovery_trajectory = {
        'reoc' : np.array(recovery['reoccupancy']['recovery_trajectory']['recovery_day'])[p_idx,:],
        'func' : np.array(recovery['functional']['recovery_trajectory']['recovery_day'])[p_idx,:],
        'level_of_repair' : np.array(recovery['reoccupancy']['recovery_trajectory']['percent_recovered']),
        'ful_rep' : np.ones(len(recovery['reoccupancy']['recovery_trajectory']['percent_recovered'])) * np.ceil(full_repair_time[p_idx])
        }
    
    # Collect Worker Data
    worker_data = {
        'total_workers' : np.array(workers['total_workers'])[p_idx,:],
        'day_vector' : np.array(workers['day_vector'])[p_idx,:]
        }
    
    # Collect Impedance Times
    sys_imp_times = []
    labs = []
    for i in range(len(imps)):
        duration = impede[imps[i]]['complete_day'][p_idx] - impede[imps[i]]['start_day'][p_idx]
        # if duration > 0:
        sys_imp_times.append([impede[imps[i]]['start_day'][p_idx], duration])
        labs.append(imps[i][0].upper() + imps[i][1:len(imps[i])].replace('_',' '))
     
    labs_imp = np.array(labs)
    y_imp = np.array(sys_imp_times)

    # Collect Repair Times 
    sys_repair_times = []
    labs = []
    for s in range(len(sys)): 
        duration = schedule['full']['repair_complete_day']['per_system'][p_idx][s] - schedule['full']['repair_start_day']['per_system'][p_idx][s]
        if duration > 0:
            sys_repair_times.append([schedule['full']['repair_start_day']['per_system'][p_idx][s], duration])
            labs.append(sys[s][0].upper() + sys[s][1:len(sys[s])] + ' Repairs')

    labs.reverse()    
    labs_rep = labs
    y_rep = np.flip(np.array(sys_repair_times), axis=0)
    ## Plot Gantt
    
    plt.rcParams["font.family"] = "Times New Roman"
    # Impedance Time
    fig, (G1, G2, G3, G4) = plt.subplots(4, 1, sharex=True, figsize = (10,12), gridspec_kw={'height_ratios': [2, 1, 1, 1]})
    G1.barh(labs_imp, y_imp[:,0], color = 'white')    
    G1.barh(labs_imp, y_imp[:,1], left = y_imp[:,0], color='lightgrey')
    G1.set_title('Impedance Time')
    G1.grid(which = 'major', axis = 'x', alpha=0.5)
    # G1.set_xlabel('Days After Earthquake')
    
    # Repair Time
    G2.barh(labs_rep, y_rep[:,0], color = 'white')
    G2.barh(labs_rep, y_rep[:,1], left = y_rep[:,0], color='grey')
    G2.set_title('Repair Time') 
    G2.grid(which = 'major', axis = 'x', alpha=0.5)    
    
    
    # Workers
    G3.plot(worker_data['day_vector'], worker_data['total_workers'])
    G3.set_ylabel('Number of workers')
    G3.set_title('Number of workers')
    G3.grid(which = 'major', axis = 'x', alpha=0.5) 
    
    # Plot Recovery Trajectory
    G4.plot(recovery_trajectory['reoc'], recovery_trajectory['level_of_repair'],'r-', linewidth = 1.5, label = 'Re-Occupancy')
    G4.plot(recovery_trajectory['func'], recovery_trajectory['level_of_repair'],'b-', linewidth = 1.5, label = 'Functional')
    G4.plot(recovery_trajectory['ful_rep'], recovery_trajectory['level_of_repair'],'k-', linewidth = 1.5, label = 'Fully Repaired')
    G4.set_ylim([0,1])
    G4.set_xlabel('Days After Earthquake')
    G4.set_ylabel('Fraction of Floor Area')
    G4.set_title('Building Recovery State')
    G4.grid(which = 'major', axis = 'x', alpha=0.5)
    G4.legend()
    fig.subplots_adjust(left=0.20)
    fig.savefig(plot_dir + plot_name + '.png', dpi=300)
    
    return
