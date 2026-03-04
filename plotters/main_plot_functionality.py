def main_plot_functionality(functionality, save_dir, p_gantt, systems):
    '''Plot function and occupancy loss and recovery at for a single model at a 
    single intensity levels
    
    Parameters
    ----------
    functionality: dictionary
     main output data strcuture of the functional recovery assessment. 
     Loaded directly from the output mat file.
    save_dir: str
     Save directory for plots. Plots will save directly to this location as
     png files.
    p_gantt: int
     percentile of functional recovery time to plot gantt chart
    
    Returns
    -------'''
     
    import numpy as np
    import os
    
    ## Initial Setup
    # Import Packages
    from plotters import other_plot_functions
    
    # Set plot variables to use
    recovery = functionality['recovery']
    impede = functionality['impeding_factors']['breakdowns']['full']
    schedule = functionality['building_repair_schedule']
    workers = functionality['worker_data']
    full_repair_time = np.nanmax(np.array(schedule['full']['repair_complete_day']['per_story']), axis=1)
    
    if os.path.exists(save_dir) == False:
        os.mkdir(save_dir)
    ## Plot Performance Objective Grid for system and component breakdowns

    plot_dir = os.path.join(save_dir,'breakdowns')
    other_plot_functions.plt_heatmap_breakdowns(recovery, plot_dir)
    
    ## Plot Performance Target Distribution Across all Realizations
    plot_dir = os.path.join(save_dir,'histograms')
    other_plot_functions.plt_histograms(recovery,plot_dir)
    
    ## Plot Mean Recovery Trajectories
    plot_dir = os.path.join(save_dir,'recovery_trajectories')
    other_plot_functions.plt_recovery_trajectory( recovery, full_repair_time, plot_dir)
    
    # Plot Gantt Charts
    plot_dir = os.path.join(save_dir,'gantt_charts')
    fr_time = np.array(functionality['recovery']['functional']['building_level']['recovery_day'])
    if len(np.where(fr_time == np.percentile(fr_time,p_gantt))[0])>0:
        p_idx = np.where(fr_time == np.percentile(fr_time,p_gantt))[0][0] # Find the index of the first realization that matches the selected percentile
        
    else:
        diff = abs(fr_time - np.percentile(fr_time,p_gantt))
        p_idx = np.where(diff == min(diff))[0][0]
        from scipy.stats import percentileofscore
        p_gantt = percentileofscore(fr_time, fr_time[p_idx])
    
        
    plot_name = 'prt_'+str(p_gantt)
    other_plot_functions.plt_gantt_chart(p_idx, recovery, full_repair_time, workers, schedule, impede, plot_dir, plot_name, systems)
    


