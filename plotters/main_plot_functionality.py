def plot_results(outputs_dir, p_gantt=50):
    """
    This method wraps `main_plot_functionality` to call all functionality/reoccupancy recovery
    plots by requiring only the directory of the output.
    
    Parameters
    ----------
    output dir: string
        Directory of outputs
    p_gantt: float
        percentile of functional recovery time to plot for the gantt chart
        default: 50 = 50th percentile of functional recovery time (median)
    
    """
    import os
    import json
    import pandas as pd
    
    # from plotters import main_plot_functionality
    # Plot Functional Recovery Plots For a Single Model and Single Intensity
    
    ## Define User inputs
    
    # Load systems information
    systems = pd.read_csv(os.path.join(os.path.dirname(__file__), os.pardir, 'src', 'atc138', 'data', 'systems.csv'))
    systems = systems['name']
    
    # outputs will save to a directory with this name
    plot_dir = outputs_dir +'/plots' # Directory where the plots will be saved
    
    ## Import Packages
    
    ## Load Assessment Output Data
    f = open(os.path.join(outputs_dir, 'recovery_outputs.json'))
    functionality= json.load(f)
    
    ## Create plot for single intensity assessment of PBEE Recovery
    main_plot_functionality(functionality, plot_dir, p_gantt, systems)

def main_plot_functionality(functionality, save_dir, p_gantt, systems):
    '''
    This method calls all functionality and occupancy loss and recovery plots, including the following
    - Component and system-level breakdowns of hinderance to reoccupancy and functional status per day
    - Distribution of realizations achieving reoccupancy and functional status per day
    - Mean and per-realization breakdown of recovery trajectories
    - Gantt chart of impeding factors, repair work, number of workers, 
    and recovery status of building per day for the realization with `p_gantt`-th percentile of functional recovery day. 
    
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
    other_plot_functions.plt_recovery_trajectory(recovery, full_repair_time, plot_dir)
    
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
    


